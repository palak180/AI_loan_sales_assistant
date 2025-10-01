from state import State
import dotenv
from langchain_groq import ChatGroq
import json
import re
from langgraph.types import Command
from typing import Literal
from langgraph.graph import END
from agents.prompts import PROMPTS
from tools.tavily_tool import tavily_tool
from tools.emi_calculator_tool import calculate_emi
from tools.credit_bureau import credit_score_api, pre_approved_amount_api

dotenv.load_dotenv()

llm = ChatGroq(model="llama-3.1-8b-instant")

MAX_COUNT = 6

def master_agent(state: State) -> Command[Literal["user_agent", "sales_agent", "search_agent", END]]:
    if state.get("count", 0) >= MAX_COUNT:
        return Command(goto = END, update = state)
    
    if state["history"] == "":
        greeting = "Hello! Welcome to Tata Capital loan assistant. How can I help you today?"
        print("Master Agent:", greeting)
        state["history"] = "Loan assistant: " + greeting
        return Command(goto = "user_agent", update = state)

    # Decide if search needed (example heuristic: look for keywords)
    user_latest_message = state.get("history", "").split("User: ")[-1].lower()

    response = llm.invoke(f"""You are a master agent for Tata Capital Loans.
        Based on the user's latest message, decide if searching the Tata Capital website is needed to assist the sales agent.
        If the message contains keywords related to loan details, eligibility, rates, etc.,
        set action to 'search_agent' and populate 'queries' with a list of relevant search terms (can be more than one).
        Otherwise, set action to 'sales_agent' and return 'queries' as an empty list.

        Latest user message: {user_latest_message}

        Respond in a strict JSON format with 'action' and 'queries' as a list. Examples:
        1. {{
            "action": "search_agent",
            "queries": ["documents required for personal loan", "processing charges for personal loan"]
        }}
        2. {{
            "action": "sales_agent",
            "queries": []
        }}
        3. {{
            "action": "search_agent",
            "queries": ["interest rates for home loan", "charges and requirements for home loan"]
        }}
    """)

    print("Master Agent:", response.content)

    text = str(response.content)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    new_state = state.copy()

    if match:
        try:
            data = json.loads(match.group())
            print("Clean JSON:", data)
            new_state["queries"] = data.get("queries", [])  # Always a list now
            new_state["action"] = data.get("action", "sales_agent")
        except json.JSONDecodeError as e:
            print("Still invalid JSON:", e)
    else:        
        data = json.loads('{"action": "sales_agent", "queries": []}')
        print("No JSON found in response")
    
    return Command(goto = data.get("action", "sales_agent"), update = new_state)

def sales_agent(state: State) -> Command[Literal["user_agent", END]]:
    if state.get("count", 0) >= MAX_COUNT:
        print("Stopping conversation at sales_agent due to max count")
        return Command(goto=END, update=state)

    search_info = state.get("search_results", "")
    prompt = PROMPTS['sales_agent'] + "\nHistory: " + state["history"]
    if search_info:
        prompt += "\nRefer to the following search info when responding:\n" + search_info

    messages = "Your role: " + prompt + \
    "\nRespond appropriately as the sales agent."

    tools = [calculate_emi, credit_score_api, pre_approved_amount_api]
    llm_with_tools = llm.bind_tools(tools)

    # Use the tool-enabled LLM for invocation
    response = llm_with_tools.invoke(messages)
    print("\n\nSales:", response.content)

    new_state = state.copy()
    new_state["search_results"] = ""
    new_state["history"] += "\nSales Agent: " + response.content
    new_state["count"] = state.get("count", 0) + 1

    return Command(goto="user_agent", update=new_state)


def search_agent(state: State) -> Command[Literal["sales_agent"]]:
    queries = state.get("queries", "")
    if len(queries) == 0:
        return Command(goto="sales_agent", update=state)  

    
    try:
        overall_search_results = ""
        for query in queries:
            tavily_results = tavily_tool.invoke({"query": "Find everything related to " + query + " in relation to Tata Capital loans."})
            tavily_results_formatted = ""

            # print(f"\n\nTavily Raw Results for query '{query}':", tavily_results)

            for result in tavily_results.get("results", []):
                tavily_results_formatted += f"{result['title']}: {result['content']}\n"
            
            
            summary = llm.invoke(f"""
        Summarize the following search results into a to the point summary relevant to the user's query about Tata Capital loans.
        If no relevant information is found, respond with 'No relevant information found.
        Stick to the facts from the search results, do not make up any information.
        Do not add any pleasantries or any extra random things. 
        User Query: {query}
        Search Results: {tavily_results_formatted}
        """).content
            
            overall_search_results += f"Query: {query}\nSummary: {summary}\n\n"
        # The numbers/processes/terms/interest rates/fees/tenure and other facts which are relevant to the query must be included.

    except Exception as e:
        overall_search_results = ""


    new_state = state.copy()
    new_state["search_results"] = overall_search_results
    # print("\n\nSearch Summary:", overall_search_results)
    
    # state["history"] += f"\nSearchAgent({query}): {summary}"

    return Command(goto="sales_agent", update=new_state)

