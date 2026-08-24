import re
from typing import List, Dict

class MarkdownChunker:
    def __init__(self):
        # A simple regex for matching markdown headers
        self.header_regex = re.compile(r'^(#{1,6})\s+(.*)')

    # Chunks shorter than this (chars) are merged into the next chunk instead
    # of being embedded as standalone vectors — avoids wasting ONNX calls on
    # single-line sections like "---" separators or one-word headers.
    MIN_CHUNK_CHARS = 120

    def chunk_file(self, file_path: str) -> List[Dict[str, str]]:
        """
        Parses a Markdown file and returns chunks separated by headers.
        Short chunks are merged forward to reduce the number of embeddings.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return []

        raw: List[Dict[str, str]] = []
        current_chunk: List[str] = []
        current_header = "Document Root"

        for line in lines:
            match = self.header_regex.match(line)
            if match:
                if current_chunk:
                    content = "".join(current_chunk).strip()
                    if content:
                        raw.append({
                            "header": current_header,
                            "content": content,
                            "file_path": file_path,
                        })
                current_header = match.group(2).strip()
                current_chunk = [line]
            else:
                current_chunk.append(line)

        if current_chunk:
            content = "".join(current_chunk).strip()
            if content:
                raw.append({
                    "header": current_header,
                    "content": content,
                    "file_path": file_path,
                })

        # Merge short chunks forward to reduce embedding count
        merged: List[Dict[str, str]] = []
        pending: Dict[str, str] | None = None
        for chunk in raw:
            if pending is None:
                pending = chunk
            elif len(pending["content"]) < self.MIN_CHUNK_CHARS:
                # Absorb pending into current chunk
                pending = {
                    "header": pending["header"],
                    "content": pending["content"] + "\n\n" + chunk["content"],
                    "file_path": file_path,
                }
            else:
                merged.append(pending)
                pending = chunk
        if pending is not None:
            merged.append(pending)

        return merged

_MD_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    ".nervapack",
    "dist", "build", "site", "target", "out", "output",
    ".eggs", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "htmlcov", "coverage",
    ".next", ".nuxt", ".svelte-kit", ".turbo",
    "bin", ".gradle",
    ".idea", ".vscode",
    "vendor", "vendors", "third_party", "extern", "_vendor",
    "lib", "libs",
    "rusted-host", "site-packages",
}


def scan_markdown_directory(directory: str) -> List[Dict[str, str]]:
    import os
    from nervapack.parser.ast_parser import _is_vendor_dir
    chunker = MarkdownChunker()
    all_chunks = []
    abs_root = os.path.abspath(directory)
    for root, dirs, files in os.walk(directory):
        dirs[:] = [
            d for d in dirs
            if d not in _MD_SKIP_DIRS
            and not d.endswith((".egg-info", ".dist-info"))
            and not _is_vendor_dir(os.path.join(root, d), d, abs_root)
        ]
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                all_chunks.extend(chunker.chunk_file(file_path))
    return all_chunks
