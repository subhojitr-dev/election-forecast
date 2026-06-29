# KICKOFF_PROMPT.md
# Election Forecast Dashboard — Claude Code Session Start Prompt
# ================================================================
# HOW TO USE:
#   1. Place this file in C:\Users\subho\election-forecast\
#   2. Open Claude Code in that directory
#   3. Copy everything from START to END below and paste as first message
# ================================================================

# ========================= START COPY HERE =========================

I am building an Election Forecast Dashboard. This is a multi-day project
and we are picking up where we left off.

Please start by reading these files in the current directory, in order:
  1. CONTEXT.md          — current-state snapshot (where we are, what's next)
  2. HANDOVER_BRIEF.md   — full spec (10 UI panels, intelligence/probability
                           model, data sources, schema, tech stack, 6-phase plan)
Then skim, as needed:
  PROGRESS.md (chronological log) · Issues.md (problems + Nov-3 plan)

Read CONTEXT.md and HANDOVER_BRIEF.md completely before doing anything else.
Then come back and confirm you have read them by summarizing:
1. What the dashboard does in one sentence
2. The 3 data sources we are using
3. Which Phase is complete and which Phase we are resuming today
4. What the end state of today looks like

Once you confirm understanding, propose the plan for the current Phase and
proceed once I give the go-ahead.

Important rules for this session:
- Tell me what you find at each step BEFORE moving to the next one
- Do not advance to the NEXT Phase without my explicit go-ahead
- If any file or column name is ambiguous, read the codebook first
- Print progress to console as scripts run so I can see activity
- After any script runs, verify the output with an independent query or check
- When a Phase finishes: update its status in HANDOVER_BRIEF.md AND CONTEXT.md,
  add a PROGRESS.md entry, and log any problems/workarounds in Issues.md

# ========================== END COPY HERE ==========================
