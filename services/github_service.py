"""GitHub Service — uses httpx only, no PyGithub dependency.

Commits all files atomically using the Git Data API (trees + commits)
instead of one PUT-per-file, which was racing against GitHub's
auto_init commit and silently dropping files on conflict.
"""
from __future__ import annotations

import base64
import logging
import time
import uuid
from typing import Any, Dict, List

import httpx

from models.schemas import GeneratedFile

logger = logging.getLogger(__name__)


class GitHubCommitError(Exception):
    """Raised when the atomic commit fails. Carries the real response body."""


class GitHubService:
    BASE = "https://api.github.com"

    def __init__(self, token: str, username: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.username = username

    def create_repo(self, repo_name: str, private: bool = False) -> Dict[str, Any]:
        # Every build run gets its own fresh repo, even if the project
        # name is identical (e.g. "cafe website" run 50 times). Without
        # this, every same-named run silently reused and piled commits
        # onto ONE shared repo, leaving stale files from old/broken
        # runs sitting alongside new ones forever (this was the actual
        # cause of "old TODO placeholder" and "old wrong route path"
        # errors resurfacing after fixes that had already worked).
        base_slug = repo_name.lower().replace(" ", "-")[:30]
        unique_suffix = uuid.uuid4().hex[:8]
        safe_name = f"{base_slug}-{unique_suffix}"

        r = httpx.post(
            f"{self.BASE}/user/repos",
            headers=self.headers,
            # auto_init=True: GitHub's Git Data API (blobs/trees) rejects
            # writes against a truly empty repo with no initial commit/ref
            # ("Git Repository is empty" 409). We need SOME initial commit
            # to exist. This is safe now (unlike the old code) because we
            # only ever make ONE atomic commit afterward in commit_files(),
            # not 17 separate racing PUTs — commit_files() reads the real
            # parent SHA from this initial commit and builds on top of it.
            json={"name": safe_name, "private": private, "auto_init": True},
            timeout=30,
        )
        if r.status_code == 201:
            data = r.json()
        elif r.status_code == 422:
            # Extremely unlikely name collision even with the random
            # suffix — retry once with a fresh suffix instead of ever
            # silently reusing an existing repo.
            unique_suffix = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
            safe_name = f"{base_slug}-{unique_suffix}"
            r2 = httpx.post(
                f"{self.BASE}/user/repos",
                headers=self.headers,
                json={"name": safe_name, "private": private, "auto_init": True},
                timeout=30,
            )
            r2.raise_for_status()
            data = r2.json()
        else:
            r.raise_for_status()
            data = r.json()

        return {
            "html_url": data.get("html_url", ""),
            "clone_url": data.get("clone_url", ""),
            "full_name": data.get("full_name", f"{self.username}/{safe_name}"),
            "repo_name": safe_name,
        }

    def commit_files(
        self,
        repo_full_name: str,
        files: List[GeneratedFile],
        commit_message: str,
        branch: str = "main",
    ) -> None:
        """Create ALL files in a single atomic commit via the Git Data API.

        This replaces the old per-file GET-then-PUT loop, which raced
        against repo initialization and silently dropped files whenever
        a PUT failed (the old code caught every exception and continued).
        """
        base_url = f"{self.BASE}/repos/{repo_full_name}"

        # 1. Read the initial commit GitHub created via auto_init=True.
        #    This can take a brief moment to land after create_repo()
        #    returns, so retry a few times instead of assuming it's
        #    instantly there (this is the actual race that bit us before).
        parent_sha = None
        base_tree_sha = None
        for attempt in range(5):
            ref_resp = httpx.get(f"{base_url}/git/ref/heads/{branch}", headers=self.headers, timeout=15)
            if ref_resp.status_code == 200:
                parent_sha = ref_resp.json()["object"]["sha"]
                commit_resp = httpx.get(f"{base_url}/git/commits/{parent_sha}", headers=self.headers, timeout=15)
                commit_resp.raise_for_status()
                base_tree_sha = commit_resp.json()["tree"]["sha"]
                break
            time.sleep(1.5)

        # 2. Create a blob for every file's content.
        tree_items = []
        for f in files:
            blob_resp = httpx.post(
                f"{base_url}/git/blobs",
                headers=self.headers,
                json={
                    "content": base64.b64encode(f.content.encode("utf-8")).decode("ascii"),
                    "encoding": "base64",
                },
                timeout=30,
            )
            if blob_resp.status_code != 201:
                raise GitHubCommitError(
                    f"Failed to create blob for {f.path}: "
                    f"{blob_resp.status_code} {blob_resp.text[:300]}"
                )
            tree_items.append({
                "path": f.path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_resp.json()["sha"],
            })

        # 3. Create a single tree containing every file.
        tree_body: Dict[str, Any] = {"tree": tree_items}
        if base_tree_sha:
            tree_body["base_tree"] = base_tree_sha
        tree_resp = httpx.post(f"{base_url}/git/trees", headers=self.headers, json=tree_body, timeout=30)
        if tree_resp.status_code != 201:
            raise GitHubCommitError(f"Failed to create tree: {tree_resp.status_code} {tree_resp.text[:300]}")
        new_tree_sha = tree_resp.json()["sha"]

        # 4. Create the commit pointing at that tree.
        commit_body: Dict[str, Any] = {"message": commit_message, "tree": new_tree_sha}
        if parent_sha:
            commit_body["parents"] = [parent_sha]
        new_commit_resp = httpx.post(f"{base_url}/git/commits", headers=self.headers, json=commit_body, timeout=30)
        if new_commit_resp.status_code != 201:
            raise GitHubCommitError(
                f"Failed to create commit: {new_commit_resp.status_code} {new_commit_resp.text[:300]}"
            )
        new_commit_sha = new_commit_resp.json()["sha"]

        # 5. Point the branch ref at the new commit (create it if it
        #    doesn't exist yet, since auto_init=False means no ref exists).
        if parent_sha:
            update_resp = httpx.patch(
                f"{base_url}/git/refs/heads/{branch}",
                headers=self.headers,
                json={"sha": new_commit_sha, "force": False},
                timeout=30,
            )
            ok_codes = (200,)
        else:
            update_resp = httpx.post(
                f"{base_url}/git/refs",
                headers=self.headers,
                json={"ref": f"refs/heads/{branch}", "sha": new_commit_sha},
                timeout=30,
            )
            ok_codes = (201,)

        if update_resp.status_code not in ok_codes:
            raise GitHubCommitError(
                f"Failed to update ref heads/{branch}: "
                f"{update_resp.status_code} {update_resp.text[:300]}"
            )

        logger.info(
            "Committed %d files to %s@%s as %s",
            len(files), repo_full_name, branch, new_commit_sha,
        )
