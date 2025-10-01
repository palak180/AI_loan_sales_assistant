import dotenv
from langgraph.graph import StateGraph, START, END

from agents.user_agent import user_agent
from agents.loan_agents import master_agent, sales_agent, search_agent

from state import State

dotenv.load_dotenv()

graph_builder = StateGraph(State)

graph_builder.add_node("sales_agent", sales_agent)
graph_builder.add_node("user_agent", user_agent)
graph_builder.add_node("search_agent", search_agent)
graph_builder.add_node("master_agent", master_agent)

graph_builder.add_edge(START, "master_agent")

graph = graph_builder.compile()

conversation = graph.invoke({'count':0,'history':'','queries':[],'search_results':'','action':''})
# print(conversation['history'])