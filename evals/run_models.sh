#!/bin/bash

# This script is intended to be run from the evals/ directory.

# Define the list of models to test.
# Replace these with exact names from `ollama list`, for example:
MODELS_TO_TEST=(
  "gemma3:4b"
  "gemma3:270m"
  "gemma4:e4b"
  "gemma4:e2b"
)

# Define the list of task files to test against.
TASKS_TO_TEST=(
  "sample_tasks.jsonl"
  "broad_tasks.jsonl"
  "agentic_tasks.jsonl"
)

# Define the output file for all evaluation results
OUTPUT_FILE="evals/results.jsonl"

# Clear the output file before starting new evaluations to ensure a clean run.
# This prevents results from previous runs from interfering with the current analysis.
> "$OUTPUT_FILE"
echo "Cleared previous evaluation results from $OUTPUT_FILE"
echo ""

# Loop through each model and then through each task file
for model_name in "${MODELS_TO_TEST[@]}"; do
    for task_file in "${TASKS_TO_TEST[@]}"; do
        echo "Running model: $model_name on task: $task_file"

        # Calling run_eval.py for the current model and task.
        # We specify the output file where results will be appended.
        # The `--output` flag ensures the results are saved to the specified file.
        python run_eval.py --model "$model_name" --tasks "$task_file" --output "$OUTPUT_FILE"

        echo "Finished running evaluation for $model_name on $task_file."
        echo "" # Add a blank line for clarity between runs
    done
done

echo "All models and tasks evaluated. Starting analysis..."
echo ""

# Call analyze_results.py to process all aggregated results.
# It will read from the OUTPUT_FILE which now contains results from all models and tasks.
# We pass the input file to the analyze_results.py script.
python analyze_results.py --input "$OUTPUT_FILE"

echo "Analysis complete."