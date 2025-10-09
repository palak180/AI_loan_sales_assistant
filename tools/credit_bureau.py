from agents.prompts import PROMPTS
from langchain.tools import tool

# @tool
def credit_score_api(user_id: int) -> int:
    """
    Fetches the credit score (out of 900) for the given user_id.

    Args:
        user_id (int): The user ID for whom to fetch the credit score.
    Returns:
        int: The credit score (out of 900).
    """
    return PROMPTS[user_id]['credit_score']

# @tool
def pre_approved_amount_api(user_id: int) -> int:
    """
    Fetches the pre-approved loan amount (in INR) for the given user_id.

    Args:
        user_id (int): The user ID for whom to fetch the pre-approved amount.
    Returns:
        int: The pre-approved loan amount (in INR).
    """
    
    return PROMPTS[user_id]['pre-approved_amount']