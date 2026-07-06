"""
Code hotspot analysis using git commit history.

Identifies files changed most frequently, which correlates with bug-prone
or high-churn areas of the codebase.
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class FileHotspot:
    """Change frequency data for a single file."""
    file_path: str
    change_count: int
    insertions: int
    deletions: int
    churn_score: float  # insertions + deletions — total lines touched


class HotspotAnalyzer:
    """Analyzes code hotspots from git history."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)

    def _run_git(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def is_git_repo(self) -> bool:
        return bool(self._run_git(["rev-parse", "--git-dir"]))

    def get_hotspots(
        self,
        limit: int = 20,
        since: Optional[str] = None,
        extensions: Optional[List[str]] = None,
    ) -> List[FileHotspot]:
        """
        Return files ranked by change frequency.

        Args:
            limit: Max files to return.
            since: Git date expression e.g. "6 months ago", "2024-01-01".
            extensions: Filter to specific file extensions e.g. [".py", ".ts"].
        """
        args = ["log", "--numstat", "--pretty=format:"]
        if since:
            args += [f"--since={since}"]

        raw = self._run_git(args)
        if not raw:
            return []

        counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"changes": 0, "ins": 0, "del": 0})

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            ins_str, del_str, path = parts
            # Binary files show "-" — skip them
            if ins_str == "-" or del_str == "-":
                continue
            try:
                ins = int(ins_str)
                dels = int(del_str)
            except ValueError:
                continue

            if extensions:
                if not any(path.endswith(ext) for ext in extensions):
                    continue

            counts[path]["changes"] += 1
            counts[path]["ins"] += ins
            counts[path]["del"] += dels

        hotspots = [
            FileHotspot(
                file_path=path,
                change_count=data["changes"],
                insertions=data["ins"],
                deletions=data["del"],
                churn_score=float(data["ins"] + data["del"]),
            )
            for path, data in counts.items()
        ]

        hotspots.sort(key=lambda h: h.change_count, reverse=True)
        return hotspots[:limit]

    def get_hotspot_summary(
        self,
        limit: int = 20,
        since: Optional[str] = None,
        extensions: Optional[List[str]] = None,
    ) -> Dict:
        """Return hotspot data as a plain dict for serialisation."""
        hotspots = self.get_hotspots(limit=limit, since=since, extensions=extensions)
        return {
            "hotspots": [
                {
                    "file_path": h.file_path,
                    "change_count": h.change_count,
                    "insertions": h.insertions,
                    "deletions": h.deletions,
                    "churn_score": h.churn_score,
                }
                for h in hotspots
            ],
            "total_files_analyzed": len(hotspots),
            "since": since,
        }
