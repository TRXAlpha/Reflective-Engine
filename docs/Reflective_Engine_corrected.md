# Reflective Engine: Corrected Technical Report

Christian Morogan

Corrected evidence review date: 2026-05-31

Repository reviewed: `TRXAlpha/Reflective-Engine`, commit `9eba1ad`

## Abstract

This corrected report describes the Reflective Engine repository as it exists in the reviewed snapshot. The project implements a local-first reflective prompting loop around an Ollama-compatible model, with streaming generation, self-scoring prompts, early stopping heuristics, and JSONL memory. The original PDF included formal benchmark tables and performance-equivalence claims that are not supported by the repository contents. Those unsupported claims are removed here and replaced with verifiable implementation facts, externally checked model facts, and a clear reproducibility status.

The current evidence supports describing the project as a research preview and prototype implementation. It does not yet support claims that Gemma 3 4B with reflection reaches 81.1 percent accuracy, improves reasoning by 27.32 percent, matches a 14.3B baseline, or achieves measured latency, energy, cache-hit, and error-reduction results.

## What Was Verified

- The repository contains a standalone Python reflective engine at `reflective_enginev2.py`.
- The backend contains a Flask server and a compact-memory version of the engine in `backend/reflective_engine.py`.
- The frontend is a React/Vite application under `frontend/`.
- The default local model identifier in the Python code is `gemma3:4b`.
- The code uses Ollama's local generate endpoint by default: `http://localhost:11434/api/generate`.
- Memory is persisted as JSONL. In the reviewed snapshot, `backend/ghost_memory.jsonl` contains 31 records.
- The repository now contains a minimal evaluation scaffold and `requirements.txt`, but it still does not contain benchmark datasets, formal result logs, or a publication-grade reproducible evaluation harness.

## Current Implementation

The standalone engine in `reflective_enginev2.py` provides:

- streaming calls to an Ollama-compatible endpoint;
- model-selected reflection loop count bounded by a user-provided maximum;
- model-based answer scoring on a 0-10 scale;
- a convergence token, `###DONE###`;
- repeated-answer detection using `difflib.SequenceMatcher`;
- early stopping when score improvement is small and the score is already high;
- JSONL memory writes to `ghost_memory.jsonl`;
- an optional finisher pass that formats the final answer.

The backend engine in `backend/reflective_engine.py` is a related compact-memory implementation. It stores shortened answer and reasoning snippets rather than full long traces. It also includes a user profile file path and memory summarization logic for prompt context.

The frontend package uses React 19, Vite 7, Tailwind CSS, Headless UI, and Heroicons.

## Corrected Evidence Status

The following table replaces the unsupported benchmark table in the original PDF.

| Claim area | Corrected status |
| --- | --- |
| Gemma 3 4B via Ollama | Supported. The code defaults to `gemma3:4b`, and Ollama publishes a `gemma3:4b` model. |
| Recursive reflection loop | Supported. Implemented in Python with review, improvement, scoring, and stopping logic. |
| Persistent memory | Partially supported. JSONL memory exists, but the implemented memory is simple record storage and summarization, not a validated semantic memory system. |
| TF-IDF/vector retrieval | Not supported by the reviewed code. The code uses string similarity and memory summaries, not TF-IDF vectors or a vector database. |
| 500 examples per task | Not supported. No benchmark dataset or result file was found. |
| 81.1 percent post-reflection accuracy | Not supported. No benchmark run or result log was found. |
| 27.32 percent reasoning improvement | Not supported. The number appears only in the PDF, not in reproducible artifacts. |
| 14.3B model equivalence | Not supported. The scaling calculation depends on unverified benchmark numbers. |
| 20 percent latency overhead | Not supported. No measurement logs or benchmark script were found. |
| Energy per query | Not supported. No power measurement methodology or logs were found. |
| arXiv preprint record | Not verified. Exact title/name searches did not locate a matching arXiv record during review. |

## External Facts Checked

