from state import State
import dotenv
from langchain_groq import ChatGroq
import json
import re
from typing import Literal
from langgraph.graph import END
from agents.prompts import PROMPTS
from tools.tavily_tool import tavily_tool
from tools.emi_calculator_tool import calculate_emi
from tools.credit_bureau import credit_score_api, pre_approved_amount_api

dotenv.load_dotenv()

llm = ChatGroq(model="llama-3.1-8b-instant")

MAX_COUNT = 6

def update_user_profile(latest_message: str, current_profile: dict) -> dict:
    """
    Update the user profile based on the latest message using LLM.
    """
    if len(current_profile) == 0:
        prompt = f"""
        You are an expert at extracting and creating user profiles for loan applications based on conversation history.
        The latest user message is: "{latest_message}"
        Create a user profile with any relevant information from the latest message.
        Extract: name, phone, email, user_id, income, employment_type, loan_amount, loan_type, loan_tenure, property_value, etc.
        If no relevant information is found, return an empty JSON object.
        Return the profile in strict JSON format.
        """
    else:
        prompt = f"""
        You are an expert at extracting and updating user profiles for loan applications based on conversation history.
        The current user profile is: {json.dumps(current_profile)}
        The latest user message is: "{latest_message}"
        
        Update the user profile with any new information from the latest message.
        If no new relevant information is found, return the current profile unchanged.
        
        Return the updated profile in strict JSON format.
        """

    response = llm.invoke(prompt)
    text = str(response.content)
    match = re.search(r"\{.*\}", text, re.DOTALL)

    print("Updated profile: ", match)
    if match:
        try:
            updated_profile = json.loads(match.group())
            return updated_profile
        except json.JSONDecodeError as e:
            print("Invalid JSON in profile update:", e)
            return current_profile
    else:
        print("No JSON found in profile update response")
        return current_profile


def master_agent(state: State) -> State:
    """
    Master routing agent - decides which agent to call next.
    Returns updated state with 'action' field set for routing.
    """
    # Check max count
    if state.get("count", 0) >= MAX_COUNT:
        state["action"] = "end"
        return state
    
    # Initial greeting
    if state["history"] == "":
        greeting = "Hello! Welcome to Tata Capital loan assistant. How can I help you today?"
        print("Master Agent:", greeting)
        state["history"] = "Loan assistant: " + greeting
        state["action"] = "user_agent"
        return state

    # Get latest user message
    user_latest_message = state.get("history", "").split("User: ")[-1]
    
    # Update user profile
    user_profile = update_user_profile(user_latest_message, state["user_profile"])
    state["user_profile"] = user_profile

    # Routing decision prompt
    routing_prompt = f"""You are a master routing agent for Tata Capital Loans.
    Analyze the conversation and user profile to decide the next action.

    User's latest message: {user_latest_message}
    Current user profile: {json.dumps(user_profile)}

    Routing Rules:
    1. If user mentions/provides a user_id AND we haven't checked credit yet → route to 'underwriting_agent'
    2. If user asks about loan products, eligibility, rates, documents, fees, processes → route to 'search_agent' with specific queries
    3. If user asks to calculate EMI AND we have (loan_amount, interest_rate, tenure) → route to 'emi_calculator'
    4. Otherwise (general sales, follow-ups, negotiations) → route to 'sales_agent'

    Respond in strict JSON format:
    {{
        "action": "underwriting_agent" | "search_agent" | "emi_calculator" | "sales_agent",
        "queries": ["query1", "query2"] (only for search_agent, else empty list),
        "reason": "brief explanation"
    }}
    """

    response = llm.invoke(routing_prompt)
    print("\n[MASTER AGENT ROUTING]:", response.content)

    text = str(response.content)
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        try:
            data = json.loads(match.group())
            action = data.get("action", "sales_agent")
            
            # Validate underwriting routing - need user_id and not already checked
            if action == "underwriting_agent":
                if not state.get("user_id") and not user_profile.get("user_id"):
                    print("  → Cannot route to underwriting: no user_id")
                    action = "sales_agent"
                elif state["user_profile"].get("credit_score_checked"):
                    print("  → Already checked credit, routing to sales instead")
                    action = "sales_agent"
            
            # Validate EMI calculator routing
            if action == "emi_calculator":
                required_fields = ["loan_amount", "interest_rate", "tenure"]
                missing = [f for f in required_fields if not user_profile.get(f)]
                if missing:
                    print(f"  → Cannot calculate EMI: missing {missing}")
                    action = "sales_agent"
            
            state["queries"] = data.get("queries", [])
            state["action"] = action
            print(f"  → Final routing: {action}")
            
        except json.JSONDecodeError as e:
            print("Invalid JSON in routing:", e)
            state["action"] = "sales_agent"
            state["queries"] = []
    else:
        print("No JSON found in routing response")
        state["action"] = "sales_agent"
        state["queries"] = []

    return state


