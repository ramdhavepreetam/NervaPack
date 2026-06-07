import ollama
from typing import List, Dict
from nervapack.parser.ast_parser import ParsedEntity

class LLMSummarizer:
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def summarize_entity(self, entity: ParsedEntity) -> str:
        """
        Generate a quick summary for an AST node using Ollama.
        """
        prompt = f"Summarize the following code block (Type: {entity.type}, Name: {entity.name}):\n\n```\n{entity.content}\n```\n\nSummary:"
        try:
            response = ollama.chat(model=self.model_name, messages=[
                {"role": "system", "content": "You are a concise code summarizer. Output only a 1-3 sentence summary of what the code does."},
                {"role": "user", "content": prompt}
            ])
            return response['message']['content']
        except Exception as e:
            return f"Summary unavailable: {str(e)}"

    def bind_docs_to_ast(self, doc_chunk: str, ast_nodes: List[Dict[str, str]]) -> List[str]:
        """
        Takes a documentation chunk and a list of candidate AST nodes.
        Returns a list of node_ids that the documentation EXPLAINS or IMPLEMENTS.
        """
        candidates_str = "\n".join([f"ID: {n['node_id']} | Summary: {n['summary']}" for n in ast_nodes])
        prompt = (
            f"Given the following documentation chunk:\n\n{doc_chunk}\n\n"
            f"Which of the following code entities does it explain or implement? "
            f"Return a comma-separated list of IDs only, or 'None' if none match.\n\n"
            f"Candidates:\n{candidates_str}\n\nMatched IDs:"
        )
        try:
            response = ollama.chat(model=self.model_name, messages=[
                {"role": "system", "content": "You are an AI binding engine. Output ONLY a comma-separated list of IDs."},
                {"role": "user", "content": prompt}
            ])
            content = response['message']['content'].strip()
            if content.lower() == "none" or not content:
                return []
            return [i.strip() for i in content.split(",") if i.strip()]
        except Exception:
            return []
