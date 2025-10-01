from langchain.tools import tool

@tool
def calculate_emi(principal: float, interest_rate: float, tenure_months: int) -> float:
    """ 
    Calculate the Equated Monthly Installment (EMI) for a loan for given principal, annual interest rate, and tenure in months.
    """
    if tenure_months == 0:
        return 0.0
    monthly_rate = interest_rate / (12 * 100)
    if monthly_rate == 0:
        emi = principal / tenure_months
    else:
        emi = (principal * monthly_rate * (1 + monthly_rate) ** tenure_months) / \
              ((1 + monthly_rate) ** tenure_months - 1)
    return round(emi, 0)
