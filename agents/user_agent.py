import dotenv
from langchain_groq import ChatGroq
from agents.prompts import USERS
from state import State
from langgraph.types import Command
from typing import Literal
from langgraph.graph import END


dotenv.load_dotenv()

llm = ChatGroq(model="llama-3.1-8b-instant")

MAX_COUNT = 6

def user_agent(state: State) -> Command[Literal["master_agent", END]]:
    if state.get("count", 0) >= MAX_COUNT:
        print("Stopping conversation at sales_agent due to max count")
        return Command(goto=END, update=state)
    
    messages = "Your role: " + USERS[2]['description'] + "\nHistory: " + state["history"] + "\nRespond appropriately as the user."
    response = llm.invoke(messages)

    print("\n\nUser:", response.content)

    new_state = state.copy()
    new_state["history"] += "\nUser: " + response.content
    new_state["count"] = state.get("count", 0) + 1

    return Command(goto="master_agent", update=new_state)