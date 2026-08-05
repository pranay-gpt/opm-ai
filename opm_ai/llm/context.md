# opm_ai/llm - Provider-Abstracted LLM Client

Last updated: 2026-08-04. Status: complete (Stage 3 client + Stage B
extract_json + schedule-event guidance added to extraction prompt).

## Purpose
One client for Groq / OpenAI / NVIDIA NIM / offline, used by the builder
(parameter extraction), linter (summary), chat loop, and explainer.

## Files
| File | Purpose |
|------|---------|
| `client.py` | `LLMClient`: `.chat(messages) -> str\|None`, `.chat_with_tools(...)`, `.extract_json(prompt, schema) -> dict\|None`, `.available: bool` |
| `prompts/extract_model_spec.j2` | ModelSpec JSON-schema extraction prompt with few-shot examples. The `{{ schema }}` reference already includes ScheduleEvent because ModelSpec.schedule renders into the JSON schema. Few-shot examples explicitly demonstrate WAG and BUILDUP schedule emission so the LLM knows to populate `schedule` for shut-in / alternating-injection descriptions. (Added 2026-08-04, commit 7d0ff96.) |

## Invariants
- **Opt-in networking**: default `LLM_PROVIDER=offline`; only `.env` or the
  runtime settings API opts in. CI must stay offline. Never make a network
  call when the provider is offline - offline methods return None.
- **Never raises to callers**: chat/extract failures return None; callers
  (builder, linter) have deterministic offline fallbacks.
- `extract_json`: JSON mode where the provider supports it, else
  strict-prompt + parse + ONE repair retry; result validated by the caller
  (Pydantic) before use.
- **Constructed per use, never cached at import**: `LLMClient()` reads the
  settings singleton at `__init__`, which is how POST /api/settings runtime
  overrides take effect without restart (chat.py builds one per connection).
  Do not add a module-level client instance.
- Providers/models: groq = Llama-3.3-70B-versatile; nim via OpenAI-compatible
  endpoint; keys `GROQ_API_KEY`, `NVIDIA_NIM_API`, `OPENAI_API_KEY`.
- A selected provider without a key resolves to offline
  (`settings.active_llm_client`).

## Tests
`tests/unit/test_llm.py` (mocked providers: valid, invalid-schema, garbage
responses); `tests/unit/test_llm_extraction.py` (FakeClient returns canned
JSON, validates the rendered system_prompt contains schedule guidance
and WAG/BUILDUP few-shot examples - 2026-08-04); live-Groq paths are
verified manually, not in CI.
