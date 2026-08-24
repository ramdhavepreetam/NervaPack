import argparse
import subprocess
import os
import shutil
import json
import pandas as pd
from datasets import load_dataset
from tqdm import tqdm
import tiktoken
import tempfile
import re

TARGET_REPOS = ["django/django", "psf/requests", "pallets/flask", "sphinx-doc/sphinx", "pytest-dev/pytest"]

def count_tokens(text: str, model="gpt-4o") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        return 0

def extract_modified_files(patch: str):
    files = set()
    for line in patch.split('\n'):
        if line.startswith('diff --git '):
            parts = line.split(' b/')
            if len(parts) == 2:
                files.add(parts[1].strip())
    return files

def get_nervapack_context(temp_dir, query_text):
    script_path = os.path.join(temp_dir, "_dump_context.py")
    with open(script_path, "w") as f:
        f.write(f"""
import sys
import os
from nervapack.graph.builder import GraphBuilder
from nervapack.graph.vector_store import VectorStore
from nervapack.graph.retrieval import GraphRetriever

def main():
    gb = GraphBuilder(repo_path='.')
    graph = gb.load()
    if not graph:
        sys.exit(1)
        
    vs = VectorStore(db_path='.nervapack/chroma_db')
    results = vs.search("{query_text}", n_results=3)
    
    start_nodes = []
    if results and 'metadatas' in results and results['metadatas']:
        for meta_list in results['metadatas']:
            if not meta_list: continue
            for meta in meta_list:
                if 'node_id' in meta:
                    start_nodes.append(meta['node_id'])
                elif 'file_path' in meta:
                    start_nodes.append(meta['file_path'])
    
    retriever = GraphRetriever(graph)
    subgraph = retriever.retrieve_context(start_nodes, max_hops=2)
    
    context_text = ""
    for n, data in subgraph.nodes(data=True):
        if data.get("type") == "file":
            context_text += data.get("content", "") + "\\n"
        elif data.get("type") == "function" or data.get("type") == "class":
            context_text += data.get("content", "") + "\\n"
            
    print(context_text)

if __name__ == '__main__':
    main()
""")
    subprocess.run(["nervapack", "ingest", "."], cwd=temp_dir, capture_output=True)
    res = subprocess.run(["python", "_dump_context.py"], cwd=temp_dir, capture_output=True, text=True)
    return res.stdout

def get_aider_context(temp_dir):
    try:
        res = subprocess.run(["aider", "--dry-run", "--message", "generate repomap"], cwd=temp_dir, capture_output=True, text=True)
        return res.stdout
    except Exception:
        return ""

def get_repomix_context(temp_dir):
    try:
        subprocess.run(["npx", "repomix"], cwd=temp_dir, capture_output=True)
        output_file = os.path.join(temp_dir, "repomix-output.txt")
        if os.path.exists(output_file):
            with open(output_file, "r") as f:
                return f.read()
    except Exception:
        return ""
    return ""

def calculate_recall(context_text, ground_truth_files):
    if not ground_truth_files: return 0.0
    found = sum(1 for f in ground_truth_files if os.path.basename(f) in context_text or f in context_text)
    return found / len(ground_truth_files)

def run_benchmark():
    print("Loading SWE-bench Lite...")
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    instances = []
    seen_repos = set()
    for item in ds:
        repo = item["repo"]
        if repo in TARGET_REPOS and repo not in seen_repos:
            instances.append(item)
            seen_repos.add(repo)
            if len(seen_repos) == len(TARGET_REPOS):
                break
                
    results = []
    
    for item in tqdm(instances, desc="Benchmarking Repos"):
        repo = item["repo"]
        instance_id = item["instance_id"]
        base_commit = item["base_commit"]
        problem_statement = item["problem_statement"]
        patch = item["patch"]
        
        ground_truth_files = extract_modified_files(patch)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"\\nCloning {repo} @ {base_commit}...")
            subprocess.run(["git", "clone", f"https://github.com/{repo}.git", "."], cwd=temp_dir, capture_output=True)
            subprocess.run(["git", "checkout", base_commit], cwd=temp_dir, capture_output=True)
            
            # 1. NervaPack
            np_ctx = get_nervapack_context(temp_dir, problem_statement)
            np_tokens = count_tokens(np_ctx)
            np_recall = calculate_recall(np_ctx, ground_truth_files)
            
            # 2. Aider
            aider_ctx = get_aider_context(temp_dir)
            aider_tokens = count_tokens(aider_ctx) if aider_ctx else 0
            aider_recall = calculate_recall(aider_ctx, ground_truth_files) if aider_ctx else 0.0
            
            # 3. Repomix
            repomix_ctx = get_repomix_context(temp_dir)
            repomix_tokens = count_tokens(repomix_ctx) if repomix_ctx else 0
            repomix_recall = calculate_recall(repomix_ctx, ground_truth_files) if repomix_ctx else 0.0
            
            results.append({"repo": repo, "instance_id": instance_id, "tool": "NervaPack", "tokens": np_tokens, "recall": np_recall})
            results.append({"repo": repo, "instance_id": instance_id, "tool": "Aider", "tokens": aider_tokens, "recall": aider_recall})
            results.append({"repo": repo, "instance_id": instance_id, "tool": "Repomix", "tokens": repomix_tokens, "recall": repomix_recall})
            
    df = pd.DataFrame(results)
    df.to_csv("results.csv", index=False)
    print("\\nResults saved to results.csv")
    print(df)

if __name__ == "__main__":
    run_benchmark()
