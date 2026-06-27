"""
Heaven AI — GitHub API Service
Creates private repos, commits all generated files, and triggers GitHub Actions.
"""
from __future__ import annotations
import base64
import time
from typing import Dict, List, Optional
import httpx
from models.schemas import GeneratedFile


class GitHubService:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, username: str):
        self.token = token
        self.username = username
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        url = f"{self.BASE_URL}{path}"
        with httpx.Client(timeout=30) as client:
            response = client.request(method, url, headers=self.headers, **kwargs)
            if response.status_code not in [200, 201, 204]:
                raise RuntimeError(
                    f"GitHub API error {response.status_code}: {response.text[:500]}"
                )
            if response.status_code == 204:
                return {}
            return response.json()

    def create_repo(self, repo_name: str, description: str = "", private: bool = True) -> Dict:
        """Create a new private GitHub repository."""
        # Sanitize repo name
        safe_name = repo_name.lower().replace(" ", "-").replace("_", "-")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "-")[:100]
        safe_name = f"heaven-ai-{safe_name}-{int(time.time()) % 10000}"

        payload = {
            "name": safe_name,
            "description": description or f"Built by Heaven AI Engine — {repo_name}",
            "private": private,
            "auto_init": False,
            "has_issues": True,
            "has_projects": False,
            "has_wiki": False,
        }
        result = self._request("POST", "/user/repos", json=payload)
        return {
            "repo_name": result["name"],
            "full_name": result["full_name"],
            "html_url": result["html_url"],
            "clone_url": result["clone_url"],
            "default_branch": result.get("default_branch", "main"),
        }

    def commit_files(
        self,
        repo_full_name: str,
        files: List[GeneratedFile],
        commit_message: str = "🚀 Initial commit — built by Heaven AI Engine",
        branch: str = "main",
    ) -> str:
        """
        Commit all generated files to the repository in a single operation.
        Uses the Git Data API for atomic multi-file commits.
        """
        # 1. Get or create initial commit to establish HEAD
        try:
            ref_data = self._request("GET", f"/repos/{repo_full_name}/git/refs/heads/{branch}")
            base_sha = ref_data["object"]["sha"]
        except RuntimeError:
            # Repo is empty — create an initial commit with README
            base_sha = self._create_initial_commit(repo_full_name, branch)

        # 2. Get base tree SHA
        commit_data = self._request("GET", f"/repos/{repo_full_name}/git/commits/{base_sha}")
        base_tree_sha = commit_data["tree"]["sha"]

        # 3. Create blobs for each file
        tree_items = []
        for file in files:
            blob_data = self._request(
                "POST",
                f"/repos/{repo_full_name}/git/blobs",
                json={
                    "content": base64.b64encode(file.content.encode("utf-8")).decode("ascii"),
                    "encoding": "base64",
                },
            )
            tree_items.append({
                "path": file.path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_data["sha"],
            })

        # 4. Create tree
        tree_data = self._request(
            "POST",
            f"/repos/{repo_full_name}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree_items},
        )

        # 5. Create commit
        new_commit = self._request(
            "POST",
            f"/repos/{repo_full_name}/git/commits",
            json={
                "message": commit_message,
                "tree": tree_data["sha"],
                "parents": [base_sha],
                "author": {
                    "name": "Heaven AI Engine",
                    "email": "engine@heaven.ai",
                },
            },
        )

        # 6. Update HEAD ref
        self._request(
            "PATCH",
            f"/repos/{repo_full_name}/git/refs/heads/{branch}",
            json={"sha": new_commit["sha"], "force": False},
        )

        return new_commit["sha"]

    def _create_initial_commit(self, repo_full_name: str, branch: str) -> str:
        """Create a root commit with a README for an empty repo."""
        readme_content = base64.b64encode(
            b"# Heaven AI Engine\n\nThis project was built by Heaven AI Engine.\n"
        ).decode("ascii")

        blob = self._request(
            "POST",
            f"/repos/{repo_full_name}/git/blobs",
            json={"content": readme_content, "encoding": "base64"},
        )
        tree = self._request(
            "POST",
            f"/repos/{repo_full_name}/git/trees",
            json={"tree": [{"path": "README.md", "mode": "100644", "type": "blob", "sha": blob["sha"]}]},
        )
        commit = self._request(
            "POST",
            f"/repos/{repo_full_name}/git/commits",
            json={
                "message": "Initial commit",
                "tree": tree["sha"],
                "parents": [],
                "author": {"name": "Heaven AI Engine", "email": "engine@heaven.ai"},
            },
        )
        # Create branch ref
        self._request(
            "POST",
            f"/repos/{repo_full_name}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": commit["sha"]},
        )
        return commit["sha"]

    def set_repo_secret(self, repo_full_name: str, secret_name: str, secret_value: str) -> None:
        """Set a GitHub Actions secret on the repo (requires nacl for encryption in prod)."""
        # Simplified — in production use PyNaCl to encrypt with repo public key
        # This is a placeholder to show the integration point
        pass

    def get_repo_url(self, repo_full_name: str) -> str:
        data = self._request("GET", f"/repos/{repo_full_name}")
        return data["html_url"]
