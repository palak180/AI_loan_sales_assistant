import dotenv
from langgraph.graph import StateGraph, START, END
from agents.user_agent import user_agent
from agents.agents import (
    master_agent, 
    sales_agent, 
    underwriting_agent,
    route_after_master,
    route_after_sales
)
from agents.search_agent import search_agent
from state import State

dotenv.load_dotenv()

# Initialize graph
graph_builder = StateGraph(State)

# Add all nodes
graph_builder.add_node("master_agent", master_agent)
graph_builder.add_node("sales_agent", sales_agent)
graph_builder.add_node("user_agent", user_agent)
graph_builder.add_node("search_agent", search_agent)
graph_builder.add_node("underwriting_agent", underwriting_agent)

# Start always goes to master
graph_builder.add_edge(START, "master_agent")

# Master agent uses conditional routing
graph_builder.add_conditional_edges(
    "master_agent",
    route_after_master,
    {
        "user_agent": "user_agent",
        "sales_agent": "sales_agent",
        "search_agent": "search_agent",
        "underwriting_agent": "underwriting_agent",
        "__end__": END
    }
)

# User agent always goes back to master for routing
graph_builder.add_edge("user_agent", "master_agent")

# Sales agent conditional routing
graph_builder.add_conditional_edges(
    "sales_agent",
    route_after_sales,
    {
        "user_agent": "user_agent",
        "__end__": END
    }
)

# Search agent always goes to sales
graph_builder.add_edge("search_agent", "sales_agent")

# Underwriting agent always goes to sales
graph_builder.add_edge("underwriting_agent", "sales_agent")

# Compile graph
graph = graph_builder.compile()

# Run conversation
if __name__ == "__main__":
    initial_state = {
        'count': 0,
        'history': '',
        'search_results': '',
        'emi_calculation': '',
        'action': '',
        'user_profile': {},
        'user_id': None
    }

    conversation = graph.invoke(initial_state)

    print("\n" + "="*50)
    print("FINAL CONVERSATION HISTORY:")
    print("="*50)
    print(conversation['history'])