#!/bin/bash

# Define the models array
models=(
  "gemma3:4b"
  # Replace these with exact names from `ollama list`, for example:
   "gemma3:270m",
   "gemma4:e4b",
   "gemma4:e2b"
)

# Run agentic tasks
# Note: Changed .ps1 to .sh assuming you have a shell version of the script
./evals/run_models.sh \
  -Models "${models[@]}" \
  -Tasks "evals/agentic_tasks.jsonl" \
  -Output "evals/results_agentic_multi.jsonl" \
  -MaxLoops 3

# Run broad tasks
./evals/run_models.sh \
  -Models "${models[@]}" \
  -Tasks "evals/broad_tasks.jsonl" \
  -Output "evals/results_broad_multi.jsonl" \
  -MaxLoops 3