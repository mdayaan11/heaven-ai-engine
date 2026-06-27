"""
Heaven AI — Vercel & Render Deployment Service
Programmatically creates projects and triggers production deployments.
"""
from __future__ import annotations
import time
from typing import Dict, Optional
import httpx


class VercelService:
    BASE_URL = "https://api.vercel.com"

    def __init__(self, token: str, team_id: Optional[str] = None):
        self.token = token
        self.team_id = team_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _params(self, extra: Optional[Dict] = None) -> Dict:
        """Build query params, including teamId if set."""
        params = {}
        if self.team_id:
            params["teamId"] = self.team_id
        if extra:
            params.update(extra)
        return params

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        url = f"{self.BASE_URL}{path}"
        with httpx.Client(timeout=60) as client:
            response = client.request(
                method, url, headers=self.headers,
                params=self._params(kwargs.pop("params", None)),
                **kwargs
            )
            if response.status_code not in [200, 201, 202]:
                raise RuntimeError(
                    f"Vercel API error {response.status_code}: {response.text[:500]}"
                )
            return response.json()

    def create_project(
        self,
        project_name: str,
        github_repo: str,
        framework: str = "nextjs",
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """
        Create a new Vercel project linked to a GitHub repo.

        Args:
            project_name: Unique project name
            github_repo: Full repo name e.g. 'username/repo-name'
            framework: 'nextjs' | 'react' | 'vite' | 'other'
            env_vars: Dict of environment variable names → values

        Returns:
            {"project_id": ..., "project_url": ...}
        """
        safe_name = project_name.lower().replace(" ", "-")[:52]
        payload: Dict = {
            "name": safe_name,
            "framework": framework,
            "gitRepository": {
                "type": "github",
                "repo": github_repo,
            },
            "publicSource": False,
        }

        if env_vars:
            payload["environmentVariables"] = [
                {"key": k, "value": v, "target": ["production", "preview", "development"]}
                for k, v in env_vars.items()
            ]

        result = self._request("POST", "/v10/projects", json=payload)
        return {
            "project_id": result["id"],
            "project_name": result["name"],
            "project_url": f"https://{result['name']}.vercel.app",
        }

    def trigger_deployment(self, project_id: str, github_repo: str, branch: str = "main") -> Dict:
        """
        Trigger a new deployment from the latest GitHub commit.

        Returns:
            {"deploy_id": ..., "deploy_url": ..., "state": ...}
        """
        payload = {
            "name": project_id,
            "gitSource": {
                "type": "github",
                "ref": branch,
                "repoId": github_repo,
            },
            "target": "production",
        }
        result = self._request("POST", "/v13/deployments", json=payload)
        deploy_url = f"https://{result.get('url', project_id + '.vercel.app')}"
        return {
            "deploy_id": result["id"],
            "deploy_url": deploy_url,
            "state": result.get("readyState", "QUEUED"),
            "inspect_url": f"https://vercel.com/dashboard",
        }

    def wait_for_deployment(
        self,
        deploy_id: str,
        on_log: Optional[callable] = None,
        max_wait_seconds: int = 300,
    ) -> Dict:
        """
        Poll deployment status until ready or failed.

        Returns final deployment status dict.
        """
        start = time.time()
        poll_interval = 8

        while time.time() - start < max_wait_seconds:
            result = self._request("GET", f"/v13/deployments/{deploy_id}")
            state = result.get("readyState", "QUEUED")

            if on_log:
                on_log(f"[SYS_LOG: DEPLOYING_PROD] Deployment status: {state}...")

            if state == "READY":
                production_url = f"https://{result.get('url', '')}"
                return {"state": "READY", "production_url": production_url, "deploy_id": deploy_id}
            elif state in ("ERROR", "CANCELED"):
                raise RuntimeError(f"Vercel deployment failed with state: {state}")

            time.sleep(poll_interval)

        raise RuntimeError(f"Vercel deployment timed out after {max_wait_seconds}s")

    def set_env_vars(self, project_id: str, env_vars: Dict[str, str]) -> None:
        """Set environment variables on an existing project."""
        for key, value in env_vars.items():
            try:
                self._request(
                    "POST",
                    f"/v10/projects/{project_id}/env",
                    json={
                        "key": key,
                        "value": value,
                        "target": ["production", "preview", "development"],
                        "type": "encrypted",
                    },
                )
            except RuntimeError:
                pass  # Variable may already exist; non-fatal


class RenderService:
    """Render.com deployment for full-stack (backend) apps."""
    BASE_URL = "https://api.render.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        url = f"{self.BASE_URL}{path}"
        with httpx.Client(timeout=60) as client:
            response = client.request(method, url, headers=self.headers, **kwargs)
            if response.status_code not in [200, 201, 202]:
                raise RuntimeError(
                    f"Render API error {response.status_code}: {response.text[:500]}"
                )
            return response.json()

    def create_web_service(
        self,
        service_name: str,
        github_repo: str,
        branch: str = "main",
        runtime: str = "node",
        build_command: str = "npm install && npm run build",
        start_command: str = "npm start",
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """Create a Render web service from a GitHub repo."""
        safe_name = service_name.lower().replace(" ", "-")[:63]
        payload = {
            "type": "web_service",
            "name": safe_name,
            "repo": f"https://github.com/{github_repo}",
            "branch": branch,
            "runtime": runtime,
            "buildCommand": build_command,
            "startCommand": start_command,
            "envVars": [
                {"key": k, "value": v}
                for k, v in (env_vars or {}).items()
            ],
            "plan": "free",
            "region": "oregon",
            "autoDeploy": "yes",
        }
        result = self._request("POST", "/services", json=payload)
        service = result.get("service", result)
        return {
            "service_id": service["id"],
            "service_name": service["name"],
            "production_url": f"https://{service['name']}.onrender.com",
            "dashboard_url": f"https://dashboard.render.com/web/{service['id']}",
        }

    def trigger_deploy(self, service_id: str) -> Dict:
        """Trigger a manual deploy on a Render service."""
        result = self._request("POST", f"/services/{service_id}/deploys", json={})
        return {
            "deploy_id": result.get("id", ""),
            "status": result.get("status", "created"),
        }
