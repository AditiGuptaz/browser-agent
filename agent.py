"""
Browser agent that searches a restaurant site for places matching a cuisine,
a town, a minimum star rating and a minimum review count.

Run one search:
    python agent.py

Change SITE below to "yelp" or "google_maps" to switch sites.
"""

import asyncio
import json
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from browser_use import Agent, ChatOpenAI

load_dotenv()

# ---------- Settings ----------
MODEL = "gpt-4o"
SITE = "yelp"  # "yelp" or "google_maps"
MAX_STEPS = 15  # hard stop so a confused run can't go on and on


# ---------- What the agent must return ----------
# The agent fills in this structure instead of writing a sentence,
# so its answer can be checked by code.
class Place(BaseModel):
    name: str
    categories: str = Field(description="Category labels exactly as shown on the page")
    town: str
    rating: float
    review_count: int


class SearchResult(BaseModel):
    places_seen: list[Place] = Field(
        description="Every place of the requested cuisine you looked at, whether or not it met the criteria"
    )
    chosen: str | None = Field(
        description="Name of the place whose page you opened, or null if no place met all criteria"
    )
    reason: str = Field(description="One sentence on why you chose it, or why none qualified")


# ---------- Task prompts, one per site ----------
YELP_TASK = (
    "Go to {url} . "
    "Do not click any filter buttons. "
    "Look only at the first page of results. Do not go to page 2. "
    "Extract the list of restaurants from the page in one step instead of scrolling repeatedly. "
    "When extracting, list every restaurant on the page with its categories, rating and review count. "
    "Do not filter during extraction; apply the criteria afterwards. "
    "Results under the 'Sponsored Results' heading are ads: skip them and use only the numbered results. "
    "Only consider restaurants whose category tags include '{cuisine}'. "
    "Use only the category tags shown under each listing, not words that appear in reviews. "
    "For each {cuisine} restaurant you see, record its name, categories, town, star rating and review count. "
    "From those, find the ones with at least {min_reviews} reviews and {min_stars} or higher stars, "
    "and open the page of the highest rated one. If two are tied on rating, pick the one with more reviews. "
    "If none on the first page meet all criteria, say so and stop. Do not pick a substitute."
)

GOOGLE_MAPS_TASK = (
    "Go to {url} . "
    "If a cookie or consent page appears, stop and report it. Do not accept anything. "
    "Do not click any filter buttons such as Rating, Open now, or Price. "
    "Read the results list on the left side of the page. Scroll that list at most 2 times, "
    "then stop scrolling. Do not move or zoom the map. "
    "Ignore results marked as Sponsored or Ad. "
    "Only consider places whose category label includes '{cuisine}'. "
    "Review counts may be shown in short form, for example (1.2K) means 1,200 reviews. "
    "For each {cuisine} place you see, record its name, category label, town, star rating and review count. "
    "From those, find the ones with at least {min_reviews} reviews and {min_stars} or higher stars, "
    "and open the page of the highest rated one. If two are tied on rating, pick the one with more reviews. "
    "If none of the places you saw meet all criteria, say so and stop. Do not pick a substitute."
)


def build_task(site: str, cuisine: str, town: str, min_reviews: int, min_stars: float) -> str:
    """Fill in the prompt for the chosen site."""
    if site == "yelp":
        url = (
            "https://www.yelp.com/search?find_desc="
            + quote_plus(cuisine)
            + "&find_loc="
            + quote_plus(town)
        )
        template = YELP_TASK
    elif site == "google_maps":
        url = "https://www.google.com/maps/search/" + quote_plus(f"{cuisine} restaurants in {town}")
        template = GOOGLE_MAPS_TASK
    else:
        raise ValueError(f"Unknown site: {site}. Use 'yelp' or 'google_maps'.")

    return template.format(
        url=url, cuisine=cuisine, min_reviews=min_reviews, min_stars=min_stars
    )


def rule_choice(places: list[Place], cuisine: str, min_reviews: int, min_stars: float) -> str | None:
    """
    Apply the selection rule in plain Python to the places the agent reported.
    If this disagrees with the agent's own choice, the agent read the page
    correctly but picked wrongly.
    """
    qualifying = [
        p
        for p in places
        if cuisine.lower() in p.categories.lower()
        and p.review_count >= min_reviews
        and p.rating >= min_stars
    ]
    if not qualifying:
        return None
    best = max(qualifying, key=lambda p: (p.rating, p.review_count))
    return best.name


async def run_search(
    cuisine: str,
    town: str,
    min_reviews: int,
    min_stars: float,
    site: str = SITE,
    model: str = MODEL,
    max_steps: int = MAX_STEPS,
) -> dict:
    """Run the agent once and return a summary that can be saved as one row of results."""
    agent = Agent(
        task=build_task(site, cuisine, town, min_reviews, min_stars),
        llm=ChatOpenAI(model=model),
        output_model_schema=SearchResult,
        calculate_cost=True,
    )

    summary = {
        "site": site,
        "model": model,
        "cuisine": cuisine,
        "town": town,
        "min_reviews": min_reviews,
        "min_stars": min_stars,
        "agent_choice": None,
        "rule_choice": None,
        "agent_matches_rule": None,
        "places_seen": [],
        "reason": None,
        "agent_says_success": None,
        "judge_says_success": None,
        "judge_reason": None,
        "steps": None,
        "seconds": None,
        "cost_usd": None,
        "error": None,
    }

    try:
        history = await agent.run(max_steps=max_steps)
    except Exception as e:  # a crash still becomes a row in the results
        summary["error"] = f"{type(e).__name__}: {e}"
        return summary

    summary["steps"] = history.number_of_steps()
    summary["seconds"] = round(history.total_duration_seconds(), 1)
    summary["agent_says_success"] = history.is_successful()
    judgement = history.judgement()
    if judgement:
        summary["judge_says_success"] = judgement.get("verdict")
        summary["judge_reason"] = judgement.get("failure_reason") or None
    if history.usage is not None:
        summary["cost_usd"] = round(history.usage.total_cost, 4)

    try:
        result = history.structured_output
    except Exception as e:  # the agent's answer didn't match the required format
        summary["error"] = f"Could not read structured output: {e}"
        return summary

    if result is None:
        summary["error"] = "Agent finished without a structured answer"
        errors = [err for err in history.errors() if err]
        if errors:
            summary["error"] += f" (last error: {errors[-1]})"
        return summary

    summary["agent_choice"] = result.chosen
    summary["reason"] = result.reason
    summary["places_seen"] = [p.model_dump() for p in result.places_seen]
    summary["rule_choice"] = rule_choice(result.places_seen, cuisine, min_reviews, min_stars)
    summary["agent_matches_rule"] = summary["agent_choice"] == summary["rule_choice"]
    return summary


async def main():
    summary = await run_search(
        cuisine="Thai",
        town="Princeton, NJ",
        min_reviews=200,
        min_stars=4.0,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())