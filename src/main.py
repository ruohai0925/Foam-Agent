from dataclasses import dataclass, field
from typing import List, Optional, TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
import argparse
from pathlib import Path
from utils import LLMService

from config import Config
from architect_node import architect_node
from input_writer_node import input_writer_node
from runner_node import runner_node
from reviewer_node import reviewer_node
import json

class GraphState(TypedDict):
    user_requirement: str
    config: Config
    case_dir: str
    tutorial: str
    case_name: str
    subtasks: List[dict]
    current_subtask_index: int
    error_command: Optional[str]
    error_content: Optional[str]
    loop_count: int
    # Additional state fields that will be added during execution
    llm_service: Optional[LLMService]
    case_stats: Optional[dict]
    tutorial_reference: Optional[str]
    case_path_reference: Optional[str]
    dir_structure_reference: Optional[str]
    case_info: Optional[str]
    allrun_reference: Optional[str]
    dir_structure: Optional[dict]
    commands: Optional[List[str]]
    foamfiles: Optional[dict]
    error_logs: Optional[List[str]]
    history_text: Optional[List[str]]
    case_domain: Optional[str]
    case_category: Optional[str]
    case_solver: Optional[str]

def create_foam_agent_graph() -> StateGraph:
    """Create the OpenFOAM agent workflow graph."""
    
    # Create the graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("architect", architect_node)
    workflow.add_node("input_writer", input_writer_node)
    workflow.add_node("runner", runner_node)
    workflow.add_node("reviewer", reviewer_node)
    
    # Define the routing logic
    def route_after_architect(state: GraphState):
        return "input_writer"
    
    def route_after_input_writer(state: GraphState):
        return "runner"
    
    def route_after_runner(state: GraphState):
        if state.get("error_logs") and len(state["error_logs"]) > 0:
            return "reviewer"
        else:
            return END
    
    def route_after_reviewer(state: GraphState):
        loop_count = state.get("loop_count", 0)
        max_loop = state["config"].max_loop
        if loop_count >= max_loop:
            print(f"Maximum loop count ({max_loop}) reached. Ending workflow.")
            return END
        if state.get("error_logs") and len(state["error_logs"]) > 0:
            state["loop_count"] = loop_count + 1
            print(f"Loop {loop_count + 1}: Continuing to fix errors.")
            return "input_writer"
        else:
            print("No more errors to fix. Ending workflow.")
            return END
    
    # Add edges
    workflow.add_edge(START, "architect")
    workflow.add_conditional_edges("architect", route_after_architect)
    workflow.add_conditional_edges("input_writer", route_after_input_writer)
    workflow.add_conditional_edges("runner", route_after_runner)
    workflow.add_conditional_edges("reviewer", route_after_reviewer)
    
    return workflow

def initialize_state(user_requirement: str, config: Config) -> GraphState:
    """Initialize the graph state with required data."""
    # Load case statistics
    case_stats = json.load(open(f"{config.database_path}/raw/openfoam_case_stats.json", "r"))
    
    # Create initial state
    state = GraphState(
        user_requirement=user_requirement,
        config=config,
        case_dir="",
        tutorial="",
        case_name="",
        subtasks=[],
        current_subtask_index=0,
        error_command=None,
        error_content=None,
        loop_count=0,
        llm_service=LLMService(config),
        case_stats=case_stats,
        tutorial_reference=None,
        case_path_reference=None,
        dir_structure_reference=None,
        case_info=None,
        allrun_reference=None,
        dir_structure=None,
        commands=None,
        foamfiles=None,
        error_logs=None,
        history_text=None,
        case_domain=None,
        case_category=None,
        case_solver=None
    )
    
    return state

def main(user_requirement: str, config: Config):
    """Main function to run the OpenFOAM workflow using LangGraph."""
    
    # Create and compile the graph
    workflow = create_foam_agent_graph()
    app = workflow.compile()
    
    # Initialize the state
    initial_state = initialize_state(user_requirement, config)
    
    print("Starting OpenFOAM workflow with LangGraph...")
    
    # Invoke the graph
    try:
        result = app.invoke(initial_state)
        print("Workflow completed successfully!")
        
        # Print final statistics
        if result.get("llm_service"):
            result["llm_service"].print_statistics()
        
        print(f"Final state: {result}")
        
    except Exception as e:
        print(f"Workflow failed with error: {e}")
        raise

if __name__ == "__main__":
    # python main.py
    parser = argparse.ArgumentParser(
        description="Run the OpenFOAM workflow"
    )
    parser.add_argument(
        "--prompt_path",
        type=str,
        default=f"{Path(__file__).parent.parent}/user_requirement.txt",
        help="User requirement file path for the workflow.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="",
        help="Output directory for the workflow.",
    )
    
    args = parser.parse_args()
    print(args)
    
    # Initialize configuration.
    config = Config()
    if args.output_dir != "":
        config.case_dir = args.output_dir
    
    with open(args.prompt_path, 'r') as f:
        user_requirement = f.read()
    
    main(user_requirement, config)
