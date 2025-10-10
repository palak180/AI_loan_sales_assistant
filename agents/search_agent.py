from state import State
import json
from tools.tavily_tool import tavily_tool
import asyncio
import re
from llm import llm

async def async_search(query):
    return tavily_tool.invoke({"query": f"{query} Tata Capital"})

async def gather_searches(queries):
    tasks = [asyncio.create_task(async_search(q)) for q in queries]
    return await asyncio.gather(*tasks)

def search_agent(state: State) -> State:
    """
    Search agent - generates queries, performs web searches, and summarizes results.
    """
    user_latest_message = state.get("history", "").split("User: ")[-1]
    user_profile = state.get("user_profile", {})
    
    print(f"\n[SEARCH AGENT] Analyzing user message: {user_latest_message[:100]}...")
    
    # Generate search queries based on user's question
    query_prompt = f"""You are a search query generator for Tata Capital loan information.

User's question: {user_latest_message}
User profile: {json.dumps(user_profile)}

Generate 1-5 search queries to find relevant information from Tata Capital's website.
Queries should be focused and specific to get accurate loan information.

Examples of good queries:
- "personal loan eligibility criteria"
- "home loan interest rates 2024"
- "documents required for business loan"
- "processing fees and charges for car loan"

Respond in strict JSON format:
{{
    "queries": ["query1", "query2", "query3"]
}}
"""

    try:
        query_resp = llm.invoke(query_prompt).content
        match = re.search(r"\{.*\}", query_resp, re.DOTALL)
        queries = json.loads(match.group())["queries"] if match else [user_latest_message]
    except Exception as e:
        print(f"[SEARCH AGENT] Query generation error: {e}, using fallback")
        queries = [user_latest_message]

    print(f"[SEARCH AGENT] Generated queries: {queries}")

    try:
        all_results = asyncio.run(gather_searches(queries))
    except Exception as e:
        print(f"[SEARCH AGENT] Search execution failed: {e}")
        state["search_results"] = "Search temporarily unavailable."
        state["action"] = "sales_agent"
        return state

    summaries = []

    for query, raw_result in zip(queries, all_results):
        try:
            results_list = raw_result.get("results", [])
            if not results_list:
                print(f"[SEARCH AGENT] No results for query: {query}")
                continue

            # ---- Rerank for relevance ----
            rerank_prompt = f"""
            Rerank the following search results based on how well they answer:
            "{query}"

            Results:
            {json.dumps(results_list[:8])}

            Provide a concise ranking explanation and list top 3 most relevant results.
            """
            reranked = llm.invoke(rerank_prompt).content

            # ---- Summarize top content ----
            combined_content = "\n\n".join(
                [f"Title: {r['title']}\n{r['content']}" for r in results_list[:3]]
            )

            summary_prompt = f"""
            Summarize the following search results about Tata Capital loans.
            Focus on concrete, factual details such as:
            - loan types
            - interest rates
            - eligibility
            - required documents
            - repayment terms
            - processing fees or offers

            Be concise but information-dense.
            Use clear bullet points or short paragraphs.

            Query: {query}
            Results:
            {combined_content}

            Provide the summary directly — no JSON, no headings, just the text.
            """

            summary = llm.invoke(summary_prompt).content.strip()
            summaries.append(f"=== {query} ===\n{summary}\n")

        except Exception as e:
            print(f"[SEARCH AGENT] Error processing query '{query}': {e}")
            continue

    final_summary = "\n\n".join(summaries) if summaries else "No relevant loan information found."
    state["search_results"] = final_summary
    state["action"] = "sales_agent"

    print(f"\n[SEARCH COMPLETE] Extracted structured loan data for {len(summaries)} queries.")
    return state
