# NervaPack Benchmarks

This directory contains the reproducible benchmark harness for comparing NervaPack's context retrieval against other tools like Aider and Repomix, specifically for token efficiency and recall on real-world issues.

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   npm install -g repomix
   ```

2. **Run Benchmarks**
   ```bash
   python run.py
   ```

## Methodology

We evaluate context generation tools on a subset of SWE-bench Lite instances. For each instance:
- The repository is checked out at the problem's base commit.
- A query is formulated from the issue's problem statement.
- Each tool generates context.
- We measure:
  - **Tokens**: The token count of the output context (using `tiktoken` with `gpt-4o`).
  - **Recall**: The percentage of modified files (ground truth) that are correctly captured in the returned context.

This provides a direct, head-to-head comparison demonstrating token savings without sacrificing the essential context required to solve the issue.
