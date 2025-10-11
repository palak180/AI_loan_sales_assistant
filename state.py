from typing import TypedDict, Any, Optional, Dict

class State(TypedDict):
    history: str                    # Conversation history
    count: int                      # Message counter for max limit
    search_results: str             # Search results (populated by search, consumed by sales)
    emi_calculation: str            # EMI calculation results (populated by emi_calculator, consumed by sales)
    action: str                     # Next action/agent to route to (populated by all agents)
    user_id: Optional[int]          # User ID for credit checks
    user_profile: Dict[str, Any]    # User profile data extracted from conversation
    feedback: Optional[str]
    last_response: str
    # Example profile fields: name, phone, email, income, employment_type, 
    # loan_amount, loan_type, tenure, interest_rate, credit_score, pre_approved_amount, etc.