# runner_node.py
from typing import List
import os
from pydantic import BaseModel, Field
import re
from utils import (
    invoke_llm, save_file, remove_files, remove_file,
    run_command, check_foam_errors, retrieve_faiss
)


class CommandsPydantic(BaseModel):
    commands: List[str] = Field(description="List of commands")

def parse_allrun(text: str) -> str:
    match = re.search(r'```(.*?)```', text, re.DOTALL)
    
    return match.group(1).strip() 

def retrieve_commands(command_path) -> str:
    with open(command_path, 'r') as file:
        commands = file.readlines()
    
    return f"[{', '.join([command.strip() for command in commands])}]"
    

def runner_node(state):
    """
    Runner node: Generate an Allrun script, execute it, and check for errors.
    On error, update state.error_command and state.error_content.
    """
    config = state.config
    case_dir = state.case_dir
    allrun_file_path = os.path.join(case_dir, "Allrun")
    if os.path.exists(allrun_file_path):
        print("Warning: Allrun file exists. Overwriting.")
    
    # Retrieve available commands from the FAISS "Commands" database.
    commands = retrieve_commands(f"{state.config.database_path}/raw/openfoam_commands.txt")
    
    command_system_prompt = (
        "You are an expert in OpenFOAM. The user will provide a list of available commands. "
        "Your task is to generate only the necessary OpenFOAM commands required to create an Allrun script for the given user case, based on the provided directory structure. "
        "Return only the list of commands—no explanations, comments, or additional text."
    )
    
    command_user_prompt = (
        f"Available OpenFOAM commands for the Allrun script: {commands}\n"
        f"Case directory structure: {state.dir_structure}\n"
        f"User case information: {state.case_info}\n"
        f"Reference Allrun scripts from similar cases: {state.allrun_reference}\n"
        "Generate only the required OpenFOAM command list—no extra text."
    )
    
    command_response = invoke_llm(config, command_user_prompt, command_system_prompt, pydantic_obj=CommandsPydantic)

    if len(command_response.commands) == 0:
        print("Failed to generate subtasks.")
        raise ValueError("Failed to generate subtasks.")

    print(f"Need {len(command_response.commands)} commands.")
    
    state.commands = command_response.commands
    
    commands_help = []
    for command in command_response.commands:
        command_help = retrieve_faiss("openfoam_command_help", command, topk=state.config.searchdocs)
        commands_help.append(command_help[0]['full_content'])
    commands_help = "\n".join(commands_help)


    allrun_system_prompt = (
        "You are an expert in OpenFOAM. Generate an Allrun script based on the provided details."
        f"Available commands with descriptions: {commands_help}\n\n"
        f"Reference Allrun scripts from similar cases: {state.allrun_reference}\n\n"
    )
    
    allrun_user_prompt = (
        f"User requirement: {state.user_requirement}\n"
        f"Case directory structure: {state.dir_structure}\n"
        f"User case infomation: {state.case_info}\n"
        "All run scripts for these similar cases are for reference only and may not be correct, as you might be a different case solver or have a different directory structure. " 
        "You need to rely on your OpenFOAM and physics knowledge to discern this, and pay more attention to user requirements, " 
        "as your ultimate goal is to fulfill the user's requirements and generate an allrun script that meets those requirements."
        "Generate the Allrun script strictly based on the above information. Do not include explanations, comments, or additional text. Put the code in ``` tags."
    )
    
    allrun_response = invoke_llm(config, allrun_user_prompt, allrun_system_prompt)
    
    allrun_script = parse_allrun(allrun_response.content)
    save_file(allrun_file_path, allrun_script)
    
    # Clean up any previous log and error files.
    out_file = os.path.join(case_dir, "Allrun.out")
    err_file = os.path.join(case_dir, "Allrun.err")
    remove_files(case_dir, prefix="log")
    remove_file(err_file)
    remove_file(out_file)
    
    # Execute the Allrun script.
    run_command(allrun_file_path, out_file, err_file, case_dir)
    
    # Check for errors.
    state.error_logs = check_foam_errors(case_dir)

    if len(state.error_logs) > 0:
        print("Errors detected in the Allrun execution.")
        print(state.error_logs)
        return {"goto": "reviewer"}
    else:
        print("Allrun executed successfully without errors.")
        return {"goto": "end"}
        
