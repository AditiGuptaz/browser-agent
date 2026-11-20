"""
Turns results/runs.jsonl into a readable report: results/runs_readable.md

Usage:
    python show_runs.py

Open the report in VS Code and press Cmd+Shift+V to see it formatted.
Each run shows what the agent chose, whether it was correct, and a table of every
restaurant it listed. Rows marked with a star meet all the rules according to the
agent's own reading of the page.
"""

import csv
import json
import re
from pathlib import Path

TASKS_FILE = Path("tasks.csv")
RUNS_FILE = Path("results/runs.jsonl")
REPORT_FILE = Path("results/runs_readable.md")


def normalize(name):
    if name is None or str(name).strip() == "":
        return "none"
    name = str(name).lower().replace("’", "'")
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return " ".join(name.split())


def is_correct(expected, got):
    exp, got = normalize(expected), normalize(got)
    if exp == "none" or got == "none":
        return exp == got
    return exp == got or exp in got or got in exp


def cell(value):
    """Make a value safe to put inside a markdown table."""
    text = "" if value is None else str(value).strip()
    return text.replace("|", "/") or "—"


def describe_run(run):
    cuisine = run["cuisine"]
    expected = run.get("expected") or ""
    choice = run.get("agent_choice") or None

    if run.get("error"):
        verdict = "⚠️ ERROR"
    elif not expected:
        verdict = "(no expected answer yet)"
    elif is_correct(expected, choice):
        verdict = "✅ CORRECT"
    else:
        verdict = "❌ WRONG"

    lines = [
        f"## Task {run['task_id']} · {cuisine}, {run['town']} · {run.get('prompt', '?')} prompt · run {run['run']} — {verdict}",
        "",
        f"- **Rules:** '{cuisine}' tag, at least {run['min_reviews']} reviews, at least {run['min_stars']} stars",
        f"- **Expected:** {expected or '—'}",
        f"- **Agent chose:** {choice or 'none'}",
        f"- **Python rule on the agent's list would choose:** {run.get('rule_choice') or 'none'}",
        f"- **Agent says success:** {run.get('agent_says_success')} · **Judge says success:** {run.get('judge_says_success')}",
        f"- **Steps:** {run.get('steps')} · **Time:** {run.get('seconds')} s · **Cost:** ${run.get('cost_usd')}",
        f"- **Agent's reason:** {run.get('reason') or '—'}",
    ]
    if run.get("judge_reason"):
        lines.append(f"- **Judge's reason:** {run['judge_reason']}")
    if run.get("error"):
        lines.append(f"- **Error:** {run['error']}")

    places = run.get("places_seen") or []
    lines += ["", f"**Restaurants the agent listed ({len(places)}):**", ""]
    if places:
        lines += [
            "| | Name | Tags (as the agent read them) | Town | Rating | Reviews |",
            "|---|---|---|---|---|---|",
        ]
        for p in places:
            tags = p.get("categories") or ""
            qualifies = (
                cuisine.lower() in tags.lower()
                and (p.get("review_count") or 0) >= run["min_reviews"]
                and (p.get("rating") or 0) >= run["min_stars"]
            )
            mark = "★" if qualifies else ""
            lines.append(
                f"| {mark} | {cell(p.get('name'))} | {cell(tags)} | {cell(p.get('town'))} "
                f"| {cell(p.get('rating'))} | {cell(p.get('review_count'))} |"
            )
    else:
        lines.append("_None listed._")

    lines += ["", "---", ""]
    return lines


def main():
    if not RUNS_FILE.exists():
        print(f"{RUNS_FILE} not found. Run run_tests.py first.")
        return

    runs = [json.loads(line) for line in RUNS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Use the current answers from tasks.csv, so fixes to the answer key show up here too.
    if TASKS_FILE.exists():
        with TASKS_FILE.open(newline="", encoding="utf-8") as f:
            current = {t["id"]: t["expected_choice"].strip() for t in csv.DictReader(f)}
        for run in runs:
            if run["task_id"] in current:
                run["expected"] = current[run["task_id"]]
    runs.sort(key=lambda r: (int(r["task_id"]), r.get("prompt", ""), r["run"]))

    lines = [
        "# Agent runs",
        "",
        f"{len(runs)} runs. ★ = meets every rule according to the agent's own reading of the page.",
        "",
    ]
    for run in runs:
        lines += describe_run(run)

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_FILE}. Open it in VS Code and press Cmd+Shift+V to view it formatted.")


if __name__ == "__main__":
    main()
