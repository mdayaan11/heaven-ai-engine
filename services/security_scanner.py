"""Security Scanner — strips hardcoded secrets from generated files"""
from __future__ import annotations
import re
from typing import List, Tuple
from models.schemas import GeneratedFile

SECRET_PATTERNS = [
    r'sk-ant-[A-Za-z0-9\-_]{20,}',
    r'ghp_[A-Za-z0-9]{36}',
    r'AIzaSy[A-Za-z0-9\-_]{33}',
    r'sk-[A-Za-z0-9]{48}',
    r'(?i)(api_key|secret|password|token)\s*=\s*["\'][^"\']{8,}["\']',
]


class SecurityScannerService:
    def scan_and_sanitize(
        self, files: List[GeneratedFile]
    ) -> Tuple[List[GeneratedFile], List[str], List[str]]:
        secrets_found: List[str] = []
        cleaned: List[GeneratedFile] = []
        for f in files:
            content = f.content
            for pat in SECRET_PATTERNS:
                matches = re.findall(pat, content)
                if matches:
                    secrets_found.extend(matches)
                    content = re.sub(pat, "process.env.SECRET_REDACTED", content)
            cleaned.append(GeneratedFile(path=f.path, content=content, language=f.language))
        return cleaned, list(set(secrets_found)), []
