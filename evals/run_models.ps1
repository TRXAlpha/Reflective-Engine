param(
  [string[]]$Models = @("gemma3:4b"),
  [string]$Tasks = "evals/broad_tasks.jsonl",
  [string]$Output = "evals/results_multi.jsonl",
  [int]$MaxLoops = 3,
  [string]$OllamaUrl = "http://localhost:11434/api/generate"
)

Remove-Item $Output -ErrorAction SilentlyContinue

foreach ($Model in $Models) {
  Write-Host "Running model: $Model"
  python evals/run_eval.py `
    --tasks $Tasks `
    --output $Output `
    --append `
    --max-loops $MaxLoops `
    --model $Model `
    --ollama-url $OllamaUrl
}

python evals/analyze_results.py --input $Output --output "evals/summary_multi.json"
