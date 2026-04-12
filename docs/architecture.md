# DataWitness — Architecture Notes

## System Design Philosophy

DataWitness is built on a **separation of concerns** principle between language understanding and data computation:

- The **LLM (Groq Llama 3.1)** handles only intent translation — it reads the user's question and outputs a Pandas code string. It never computes numbers directly.
- **Pandas** handles all actual computation — it executes the generated code on the real dataset. This is deterministic and verifiable.
- The **Trust Layer** (`trust.py`) intercepts every result before display and attaches confidence metadata, metric definitions, and source traceability.

This eliminates hallucination on numerical answers — the single biggest failure mode of LLM-based data tools.

## Data Flow

```
1. User input (natural language)
         ↓
2. Groq Llama 3.1 — generates Pandas code string only
         ↓
3. Safety check — blocks dangerous operations (import, exec, os, etc.)
         ↓
4. Python exec() — runs Pandas code on actual DataFrame
         ↓
5. trust.py — computes confidence, detects metrics, finds source rows
         ↓
6. Groq Llama 3.1 — generates narrative from verified numerical result
         ↓
7. Streamlit split-screen render:
     LEFT: narrative + chart
     RIGHT: code + confidence + metric defs + source rows
```

## Key Design Decisions

### Why Groq instead of OpenAI?
- Free tier with generous rate limits
- Sub-second inference on Llama 3.1 70B
- No credit card required for initial setup

### Why Streamlit instead of Next.js / React?
- Native Python — no context switching for the data/ML team
- Split-column layout available out of the box
- One-command deployment to Streamlit Cloud
- Faster to iterate in a 36-hour hackathon

### Why YAML for the metric dictionary?
- Human-readable and editable without code
- Judges can open `metrics.yaml` directly in the repo and verify definitions
- Easy to extend — adding a new metric takes 5 lines

### Why Pandas over SQL?
- No database setup required — works directly on CSV
- Output is always a DataFrame — consistent for chart rendering
- Code is readable and auditable — judges can inspect it in the right panel
