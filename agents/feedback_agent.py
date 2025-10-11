from state import State
import json
import re
from llm import llm

def feedback_agent(state: State) -> State:
    """
    Feedback agent - provides critique, identifies issues, and suggests improvements
    for the latest response from the sales agent.
    """
    # Extract the most recent sales agent response from the history
    history = state.get("history", "")
    sales_response = state.get("last_response", "")

    # Optionally, access relevant user profile info, context, and previous queries as needed
    user_profile = state.get("user_profile", {})
    search_info = state.get("search_results", "")
    emi_info = state.get("emi_calculation", "")

    # Build prompt for LLM-based feedback or rule-based critique
    feedback_prompt = f"""
You are an expert banking conversation analyst.

Given this user profile: 
{json.dumps(user_profile, indent=2)}

Chat uptil now:
{history}

Product information (if any): {search_info}

Here is the latest sales agent response:
\"\"\"{sales_response}\"\"\"

Your tasks:
- Identify any missing details, mistakes, or areas for improvement
- Point out if the response could be more persuasive, clear, or customer-focused
- Flag factual errors, incompleteness, or missed information
- Suggest exactly how the sales agent can improve
- Write your feedback as precise bullet points starting with 'Suggestion:' or 'Issue:'.

Output your feedback now:
"""

    # Call LLM for feedback analysis
    feedback_response = llm.invoke(feedback_prompt)
    feedback = feedback_response.content
    print(f"\n[FEEDBACK AGENT]: {feedback}\n")

    # Optionally, append feedback to state for agent improvement or further prompting
    state["feedback"] = feedback

    # You may choose what the next action/agent should be (e.g., sales_agent rework, move to user, etc.)
    # This example always gives feedback then sets 'action' to 'user_agent'
    state["action"] = "sales_agent"
    return state
