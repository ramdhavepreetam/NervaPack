# NervaPack Performance Benchmarks

> **Last Updated:** 2026-07-06
> **Version Tested:** 0.4.1

---

## Executive Summary

NervaPack achieves **significantly lower token counts** while maintaining high retrieval recall on real-world coding issues from the SWE-bench Lite dataset. 

| Metric | NervaPack | Aider (Repo Map) | Repomix (Full Pack) |
|--------|-----------|-------------------|----------------------|
| **Average Tokens** | 2300 | 10300 | 88000 |
| **Average Recall@k** | 96% | 94% | 100% |
| **Token Reduction (vs Repomix)** | **97.4%** | 88.3% | Baseline |

*Token counts refer to the context size provided to the LLM. Recall@k refers to whether the ground-truth modified files required to solve the issue were successfully included in the context.*

---

## Head-to-Head Comparison

We evaluated NervaPack against standard context generation tools on a sample of 5 public repositories from the SWE-bench Lite dataset.

- **NervaPack**: Graph-based 2-hop retrieval.
- **Aider**: Default AST-based repo map generated via dry-run.
- **Repomix**: Bundles the entire repository contents.

NervaPack achieves **4.5x fewer tokens** than an Aider repo map, and **38.3x fewer tokens** than a full Repomix bundle, while maintaining competitive recall (missing ground-truth files less than 5% of the time on average).

For full methodology and raw data, see our [Methodology](METHODOLOGY.md) page.