def sales_agent(state: State) -> State:
    """
    Sales agent - handles conversation with user.
    Focuses purely on sales, persuasion, and customer service.
    """
    if state.get("count", 0) >= MAX_COUNT:
        print("Max count reached in sales_agent")
        state["action"] = "end"
        return state

    # Gather all context for the sales agent
    search_info = state.get("search_results", "")
    emi_info = state.get("emi_calculation", "")
    credit_info = ""
    
    # Add credit info if available
    if state["user_profile"].get("credit_score"):
        credit_info = f"\nUser's Credit Score: {state['user_profile']['credit_score']}"
    if state["user_profile"].get("pre_approved_amount"):
        credit_info += f"\nPre-approved Amount: ₹{state['user_profile']['pre_approved_amount']}"
    
    # Build comprehensive prompt
    system_prompt = PROMPTS['sales_agent']
    context = f"""
Conversation History:
{state['history']}

User Profile:
{json.dumps(state.get('user_profile', {}), indent=2)}
{credit_info}

"""
    
    if search_info:
        context += f"\nProduct Information (from knowledge base):\n{search_info}\n"
    
    if emi_info:
        context += f"\nEMI Calculation Result:\n{emi_info}\n"
    
    # Sales agent focuses on conversation, not tool calling
    full_prompt = f"""{system_prompt}

{context}

Instructions:
- Respond naturally and persuasively to the user's latest message
- Use the search results and calculations provided above to support your pitch
- Focus on benefits, addressing concerns, and moving towards loan approval
- Ask relevant qualifying questions to gather missing information
- Be empathetic but drive towards closing the deal
- If you need EMI calculations or product info, acknowledge the user and the system will provide it

Generate your response now:"""

    response = llm.invoke(full_prompt)
    
    sales_response = response.content
    print(f"\n[SALES AGENT]: {sales_response}\n")

    # Update state
    state["search_results"] = ""  # Clear search results after use
    state["emi_calculation"] = ""  # Clear EMI calculation after use
    state["history"] += "\nLoan Assistant: " + sales_response
    state["count"] = state.get("count", 0) + 1
    state["action"] = "user_agent"  # Always go to user after sales response

    return state


def search_agent(state: State) -> State:
    """
    Search agent - performs web searches and summarizes results.
    """
    queries = state.get("queries", [])
    
    if len(queries) == 0:
        state["action"] = "sales_agent"
        return state

    overall_search_results = ""
    
    try:
        for query in queries:
            print(f"\n[SEARCH AGENT] Searching for: {query}")
            
            tavily_results = tavily_tool.invoke({
                "query": f"{query} Tata Capital"
            })
            
            tavily_results_formatted = ""
            for result in tavily_results.get("results", []):
                tavily_results_formatted += f"Title: {result['title']}\nContent: {result['content']}\n\n"
            
            if tavily_results_formatted:
                summary = llm.invoke(f"""
                Summarize the following search results into a concise, factual summary.
                
                CRITICAL: Include ALL specific numbers, percentages, fees, requirements, and processes.
                Format the summary clearly with bullet points if multiple items exist.
                
                User Query: {query}
                
                Search Results:
                {tavily_results_formatted}
                
                Provide a well-structured summary:
                """).content
                
                overall_search_results += f"=== {query} ===\n{summary}\n\n"
            else:
                overall_search_results += f"=== {query} ===\nNo specific information found.\n\n"
    
    except Exception as e:
        print(f"[SEARCH ERROR]: {e}")
        overall_search_results = "Search temporarily unavailable."

    state["search_results"] = overall_search_results
    state["queries"] = []  # Clear queries after processing
    state["action"] = "sales_agent"  # Always go to sales after search
    
    print(f"\n[SEARCH COMPLETE] Results:\n{overall_search_results}")
    return state


