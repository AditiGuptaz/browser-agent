# Browser Agent Reliability on Yelp

A browser agent that searches Yelp for restaurants matching a cuisine, a town, a minimum star rating and a minimum review count, and a small test setup that measures how often it gets the answer right.

The agent itself is only a few lines of code on top of [browser-use](https://github.com/browser-use/browser-use). This project is about what happens around it: where the agent goes wrong, how to check its answers against something other than its own word, and which changes to the prompt make it more reliable.

**Status:** work in progress. The test set and runner are built. The full test runs and results table are next.

## Why this project

Browser agents usually report "Task completed successfully" whether or not they did the task. In my first runs, the agent picked a ramen restaurant for a Thai search and still reported success. I wanted to find out how often that happens, why, and what reduces it.

## How it works

1. **The agent** (`agent.py`) opens a Yelp search page and reads the first page of results.
2. **It returns a structured answer** instead of a sentence: every restaurant of the requested cuisine it saw (name, category tags, town, rating, review count), the one it chose, and a short reason. The format is defined with Pydantic, so the answer can be checked by code.
3. **A Python rule re-checks the choice.** `rule_choice()` applies the same selection rule to the restaurants the agent reported. If the agent's choice and the rule's choice differ, the agent read the page correctly but chose wrongly.
4. **The runner** (`run_tests.py`) runs every task in the test set, compares each answer with the correct one, and saves the results.

Selection rule used in every task: the restaurant's Yelp category tags must include the cuisine word exactly (a "Szechuan" tag does not count as "Chinese"), and it must meet both the review and star minimums. The highest rating wins; if two are tied, the one with more reviews wins. If nothing qualifies, the correct answer is "none".

## Test set

`tasks.csv` holds 10 tasks across central and northern New Jersey. The correct answer for each task was checked by hand on Yelp (logged out, first page of results only, sponsored results skipped), and the date of the check is recorded, because ratings and review counts change over time.

| Task | Search | Minimums | Correct answer |
|---|---|---|---|
| 1 | Thai, Princeton | 200 reviews, 4.0 stars | None |
| 2 | Indian, Edison | 200, 4.0 | Delhi Garden (tie on rating, wins on reviews) |
| 3 | Italian, Hoboken | 300, 4.0 | Otto Strada (the top-rated place misses the review minimum) |
| 4 | Mexican, New Brunswick | 150, 4.0 | Tacoria |
| 5 | Chinese, Somerset | 100, 3.5 | Hong Kong Garden |
| 6 | Japanese, Jersey City | 200, 4.5 | Sushi by Bou (exactly meets the 4.5 minimum) |
| 7 | Korean, Princeton | 100, 4.0 | None |
| 8 | Ethiopian, Somerset | 50, 4.0 | Eshkol Ethiopian Cuisine & Cafe |
| 9 | Thai, Princeton | 5,000, 4.0 | None (built to have no answer) |
| 10 | Vietnamese, New Brunswick | 100, 4.0 | Baguette Delite |

The set mixes tasks with a clear answer, tasks that test the tie-break and the review minimum, and tasks where the right answer is "none". The "none" tasks matter most: they show whether the agent admits nothing qualifies or substitutes something that doesn't.

## What I found so far

These come from early runs and from checking the agent's answers against the live Yelp pages by hand. They are observations from a small number of runs, not measured rates; the test runs will put numbers on them.

**1. It reports success when it is wrong.** With a loosely worded prompt, the agent searched for Thai restaurants in Princeton, clicked filters nobody asked for (Price, Open Now), scrolled for 12 steps, and finally chose Lan Ramen, a Chinese and ramen restaurant. It reported the task as successful.

**2. It takes the cuisine from review text instead of category tags.** In one run it listed Shu House Restaurant as "Thai, Szechuan" and chose it. On Yelp, its only category tag is Szechuan; the word "Thai" came from a customer review ("Best Chinese/Thai restaurant in the area"). The next run of the same task read the tag correctly.

**3. It reads ads as results.** Yelp shows sponsored listings above the real results. The agent included two of them in its list even though the prompt said to ignore sponsored results.

**4. The same task gives different answers.** Two runs of the identical Thai/Princeton task, minutes apart, returned "Shu House Restaurant" and "none". A single run says little about reliability, which is why the runner repeats every task.

**5. It filtered too early.** In one run, the agent's page-reading step asked only for restaurants that already met the criteria, so it reported a single restaurant. That made it impossible to check whether it had missed any.

**6. The built-in judge is not reliable either.** browser-use can ask a second model to judge each run. In my runs it approved a wrong answer once and failed a correct one once (because a "verifying device" screen had appeared at the start). This is why the project uses a hand-checked answer key instead.

**7. Tighter instructions cut the work sharply.** Starting from a direct search URL, limiting the agent to the first page, and asking it to read the page in one step reduced a run from 12 steps to 4.

## Changes made in response

- The agent starts from a Yelp search URL instead of typing into the search box.
- It must not click filters and may only read the first page.
- It must list every restaurant before applying the criteria, not filter while reading.
- It must skip anything under the "Sponsored Results" heading.
- It must use only the category tags under each listing, never words from reviews.
- It returns a structured answer that code can check, and has a hard limit of 15 steps.

The original loose prompt is kept in `agent.py` so both versions can be compared on the same tasks.

## Results

*Pending.* The plan is to run every task twice with the original prompt and twice with the improved one, and report for each:

- how many answers were correct
- average steps and cost per run
- how often each mistake above occurred
- how often the agent's own "success" and the built-in judge agreed with the correct answer

## Running it

Requirements: Python 3.12, an OpenAI API key, and Chrome or Chromium.

```bash
python -m venv browser-agent-env
source browser-agent-env/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project folder:

```
OPENAI_API_KEY=your-key-here
```

Run one search:

```bash
python agent.py
```

Run the test set:

```bash
python run_tests.py --tasks 1 --runs 1                  # one quick check
python run_tests.py --runs 2 --prompt both --max-cost 3 # full comparison, stops after $3
```

Results are saved to `results/results.csv` (one row per run) and `results/runs.jsonl` (full details), as each run finishes.

Each run costs about $0.12 to $0.17 with GPT-4o.

## Files

| File | What it does |
|---|---|
| `agent.py` | The agent: builds the prompt, runs one search, returns a structured summary |
| `run_tests.py` | Runs the test set, scores each answer, saves results, enforces a spending limit |
| `tasks.csv` | The 10 test tasks with hand-checked correct answers |
| `requirements.txt` | Python packages |

## Limitations

- **Small test set.** 10 tasks in one region. Enough to show patterns, not to give precise rates.
- **Yelp changes.** Ratings, review counts and result order change over time, so the correct answers are only valid around the date they were checked.
- **Distance isn't part of the rule.** For the Ethiopian search in Somerset, Yelp widened the search and the top answer is in Pennsylvania. The agent follows the rule correctly but the answer isn't useful to someone in Somerset. The rules only cover what they say.
- **One site, one model.** All tests use Yelp and GPT-4o. The same restaurant can look very different on another site: Thai Village in Princeton has 2.9 stars on Yelp and 4.5 on Google Maps.
- **Bot checks.** Yelp often shows a "verifying device" screen at the start of a run. The agent gets past it by waiting, but it may not always.

## Use of Yelp

This project runs at very low volume (a few dozen searches) for learning and demonstration. It is not intended for scraping or bulk data collection.

## Tech

Python, [browser-use](https://github.com/browser-use/browser-use) 0.13.10, OpenAI GPT-4o, Pydantic
