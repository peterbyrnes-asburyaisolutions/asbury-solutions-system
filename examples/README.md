# Examples — non-secret configuration

Everything under this directory is a **template** or **illustrative** sample.
By design:

- No real credentials, tokens, or keys (every value is a placeholder).
- No live endpoints, hostnames, ports, or addresses.
- No client data or internal paths.

| File | What it shows |
|------|---------------|
| [`config/seat.example.yaml`](config/seat.example.yaml) | A single agent seat's profile shape: identity, model, tool allow-list, dispatch hints. |
| [`config/preset.example.yaml`](config/preset.example.yaml) | An agent preset (named execution mode) the kernel can invoke. |
| [`config/env.example`](config/env.example) | Environment template — copy to `.env`, fill locally, never commit. |
| [`swarm-dispatch.py`](swarm-dispatch.py) | Sanitized dispatch layer — seat resolution, per-step timeouts (explicit > env > step-type > base), parallel waves, fail-loud. Run `python3 swarm-dispatch.py --demo`. |
| [`evals/`](evals/) | Eval-harness example — golden datasets, regression suite, LLM-as-judge, fail-loud (how the org knows an agent works before shipping). |

To use: copy the file you need, replace the `<ANGLE_BRACKET>` placeholders with
your own values, and keep the real version out of version control (see the
root [`.gitignore`](../../.gitignore) and
[`docs/sanitization.md`](../../docs/sanitization.md)).
