from typing import Dict, TypedDict, Optional, List

class Message(TypedDict):
    role: str
    content: str

class State(TypedDict):
    history: str      # Conversation history
    count: int
    queries: List[str]                # Populated by sales_agent, consumed by search_agent
    search_results: str       # Populated by search_agent, consumed by sales_agent
    action: str               # Populated by sales_agent to decide next step