Gemma 3 is a real Google open-model family. Google's developer announcement says Gemma 3 is available in 1B, 4B, 12B, and 27B sizes and can be used with tools including Ollama. Ollama's registry lists `gemma3:4b` with 4.3B parameters and Q4_K_M quantization.

Llama 2 13B is also real. Meta's Llama 2 family includes 7B, 13B, and 70B models, and the Hugging Face `meta-llama/Llama-2-13b` model card identifies the 13B pretrained model.

Relevant prior work cited by the original PDF is broadly real, including Chain-of-Thought prompting, Self-Consistency, Reflexion, Tree of Thoughts, Self-Refine, and Constitutional AI. This corrected report does not repeat unsupported comparative claims about those methods.

## Removed Or Downgraded Claims

The original PDF made several claims that should not be presented as established results without reproducible evidence:

- "average improvement of 27.32 percent in reasoning tasks";
- "small, locally run models can match or exceed models 3-4 times their size";
- "a 4B parameter model performs equivalently to a 14.3B baseline";
- "theoretical convergence guarantees" for textual model outputs;
- "statistical significance at p < 0.001";
- quantified cache hit rate, retrieval time, memory accuracy, storage growth, user feedback gains, latency, energy, and error-reduction rates.

These claims may be hypotheses or planned evaluation targets, but they are not verified by the current repository.

## Mathematical Corrections

The original PDF's QAIS calculation is internally inconsistent. Using the listed base accuracies and reflected accuracies:

- Base accuracies: 68.5, 73.0, 62.4, 58.0, 64.2, 55.8
- Reflected accuracies: 85.1, 88.6, 82.3, 76.5, 81.7, 72.4
- Error-room values: 31.5, 27.0, 37.6, 42.0, 35.8, 44.2
- Sum of error-room values: 218.1, not 186.1
- Recomputed QAIS from those table values: approximately 0.480, not 0.562

The average relative improvement from the six per-task relative improvements is approximately 27.73 percent. The relative improvement computed from averaged accuracies is approximately 27.32 percent. Both calculations can be legitimate if labeled correctly, but they should not be mixed as the same statistic.

## Reproducibility Gaps

The repository cannot currently reproduce the original PDF's empirical claims because it lacks:

- a benchmark dataset manifest;
- test prompts and expected answers;
- a publication-grade evaluator definition;
- random seed or decoding configuration;
- raw model outputs;
- hardware measurement scripts;
- latency and energy logs;
- statistical analysis scripts;
- dependency lockfile for Python.

## Recommended Evaluation Plan

To make future claims defensible, add an `evals/` directory with:

- `datasets/` or download scripts for public benchmarks;
- a JSONL schema containing prompt, category, expected answer, and grading rule;
- a baseline runner using the same model without reflection;
- a reflection runner using the same sampling parameters;
- a deterministic grader for exact-answer tasks and a documented rubric for open-ended tasks;
- saved raw outputs for every run;
- a metrics script that computes accuracy, relative gain, confidence intervals, and error categories;
- environment capture: model tag, quantization, Ollama version, CPU/GPU, RAM, OS, and commit hash.

Until that exists, the strongest accurate claim is:

"Reflective Engine is a local research-preview implementation of an iterative self-evaluation loop for Ollama-compatible language models. It includes prototype memory, self-scoring, convergence, and frontend/backend interfaces. Formal benchmark claims remain unverified."

## Sources

- Google Developers Blog, "Introducing Gemma 3: The Developer Guide", March 12, 2025: https://developers.googleblog.com/en/introducing-gemma3/
- Ollama model registry, `gemma3:4b`: https://registry.ollama.ai/library/gemma3%3A4b
- Hugging Face model card, `meta-llama/Llama-2-13b`: https://huggingface.co/meta-llama/Llama-2-13b
- Llama 2 paper, arXiv:2307.09288: https://arxiv.org/abs/2307.09288
- Reflective Engine repository snapshot reviewed locally: `TRXAlpha/Reflective-Engine`, commit `9eba1ad`
