# Poll (Multi-Provider Q&A) - Flow

This workflow simulates “ask the room”:
- **You** = Driver (the provider that invoked `/poll`; asks the question, synthesizes)
- **Other mounted providers** = Respondents (answer independently; no code changes)

## Inputs

From `$ARGUMENTS`:
- `question`: the question to broadcast
- Optional: `respondents=<comma-separated providers>` (default: all mounted except `{self}`)
- Optional: `timeout_s=<seconds>` (default: `60`)
- Optional: `format=consensus|list|table` (default: `consensus`)

## Step 0: Detect which providers can respond

Run:
```bash
ccb-mounted
```

If `ccb-mounted` fails (non-zero) or returns invalid output, stop and ask the user to fix mounting/daemons first.

Parse `mounted[]` and define:
- For this skill, `{self} = codex`
- `respondents = mounted - {self}`
- If `respondents=...` is provided, use `respondents = (mounted ∩ requested_respondents) - {self}`

If `respondents` is empty, proceed solo: answer the question yourself and clearly label it as a solo response.

Generate a fresh correlation id you can match against later:
- `POLL_ID = <timestamp + random>` (example: `2026-01-30T12:34:56Z-8f3a`)
- `POLL_DRIVER = {self}` (the provider that invoked `/poll`)

## Step 1: Clarify if needed

If `question` is empty or missing, ask the user to provide a question before proceeding.

If the question is ambiguous, ask the user 1-2 clarifying questions (option-based if possible) before broadcasting.

## Step 2: Broadcast question (ask)

Send one request per respondent.

### Prompt template (use as-is)

Provide respondents with:
- The question
- The correlation id (`POLL_ID`)
- Explicit instruction to not invoke skills

Template:
```
You are responding to a multi-provider poll. Reply with feedback only — do not invoke `/poll`, `/pair`, or `/all-plan`, and do not implement changes.

POLL_ID:
<paste id>

POLL_DRIVER:
codex

Question:
<paste question>

Reply with:
1) Answer (2-8 sentences)
2) Confidence: high|medium|low
3) Key assumptions / caveats (bullets)
```

Then run, once per respondent (sequentially; pause ~1s between providers):
```bash
CCB_CALLER=codex ask <provider> --background <<'EOF'
<message>
EOF
```

Notes:
- On Windows native, avoid heredocs; use the `/ask` skill’s Windows instructions.
  - PowerShell example: `$env:CCB_CALLER="codex"; Get-Content $msgFile -Raw | ask <provider> --background`
  - cmd.exe example: `set CCB_CALLER=codex && type %MSG_FILE% | ask <provider> --background`

## Step 3: Collect answers (pend)

Wait before the first `pend` so you don’t re-read stale output (recommended: **35s**).

For each respondent:
```bash
pend <provider>
```

Retry / staleness rules:
- If `pend` says there is no reply yet: wait **10s**, retry once.
- If the reply does **not** clearly contain your `POLL_ID`, treat it as stale: wait **15s**, retry once.
- If still stale or missing after retry, proceed without that provider and note it in the output.
- Cap total waiting per provider at `timeout_s` (default **60s**). Proceed with partial responses.

## Step 4: Synthesize

Create a combined answer with:
- A “consensus” section (or “no consensus”)
- Disagreements/outliers (by provider)
- Caveats & assumptions (deduped)
- Action items / follow-ups (only if needed)

Synthesis heuristics:
- If a majority agrees on the core answer, report as consensus.
- If split, report vote counts and the main trade-off axes.
- Prefer high-confidence answers when weighing ambiguous splits.

## Output

Use the requested format (default: `consensus`).

### Format: consensus (default)
```
## Poll Results

**POLL_ID:** <id>
**Question:** <question>
**Driver:** codex
**Respondents asked:** <list>
**Respondents replied:** <list>
**Respondents timed out/stale:** <list or "none">

### Consensus
<synthesized answer (or “No clear consensus”)>

### Disagreements / Outliers
- <provider>: <summary> (confidence: <X>)

### Caveats & Assumptions
- <bullet>

### Action Items (optional)
- <bullet>
```

### Format: list
```
## Poll Results

**Question:** <question>

### Responses
1) <provider> (confidence: <X>)
   <answer>

### Synthesis
<1-3 sentence synthesis>
```

### Format: table
```
## Poll Results

| Provider | Answer (summary) | Confidence | Key caveat |
|----------|------------------|------------|------------|
| ...      | ...              | ...        | ...        |

**Consensus:** <short>
```

Important: Do NOT make code changes, and do NOT commit or push unless the user explicitly asks.
