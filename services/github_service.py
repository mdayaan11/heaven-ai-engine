"""GitHub Service — uses httpx only, no PyGithub dependency.

Commits all files atomically using the Git Data API (trees + commits)
instead of one PUT-per-file, which was racing against GitHub's
auto_init commit and silently dropping files on conflict.
"""
from __future__ import annotations

import base64
import logging
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
        safe_name = repo_name.lower().replace(" ", "-")[:40]
        r = httpx.post(
            f"{self.BASE}/user/repos",
            headers=self.headers,
            # auto_init=False: we create the first commit ourselves via
            # the trees API below, so there's no initial README commit
            # to race against.
            json={"name": safe_name, "private": private, "auto_init": False},
            timeout=30,
        )
        if r.status_code not in (201, 422):
            r.raise_for_status()
        data = r.json()
        if r.status_code == 422:
            r2 = httpx.get(
                f"{self.BASE}/repos/{self.username}/{safe_name}",
                headers=self.headers, timeout=15,
            )
            r2.raise_for_status()
            data = r2.json()
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

        # 1. Does the branch already have a commit? (it won't, since
        #    create_repo() now uses auto_init=False)
        parent_sha = None
        base_tree_sha = None
        ref_resp = httpx.get(f"{base_url}/git/ref/heads/{branch}", headers=self.headers, timeout=15)
        if ref_resp.status_code == 200:
            parent_sha = ref_resp.json()["object"]["sha"]
            commit_resp = httpx.get(f"{base_url}/git/commits/{parent_sha}", headers=self.headers, timeout=15)
            commit_resp.raise_for_status()
            base_tree_sha = commit_resp.json()["tree"]["sha"]

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
