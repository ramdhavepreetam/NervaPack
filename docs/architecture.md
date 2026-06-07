# NervaPack Architecture

The NervaPack architecture revolves around a CLI tool that interacts with a local graph and vector store.

## CLI Core

The `cli.py` file is the entry point for the NervaPack application. It contains commands such as `init`, `ingest`, `query`, `status`, and `sync`. These commands orchestrate the parser, the graph builder, the vector store, and the LLM summarizer.
