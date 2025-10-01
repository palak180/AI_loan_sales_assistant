from agents.prompts import PROMPTS
from langchain.tools import tool

@tool
def credit_score_api(user_id: int) -> int:
    """
    Fetches the credit score (out of 900) for the given user_id.
    """
    return PROMPTS[user_id]['credit_score']

@tool
def pre_approved_amount_api(user_id: int) -> int:
    """
    Fetches the pre-approved loan amount (in INR) for the given user_id.
    """
    return PROMPTS[user_id]['pre-approved_amount']