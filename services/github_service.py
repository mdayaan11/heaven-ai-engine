"""GitHub Service — uses httpx only, no PyGithub dependency"""
from __future__ import annotations
import base64
import os
from typing import Any, Dict, List
import httpx
from models.schemas import GeneratedFile


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
            json={"name": safe_name, "private": private, "auto_init": True},
            timeout=30,
        )
        if r.status_code not in (201, 422):
            r.raise_for_status()
        data = r.json()
        # If already exists, fetch it
        if r.status_code == 422:
            r2 = httpx.get(f"{self.BASE}/repos/{self.username}/{safe_name}", headers=self.headers, timeout=15)
            data = r2.json()
        return {
            "html_url": data.get("html_url", ""),
            "clone_url": data.get("clone_url", ""),
            "full_name": data.get("full_name", f"{self.username}/{safe_name}"),
            "repo_name": safe_name,
        }

    def commit_files(self, repo_full_name: str, files: List[GeneratedFile], commit_message: str) -> None:
        for f in files:
            try:
                encoded = base64.b64encode(f.content.encode()).decode()
                # Check if file exists to get SHA
                sha = None
                r = httpx.get(
                    f"{self.BASE}/repos/{repo_full_name}/contents/{f.path}",
                    headers=self.headers, timeout=15,
                )
                if r.status_code == 200:
                    sha = r.json().get("sha")
                body: Dict[str, Any] = {
                    "message": commit_message,
                    "content": encoded,
                }
                if sha:
                    body["sha"] = sha
                httpx.put(
                    f"{self.BASE}/repos/{repo_full_name}/contents/{f.path}",
                    headers=self.headers,
                    json=body,
                    timeout=30,
                )
            except Exception:
                pass  # Skip individual file errors, continue
