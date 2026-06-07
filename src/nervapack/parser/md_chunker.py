import re
from typing import List, Dict

class MarkdownChunker:
    def __init__(self):
        # A simple regex for matching markdown headers
        self.header_regex = re.compile(r'^(#{1,6})\s+(.*)')

    def chunk_file(self, file_path: str) -> List[Dict[str, str]]:
        """
        Parses a Markdown file and returns chunks separated by headers.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return []

        chunks = []
        current_chunk = []
        current_header = "Document Root"
        
        for line in lines:
            match = self.header_regex.match(line)
            if match:
                # Save previous chunk
                if current_chunk:
                    content = "".join(current_chunk).strip()
                    if content:
                        chunks.append({
                            "header": current_header,
                            "content": content,
                            "file_path": file_path
                        })
                current_header = match.group(2).strip()
                current_chunk = [line]
            else:
                current_chunk.append(line)
                
        # Add the last chunk
        if current_chunk:
            content = "".join(current_chunk).strip()
            if content:
                chunks.append({
                    "header": current_header,
                    "content": content,
                    "file_path": file_path
                })
                
        return chunks
