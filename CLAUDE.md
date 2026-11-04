# Sherlog — working rules

## Project
CLI tool: an LLM agent (LangGraph) investigates incidents in a simulated system (3 FastAPI services in Docker Compose + Postgres/Redis/Elasticsearch), reads code, proposes fixes. Portfolio project for backend AI engineer roles; the user is also learning the stack.

## How to work
- Explain design choices briefly; keep each step small enough to read as one diff. One concept per commit.
- Every step has a done-condition the user can run and a pytest test. Say how to run both.
- Ask before adding any dependency, framework or service outside: Python 3.12, FastAPI, Postgres, Redis, Elasticsearch, LangGraph, Docker Compose, Typer, pytest. LangChain only where it clearly saves work. No web UI in v1.
- Commit or push only when asked.

## LLM layer
- Only `src/sherlog/llm/` may import a provider SDK or know a provider. Everything else calls `complete(messages, tools)`.
- One internal tool format; adapters convert.
- Config: `sherlog.toml` (committed, provider-neutral defaults) overridden by `sherlog.local.toml` (git-ignored), plus `.env` for keys (git-ignored; keep `.env.example` current). `--model` flag overrides both.
- Defaults must work with a plain API key. No Portkey-specific headers or URLs in committed files. Portkey is a user-side override via `base_url` in `sherlog.local.toml`; no Portkey SDK.
- The private gateway hostname must never appear in committed files (a test enforces this).
- Cache keys include provider + model + base_url host + prompt hash.
- Log tokens, cost, latency per call and per investigation ourselves. Unknown pricing => cost `None`, never guessed.
- Hard cap on prompt size; truncate diffs/files/log results.

## Agent safety
- Tools are read-only. Code tools run only fixed git read commands as argv lists (`shell=False`); validate refs/patterns; no arbitrary shell.
- Path allowlist inside service repos: no `.env`, no `..`, no symlink escapes, no `.git` internals.
- Size caps on diffs/files; redact secret-looking strings before content reaches the LLM.
- Actions only from a fixed allowlist (rollback, restart). Patches are never auto-applied; every change requires explicit CLI approval (LangGraph interrupt).

## Eval integrity (hard rules)
- Never fabricate or hardcode eval numbers. Reported results must come from real runs; test fixtures are labelled synthetic.
- Incident ground truth is written by the user. Do not generate or edit `ground_truth.yaml`.
- Eval output records the single pinned model, provider, judge model, config hash and Sherlog commit.
- Keep scope tight. Cut stretch goals (patch verification) before cutting the eval.

## Secrets
- Never commit API keys. Before commits, check `.gitignore` covers `.env`, `sherlog.local.toml`, `.sherlog/`, `runs/`, and scan staged diffs for key patterns. If a key may have been committed, tell the user immediately and recommend rotation.

## Commands
- `uv run pytest` (unit tests, no Docker) · `uv run pytest -m integration` (needs `docker compose up -d`)
- `uv run sherlog --version` (more commands arrive per slice: init, break, investigate, eval, replay, doctor)
