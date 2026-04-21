# premortem

LLM-driven failure analysis for distributed system designs.

Describe your architecture as a YAML topology, point the tool at a failure ("broker is slow", "sanctions service returns 500 for 80% of requests"), and get back a structured timeline, ranked risks, and mitigation suggestions — grounded in the specifics of *your* design, not a menu of canned chaos scenarios.

This is v0.1: qualitative-only, CLI-only, one LLM call per what-if. No simulation engine yet.

## Why this exists

Architects mentally simulate failure modes all the time, but sloppily — bounded by whatever happens to be top of mind that day. Existing "system design simulator" tools (paperdraw.dev, syde.cc) ship with a fixed menu of chaos scenarios and require you to drag-and-drop your architecture. `premortem` inverts that: you describe the architecture in YAML (or, eventually, plain English), and an LLM derives the interesting failure modes from the specifics of the design.

## Setup

You need **Python 3.11 or later**. Pick one of the install paths below.

### Option A — `uv` (preferred if available)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/YOUR-USER/premortem
cd premortem
uv sync
export ANTHROPIC_API_KEY=sk-ant-...
```

### Option B — `pip` + venv (works on locked-down enterprise workstations)

```bash
git clone https://github.com/YOUR-USER/premortem
cd premortem

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -e .                  # installs the 'premortem' console script

export ANTHROPIC_API_KEY=sk-ant-...
```

### Enterprise workstation gotchas

A few things that commonly bite on corporate-managed machines:

- **Proxy**: if `pip install` hangs or fails SSL, you likely need `HTTPS_PROXY` set or `--index-url` pointed at an internal mirror. Check with IT for the internal PyPI mirror URL (often Artifactory or Nexus).
- **Corporate TLS inspection**: if you see `SSL: CERTIFICATE_VERIFY_FAILED`, your firm is probably MITM-ing TLS with an internal root CA. Fix: `pip config set global.cert /path/to/corp-ca-bundle.pem` or set `REQUESTS_CA_BUNDLE` env var. The Anthropic SDK uses `httpx` which respects `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE`.
- **Python version**: enterprise machines often default to 3.9 or earlier. Check with `python3 --version`. If it's older than 3.11, you'll need to install a newer Python (pyenv, conda, or ask IT).
- **Outbound to api.anthropic.com**: the tool calls `https://api.anthropic.com`. If this is blocked by egress rules, you'll need it added to the allow-list. This is the single most common reason this won't work on a locked-down box — check before you invest time in the setup.
- **If you can't use any of this**: run it on a personal machine with a scrubbed/anonymized version of your topology YAML. The analysis doesn't need real system names to be useful.

### Running without install (fastest way to just try it)

If you just want to try the tool once without committing to an install:

```bash
cd premortem
pip install --user -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
PYTHONPATH=. python -m premortem.cli components examples/payment_contingency.yaml
PYTHONPATH=. python -m premortem.cli run examples/payment_contingency.yaml \
    --target sanctions-check --mode "returns 500 for 80% of requests"
```

## Try it on the included example

The `examples/payment_contingency.yaml` topology models a payment orchestration system with external risk/sanctions/funds checks and a rule-driven contingency engine that substitutes decisions when those externals fail.

The commands below assume you've activated your venv (pip path) or are prefixing with `uv run` (uv path). Both work identically.

First, see what components are in it:

```bash
premortem components examples/payment_contingency.yaml
```

Now run some premortems:

```bash
# What happens when the sanctions check goes slow?
premortem run examples/payment_contingency.yaml \
  --target sanctions-check \
  --mode "returns 500 for 80% of requests for 2 minutes"

# What if the contingency engine itself is the problem?
premortem run examples/payment_contingency.yaml \
  --target contingency-engine \
  --mode "latency spikes to 3 seconds"

# What if the reverify queue's consumer falls behind?
premortem run examples/payment_contingency.yaml \
  --target reverify-consumer \
  --mode "consumer down, lag accumulating for 4 hours"
```

Each run takes ~15-30 seconds and returns a timeline, ranked risks, and specific mitigation suggestions that name the pattern (outbox, DLQ, circuit breaker, etc.) and spell out the tradeoffs.

## Writing your own topology

Copy `examples/payment_contingency.yaml` and edit. The schema is intentionally small:

- **components**: nodes. Give each an `id`, `kind` (service, message_broker, database, queue, etc.), `description`, and optionally `sla_p99_ms` and freeform `notes`.
- **edges**: directed interactions. `pattern` is `sync_request`, `async_produce`, `async_consume`, `polling`, or `webhook`.
- **constraints**: freeform list — SLAs, regulatory requirements, invariants. The LLM reads these and factors them into analysis.

The `notes` fields matter. "Historically the least reliable of the three externals" or "stateful — failed requests may leave dangling holds" is the kind of context that turns a generic analysis into a useful one.

## What's NOT here yet (roadmap)

- **Quantitative simulation** — no lag curves, no latency percentiles. Pure narrative.
- **Redesign loop** — mitigations are suggested but not applied back to the topology for re-simulation.
- **Conversational elicitation** — you write YAML, not chat.
- **Visualization** — CLI output only.
- **Pattern library** — the LLM reasons from its training; no curated pattern corpus yet.

These are on the roadmap in roughly that order.

## Development

With `uv`:
```bash
uv run pytest
uv run ruff check --fix
uv run ruff format
uv run mypy premortem
```

With pip (in activated venv, after `pip install -r requirements-dev.txt`):
```bash
pytest
ruff check --fix
ruff format
mypy premortem
```
