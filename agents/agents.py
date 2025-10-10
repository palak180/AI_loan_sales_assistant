from state import State
import json
import re
from typing import Literal
from langgraph.graph import END
from agents.prompts import PROMPTS
from tools.emi_calculator_tool import calculate_emi
from tools.credit_bureau import credit_score_api, pre_approved_amount_api
from llm import llm


MAX_COUNT = 6

def update_user_profile(latest_message: str, current_profile: dict) -> dict:
    """
    Update the user profile based on the latest message using LLM.
    """

    if len(current_profile) == 0:
        prompt = f"""
    You are an expert at creating user profiles for loan applications based on conversation history.

    The latest user message is: "{latest_message}"

    Your task: Create a user profile extracting any relevant information from this message.

    - If a field is present, populate it.
    - If a field is not present, omit it from the JSON (don't fill with null, empty string, or placeholder).
    - If no relevant information can be extracted, return an empty JSON: {{}}

    **Examples:**

    Message: "My name is Rohan and I want a personal loan for 5 lakhs"
    Output: {{"name": "Rohan", "loan_type": "personal", "loan_amount": 500000}}

    Message: "I earn ₹80,000 monthly and have a house valued at ₹40 lakh"
    Output: {{"income": 80000, "property_value": 4000000}}

    Message: "What's the processing fee?"
    Output: {{}}

    Message: "My user ID is 2 and I want a home loan for 35 lakhs, tenure 10 years"
    Output: {{"user_id": 2, "loan_amount": 3500000, "loan_type": "home", "loan_tenure": 120}}

    Now give the result as a strict JSON object.
    """
    else:
        prompt = f"""
    You are an expert at updating user profiles for loan applications based on conversation history.

    The current user profile is: {json.dumps(current_profile, ensure_ascii=False)}
    The latest user message is: "{latest_message}"

    Your task: Make a new user profile with any new information from the latest message.

    - Only add or update fields if clear, explicit new information is present.
    - If the latest message provides no relevant info, return the profile unchanged.
    - **Do not delete or overwrite previously filled fields unless there is definite new info.**
    - Always return the complete profile JSON with relevant (known) fields only.

    **Examples:**

    Current: {{"name": "Rohan Mehta"}}
    Message: "My income is 80,000 per month."
    Output: {{"name": "Rohan Mehta", "income": 80000}}

    Current: {{"loan_amount": 500000}}
    Message: "Processing fee?"
    Output: {{"loan_amount": 500000}}

    Current: {{"loan_amount": 3500000, "loan_type": "home", "loan_tenure": 120}}
    Message: "Yes sure, my user ID is 2"
    Output: {{"user_id": 2, "loan_amount": 3500000, "loan_type": "home", "loan_tenure": 120}}

    Now give only the strictly JSON response.
    """

    response = llm.invoke(prompt)
    text = str(response.content)
    match = re.search(r"\{.*\}", text, re.DOTALL)

    print("Updated profile: ", text, "\n\nEND\n\n")
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

    # PRIORITY CHECK: If we just got a user_id and haven't checked credit, do that FIRST
    user_id = state.get("user_id") or user_profile.get("user_id")
    credit_already_checked = state["user_profile"].get("credit_score_checked")
    
    if user_id and not credit_already_checked:
        print(f"\n[MASTER AGENT] User ID detected ({user_id}), routing to underwriting first")
        state["action"] = "underwriting_agent"
        # Store user_id in state if not already there
        if not state.get("user_id"):
            state["user_id"] = user_id
        return state
    
    # Simple routing decision - just decide WHICH agent, not the details
    routing_prompt = f"""You are a master routing agent for Tata Capital Loans.
    Analyze the user's message and decide which specialized agent should handle it.

    User's latest message: {user_latest_message}
    Current user profile: {json.dumps(user_profile)}

    Routing Rules:
    1. If user asks about loan products, eligibility, interest rates, documents required, fees, processes, terms → route to 'search_agent'
    2. If user asks to calculate EMI/monthly payment AND we have loan_amount AND (interest_rate OR loan_type) AND tenure → route to 'emi_calculator'
    3. Otherwise (greetings, general questions, clarifications, negotiations, follow-ups) → route to 'sales_agent'

    Respond in strict JSON format with just the action:
    {{
        "action": "search_agent" | "emi_calculator" | "sales_agent",
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
    user_id = state.get("user_id") or int(state["user_profile"].get("user_id"))
    
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

        state["user_profile"] = update_user_profile(f"Credit Score: {credit_score}, Pre approved loan limit: {pre_approved_amount}", state["user_profile"])
        
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