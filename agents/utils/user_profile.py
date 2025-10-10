import re
import json
from llm import llm

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
    - If you find user Id in the message be sure to add it as a field.

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
    - Do not delete or overwrite previously filled fields unless there is definite new info.
    - Always return the complete profile JSON with relevant (known) fields only.
    - If you find user Id in the message be sure to add it as a field.

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

