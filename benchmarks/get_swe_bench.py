from datasets import load_dataset
ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

repos = {}
for item in ds:
    repo = item["repo"]
    if repo not in repos:
        repos[repo] = []
    repos[repo].append(item)

for repo, items in repos.items():
    print(f"{repo}: {len(items)}")
