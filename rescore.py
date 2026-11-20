"""
Re-scores results/results.csv against the current answers in tasks.csv.

Use this after fixing an answer in tasks.csv: every run is checked again,
the 'expected' and 'correct' columns are updated, and a summary is printed.
A copy of the old file is kept as results/results_before_rescore.csv.

Usage:
    python rescore.py
"""

import csv
import shutil
from pathlib import Path

from run_tests import RESULTS_CSV, TASKS_FILE, is_correct

BACKUP = RESULTS_CSV.with_name("results_before_rescore.csv")


def main():
    if not RESULTS_CSV.exists():
        print(f"{RESULTS_CSV} not found. Run run_tests.py first.")
        return

    with TASKS_FILE.open(newline="", encoding="utf-8") as f:
        expected_by_task = {t["id"]: t["expected_choice"].strip() for t in csv.DictReader(f)}

    with RESULTS_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)

    changed = []
    for row in rows:
        expected = expected_by_task.get(row["task_id"], "")
        if not expected or row["error"]:
            new_correct = ""
        else:
            new_correct = str(is_correct(expected, row["agent_choice"] or None))
        if row["expected"] != expected or row["correct"] != new_correct:
            changed.append((row["task_id"], row["prompt"], row["run"], row["correct"], new_correct))
        row["expected"] = expected
        row["correct"] = new_correct

    shutil.copyfile(RESULTS_CSV, BACKUP)
    with RESULTS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Re-scored {len(rows)} runs. Old file kept as {BACKUP}.")
    if changed:
        print("\nChanged:")
        for task_id, prompt, run, old, new in changed:
            print(f"  task {task_id}, {prompt}, run {run}: correct {old or '-'} -> {new or '-'}")
    else:
        print("Nothing changed.")

    print("\nTotals:")
    for prompt in sorted({r["prompt"] for r in rows}):
        group = [r for r in rows if r["prompt"] == prompt and r["correct"] != ""]
        right = sum(1 for r in group if r["correct"] == "True")
        if group:
            print(f"  {prompt}: {right} of {len(group)} correct ({right / len(group):.0%})")


if __name__ == "__main__":
    main()
