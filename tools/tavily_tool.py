from langchain_tavily import TavilySearch
import dotenv

dotenv.load_dotenv()

tavily_tool = TavilySearch(
    max_results = 2,
    topic = "finance",
    # include_answer=False,
    # include_raw_content=True,
    # include_images=False,
    # include_image_descriptions=False,
    search_depth = "advanced",
    # time_range="day",
    include_domains = ["tatacapital.com"],
    exclude_domains = ["https://www.tatacapital.com/personal-loan/eligibility-calculator.html", "https://www.tatacapital.com/blog/"]
)

tools = [tavily_tool]

# results = tavily_tool.invoke({"query": "refinancing options, personal loan interest rates, tenure, additional fees"})
# print(results)