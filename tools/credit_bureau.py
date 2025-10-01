from agents.prompts import PROMPTS
from langchain.tools import tool

@tool
def credit_score_api(user_id: int) -> int:
    return PROMPTS[user_id]['credit_score']

@tool
def pre_approved_amount_api(user_id: int) -> int:
    return PROMPTS[user_id]['pre-approved_amount']