def emi_calculator_agent(state: State) -> State:
    """
    EMI Calculator agent - calculates EMI and updates state.
    """
    user_profile = state.get("user_profile", {})
    
    loan_amount = user_profile.get("loan_amount")
    interest_rate = user_profile.get("interest_rate")
    tenure = user_profile.get("tenure")
    
    print(f"\n[EMI CALCULATOR] Inputs: Amount={loan_amount}, Rate={interest_rate}, Tenure={tenure}")
    
    try:
        # Call the EMI calculation tool
        result = calculate_emi({
            "loan_amount": float(loan_amount),
            "annual_interest_rate": float(interest_rate),
            "tenure_months": int(tenure)
        })
        
        emi_summary = f"""
EMI Calculation Results:
- Loan Amount: ₹{loan_amount:,}
- Interest Rate: {interest_rate}% p.a.
- Tenure: {tenure} months
- Monthly EMI: ₹{result.get('emi', 0):,.2f}
- Total Payment: ₹{result.get('total_payment', 0):,.2f}
- Total Interest: ₹{result.get('total_interest', 0):,.2f}
"""
        
        state["emi_calculation"] = emi_summary
        print(f"[EMI CALCULATOR] Result:\n{emi_summary}")
        
    except Exception as e:
        print(f"[EMI CALCULATOR ERROR]: {e}")
        state["emi_calculation"] = "Unable to calculate EMI. Please verify the loan details."
    
    state["action"] = "sales_agent"
    return state


def underwriting_agent(state: State) -> State:
    """
    Underwriting agent - fetches credit score and pre-approved amount.
    Only called when user_id exists.
    """
    # Get user_id from either state or profile
    user_id = state.get("user_id") or state["user_profile"].get("user_id")
    
    if not user_id:
        print("[UNDERWRITING WARNING]: Called without user_id")
        state["action"] = "sales_agent"
        return state

    print(f"\n[UNDERWRITING AGENT] Checking credit for user_id: {user_id}")
    
    try:
        credit_score = credit_score_api(user_id)
        pre_approved_amount = pre_approved_amount_api(user_id)
        
        # Update user profile with credit info
        state["user_profile"]["credit_score"] = credit_score
        state["user_profile"]["pre_approved_amount"] = pre_approved_amount
        state["user_profile"]["credit_score_checked"] = True
        
        # Also set user_id in state if it was only in profile
        if not state.get("user_id"):
            state["user_id"] = user_id
        
        print(f"[UNDERWRITING] Results: Credit Score={credit_score}, Pre-approved=₹{pre_approved_amount:,}")
        
        # Add to history so sales agent can reference it
        underwriting_note = f"\n[System Note: Credit check completed - Score: {credit_score}, Pre-approved: ₹{pre_approved_amount:,}]"
        state["history"] += underwriting_note
        
    except Exception as e:
        print(f"[UNDERWRITING ERROR]: {e}")
        state["user_profile"]["credit_score_checked"] = True  # Mark as checked to avoid loops
        state["history"] += f"\n[System Note: Unable to fetch credit information]"

    state["action"] = "sales_agent"  # Route to sales to discuss results
    return state


# Routing functions for conditional edges
def route_after_master(state: State) -> Literal["user_agent", "sales_agent", "search_agent", "underwriting_agent", "emi_calculator", "__end__"]:
    """Route based on action set by master_agent"""
    action = state.get("action", "sales_agent")
    
    if action == "end":
        return "__end__"
    
    # Map to node names
    if action == "emi_calculator":
        return "emi_calculator"
    
    return action


def route_after_sales(state: State) -> Literal["user_agent", "__end__"]:
    """Route after sales agent - either to user or end"""
    if state.get("count", 0) >= MAX_COUNT:
        return "__end__"
    return "user_agent"


def route_after_search(state: State) -> Literal["sales_agent"]:
    """Search always routes to sales"""
    return "sales_agent"


def route_after_underwriting(state: State) -> Literal["sales_agent"]:
    """Underwriting always routes to sales"""
    return "sales_agent"


def route_after_emi(state: State) -> Literal["sales_agent"]:
    """EMI calculator always routes to sales"""
    return "sales_agent"