# main.py
from dataclasses import dataclass, field
from typing import List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
import argparse
from pathlib import Path

from config import Config
from architect_node import architect_node
from input_writer_node import input_writer_node
from runner_node import runner_node
from reviewer_node import reviewer_node
import json

@dataclass
class GraphState:
    user_requirement: str
    config: Config
    case_dir: str = ""
    tutorial: str = ""
    case_name: str = ""
    subtasks: List[str] = field(default_factory=list)
    current_subtask_index: int = 0
    error_command: Optional[str] = None
    error_content: Optional[str] = None
    loop_count: int = 0

def main(user_requirement: str):
    # Initialize configuration.
    config = Config()

    # Create the initial state.
    state = GraphState(user_requirement=user_requirement, config=config)
    
    state.case_stats = json.load(open(f"{state.config.database_path}/raw/openfoam_case_stats.json", "r"))
    
    architect_node(state)
    
    input_writer_node(state)
    
    runner_node(state)
    
    # reviewer_node(state)
    
    print(state)
    
    
    
    # # Build the state graph.
    # graph_builder = StateGraph(GraphState)
    # graph_builder.add_node("architect", architect_node)
    # graph_builder.add_node("input_writer", input_writer_node)
    # graph_builder.add_node("runner", runner_node)
    # graph_builder.add_node("reviewer", reviewer_node)
    
    # # Define edges.
    # graph_builder.add_edge(START, "architect")
    # graph_builder.add_edge("architect", "input_writer")
    # graph_builder.add_edge("input_writer", "runner")
    # graph_builder.add_edge("runner", "reviewer")
    # # From reviewer, if an error was fixed, go back to input_writer; otherwise, finish.
    # graph_builder.add_edge("reviewer", "input_writer")
    # graph_builder.add_edge("reviewer", END)
    # # Also, if runner finds no error, we go to END.
    # graph_builder.add_edge("runner", END)
    
    # # Compile and run the graph.
    # graph = graph_builder.compile()


    # print("Workflow finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the OpenFOAM workflow."
    )
    parser.add_argument(
        "--prompt_path",
        type=str,
        default=f"{Path(__file__).parent.parent}/demo_prompt.txt",
        help="User requirement file path for the workflow.",
    )
    
    args = parser.parse_args()
    
    with open(args.prompt_path, 'r') as f:
        user_requirement = f.read()
    
    main(user_requirement)
