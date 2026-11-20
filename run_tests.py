"""
Runs the test set in tasks.csv and scores every answer against expected_choice.

Examples:
    python run_tests.py --tasks 1 --runs 1                 # one quick check
    python run_tests.py --runs 2                           # all tasks, improved prompt, 2 runs each
    python run_tests.py --runs 2 --prompt loose            # same with the original prompt
    python run_tests.py --runs 2 --prompt both --max-cost 3

Results are saved as each run finishes, so nothing is lost if you stop it:
    results/results.csv   one row per run (open in Excel or VS Code)
    results/runs.jsonl    full details of each run, including every place the agent listed
"""

import argparse
import asyncio
import csv
import json
import re
from datetime import datetime
from pathlib import Path

from agent import run_search

TASKS_FILE = Path("tasks.csv")
RESULTS_DIR = Path("results")
RESULTS_CSV = RESULTS_DIR / "results.csv"
RUNS_JSONL = RESULTS_DIR / "runs.jsonl"

RESULT_COLUMNS = [
    "timestamp", "task_id", "task_type", "prompt", "run", "cuisine", "town",
    "expected", "agent_choice", "correct", "rule_choice", "agent_matches_rule",
    "agent_says_success", "judge_says_success", "steps", "seconds", "cost_usd", "error",
]


def normalize(name: str | None) -> str:
    """Make names comparable: lower case, no punctuation, single spaces. None becomes 'none'."""
    if name is None or name.strip() == "":
        return "none"
    name = name.lower().replace("’", "'")
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return " ".join(name.split())


def is_correct(expected: str, agent_choice: str | None) -> bool:
    """
    Compare the agent's answer with the expected one.
    Allows small naming differences, for example "Thai Village" vs "Thai Village Restaurant".
    """
    exp, got = normalize(expected), normalize(agent_choice)
    if exp == "none" or got == "none":
        return exp == got
    return exp == got or exp in got or got in exp


def load_tasks(selected_ids: list[str] | None) -> list[dict]:
    with TASKS_FILE.open(newline="", encoding="utf-8") as f:
        tasks = list(csv.DictReader(f))
    if selected_ids:
        tasks = [t for t in tasks if t["id"] in selected_ids]
    return tasks


def save_row(summary: dict, task: dict, run: int) -> dict:
    """Append one run to results.csv and runs.jsonl, and return the row written to the CSV."""
    RESULTS_DIR.mkdir(exist_ok=True)
    expected = task["expected_choice"].strip()

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task_id": task["id"],
        "task_type": task["type"],
        "prompt": summary["prompt"],
        "run": run,
        "cuisine": task["cuisine"],
        "town": task["town"],
        "expected": expected,
        "agent_choice": summary["agent_choice"],
        # Left empty when the task has no expected answer yet, or the run crashed.
        "correct": "" if (not expected or summary["error"]) else is_correct(expected, summary["agent_choice"]),
        "rule_choice": summary["rule_choice"],
        "agent_matches_rule": summary["agent_matches_rule"],
        "agent_says_success": summary["agent_says_success"],
        "judge_says_success": summary["judge_says_success"],
        "steps": summary["steps"],
        "seconds": summary["seconds"],
        "cost_usd": summary["cost_usd"],
        "error": summary["error"],
    }

    new_file = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)

    with RUNS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**summary, "task_id": task["id"], "run": run, "expected": expected}) + "\n")

    return row


def print_summary(rows: list[dict]) -> None:
    print("\n========== Summary of this session ==========")
    for prompt in sorted({r["prompt"] for r in rows}):
        group = [r for r in rows if r["prompt"] == prompt]
        scored = [r for r in group if r["correct"] != ""]
        right = sum(1 for r in scored if r["correct"] is True)
        costs = [r["cost_usd"] for r in group if r["cost_usd"] is not None]
        steps = [r["steps"] for r in group if r["steps"] is not None]
        errors = sum(1 for r in group if r["error"])
        print(f"\nPrompt: {prompt}")
        print(f"  Runs:          {len(group)}  (errors: {errors})")
        if scored:
            print(f"  Correct:       {right} of {len(scored)} scored runs ({right / len(scored):.0%})")
        else:
            print("  Correct:       no runs could be scored (fill in expected_choice in tasks.csv)")
        if steps:
            print(f"  Average steps: {sum(steps) / len(steps):.1f}")
        if costs:
            print(f"  Total cost:    ${sum(costs):.2f}")
    print(f"\nDetails saved in {RESULTS_CSV} and {RUNS_JSONL}")


async def main():
    parser = argparse.ArgumentParser(description="Run the browser agent on the test set.")
    parser.add_argument("--tasks", nargs="*", help="Task ids to run, e.g. --tasks 1 2 3. Default: all.")
    parser.add_argument("--runs", type=int, default=1, help="How many times to run each task. Default: 1.")
    parser.add_argument("--prompt", choices=["improved", "loose", "both"], default="improved")
    parser.add_argument("--max-cost", type=float, default=3.0,
                        help="Stop starting new runs once this many dollars have been spent "
                         "(the last run can go slightly over). Default: 3.00.")
    args = parser.parse_args()

    tasks = load_tasks(args.tasks)
    if not tasks:
        print("No matching tasks found in tasks.csv.")
        return

    unchecked = [t["id"] for t in tasks if not t["expected_choice"].strip()]
    if unchecked:
        print(f"Note: tasks {', '.join(unchecked)} have no expected_choice yet. They will run but not be scored.")

    prompts = ["loose", "improved"] if args.prompt == "both" else [args.prompt]
    total_runs = len(tasks) * args.runs * len(prompts)
    print(f"Planned: {total_runs} runs. Spending limit: ${args.max_cost:.2f}\n")

    rows, spent, count = [], 0.0, 0
    # Prompts alternate inside each task, so if the spending limit stops the session early,
    # both prompts have been tried on the same tasks and can still be compared fairly.
    for task in tasks:
        for run in range(1, args.runs + 1):
            for prompt in prompts:
                if spent >= args.max_cost:
                    print(f"\nStopping: spending limit of ${args.max_cost:.2f} reached.")
                    print_summary(rows)
                    return
                count += 1
                print(f"--- Run {count}/{total_runs}: task {task['id']} ({task['cuisine']}, {task['town']}), "
                      f"prompt={prompt}, run {run} ---")
                summary = await run_search(
                    cuisine=task["cuisine"],
                    town=task["town"],
                    min_reviews=int(task["min_reviews"]),
                    min_stars=float(task["min_stars"]),
                    prompt=prompt,
                )
                row = save_row(summary, task, run)
                rows.append(row)
                spent += summary["cost_usd"] or 0.0
                print(f"    expected={row['expected'] or '(not filled in)'}  agent={row['agent_choice']}  "
                      f"correct={row['correct']}  cost=${summary['cost_usd']}  spent so far=${spent:.2f}")

    print_summary(rows)


if __name__ == "__main__":
    asyncio.run(main())
