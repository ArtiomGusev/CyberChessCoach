Local dev: using Fake LLM

You can run the embedded API locally without a real LLM by using the FakeLLM.
Set the `LLM_MODEL` env var to `fake` or `fake:<mode>` before running scripts.

Examples:
- PowerShell (temporary for session):
  $Env:LLM_MODEL = 'fake:mate_softening'
  python test_explain.py

- Command Prompt (temporary):
  set LLM_MODEL=fake:mate_softening && python test_explain.py

Supported fake modes (examples):
- `compliant` — returns a compliant explanation
- `forbidden_phrase` — returns text containing forbidden phrases
- `missing_data_violation` — returns text missing required missing-data acknowledgements
- `mate_softening` — returns text that softens mate claims

This is useful for iterating tests and debugging `run_mode_2` without depending on external LLM services.