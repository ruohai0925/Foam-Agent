# runner_node.py
from typing import List
import os
from pydantic import BaseModel, Field
import re
from utils import (
    save_file, remove_files, remove_file,
    run_command, check_foam_errors, retrieve_faiss, remove_numeric_folders
)
from services.run_local import run_allrun_and_collect_errors


def local_runner_node(state):
    """
    Runner node: Execute an Allrun script, and check for errors.
    On error, update state.error_command and state.error_content.
    """
    config = state["config"]
    case_dir = state["case_dir"]
    allrun_file_path = os.path.join(case_dir, "Allrun")
    
    print(f"============================== Runner ==============================")
    
    # Execute using service and collect errors
    error_logs = run_allrun_and_collect_errors(case_dir, config)

    if len(error_logs) > 0:
        print("Errors detected in the Allrun execution.")
        print(error_logs)
    else:
        print("Allrun executed successfully without errors.")
    
    state['loop_count'] += 1
    # Return updated state
    return {
        **state,
        "error_logs": error_logs
    }
        