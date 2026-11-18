from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from browser_use.llm import ChatOpenAI
import asyncio

# ── keep_alive=True goes HERE, when creating the BrowserSession ──
#browser_session = BrowserSession(keep_alive=True)


agent = Agent(
    #task="Go to Yelp and find a Thai restaurant in Princeton, New Jersey with at least "
    #     "200+ reviews and 4.0 or higher stars. Pick the one with the highest rating "
    #     "and open its page.",
    #task= "Go to https://www.yelp.com/search?find_desc=Thai&find_loc=Princeton%2C+NJ&sortby=rating . "
    #"Do not click any filter buttons. "
    #"Look only at the first page of results. Do not go to page 2. "
    #"Extract the list of restaurants from the page in one step instead of scrolling repeatedly. "
    #"Ignore sponsored results. Only consider restaurants whose category includes 'Thai'. "
    #"From those, find the ones with at least 200 reviews and 3.5 or higher stars, "
    #"and open the page of the highest rated one. "
    #"If none on the first page meet all criteria, say so and stop. Do not pick a substitute."

    task = 
    "Go to https://www.google.com/maps/search/Thai+restaurants+in+Princeton,+NJ . "
    "If a cookie or consent page appears, stop and report it. Do not accept anything. "
    "Do not click any filter buttons such as Rating, Open now, or Price. "
    "Read the results list on the left side of the page. Scroll that list at most 2 times, "
    "then stop scrolling. Do not move or zoom the map. "
    "Ignore results marked as Sponsored or Ad. "
    "Only consider places whose category label includes 'Thai'. "
    "Review counts may be shown in short form, for example (1.2K) means 1,200 reviews. "
    "For each Thai place you see, report its name, category label, address or town, "
    "star rating and review count. "
    "From those, find the ones with at least 200 reviews and 4.0 or higher stars, "
    "and open the page of the highest rated one. you trust a rating more when many people gave it." 
    "If two are tied on rating, "
    "pick the one with more reviews. "
    "If none of the places you saw meet all criteria, say so and stop. "
    "Do not pick a substitute."


,

    llm=ChatOpenAI(model="gpt-4o"),
)

async def main():
    result = await agent.run()
    print(result.final_result())
    #
    # input("Press Enter to close the browser...")   # keeps it open until you press Enter

asyncio.run(main())