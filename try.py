import operator
from typing import Annotated, TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama

# 1. Define the Shared Notebook (State)
class AgentState(TypedDict):
    topic: str
    draft: str
    critique: str
    iteration: Annotated[int, operator.add]
    is_finished: bool

# 2. Initialize the "Brain" (Your 5070 Ti)
# Using temperature 0 for factual research accuracy
llm = ChatOllama(model="deepseek-r1:32b", temperature=0)

# 3. Define the Worker Nodes
def research_node(state: AgentState):
    print(f"--- Iteration {state['iteration'] + 1}: Researching ---")
    prompt = f"Provide a detailed technical summary on: {state['topic']}. Current draft: {state['draft']}"
    response = llm.invoke(prompt)
    # We return a dict to update the state
    return {"draft": response.content, "iteration": 1}

def critique_node(state: AgentState):
    print("--- Critiquing Research ---")
    prompt = f"Critique this research for technical accuracy: {state['draft']}. Is it complete? Answer only YES or NO."
    response = llm.invoke(prompt)
    finished = "YES" in response.content.upper()
    return {"critique": response.content, "is_finished": finished}

# 4. Build the Flowchart (The Graph)
workflow = StateGraph(AgentState)

workflow.add_node("researcher", research_node)
workflow.add_node("critic", critique_node)

workflow.set_entry_point("researcher")
workflow.add_edge("researcher", "critic")

# THE LOOP: If not finished and under 3 tries, go back to researcher
workflow.add_conditional_edges(
    "critic",
    lambda x: "researcher" if not x["is_finished"] and x["iteration"] < 3 else END
)

# 5. Compile and Run
app = workflow.compile()
initial_state = {"topic": "Blackwell Architecture 5070 Ti performance", "draft": "", "iteration": 0, "is_finished": False}

print("Starting Agentic Loop...")
for output in app.stream(initial_state):
    print(output)