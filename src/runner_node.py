# runner_node.py
from typing import List
import os
from pydantic import BaseModel, Field
import re
from utils import (
    invoke_llm, save_file, remove_files, remove_file,
    run_command, check_foam_errors, retrieve_faiss, remove_numeric_folders
)


def runner_node(state):
    """
    Runner node: Generate an Allrun script, execute it, and check for errors.
    On error, update state.error_command and state.error_content.
    """
    config = state.config
    case_dir = state.case_dir
    allrun_file_path = os.path.join(case_dir, "Allrun")
    
    print(f"============================== Runner ==============================")
    
    # Clean up any previous log and error files.
    out_file = os.path.join(case_dir, "Allrun.out")
    err_file = os.path.join(case_dir, "Allrun.err")
    remove_files(case_dir, prefix="log")
    remove_file(err_file)
    remove_file(out_file)
    remove_numeric_folders(case_dir)
    
    # Execute the Allrun script.
    run_command(allrun_file_path, out_file, err_file, case_dir, config)
    
    # Check for errors.
    state.error_logs = check_foam_errors(case_dir)

    if len(state.error_logs) > 0:
        print("Errors detected in the Allrun execution.")
        print(state.error_logs)
        return {"goto": "reviewer"}
    else:
        print("Allrun executed successfully without errors.")
        return {"goto": "end"}
        
