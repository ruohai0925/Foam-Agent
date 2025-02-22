# input_writer_node.py
import os
from utils import (invoke_llm, save_file, parse_context)
from typing import List
from pydantic import BaseModel, Field


class FoamfilePydantic(BaseModel):
    file_name: str = Field(description="Name of the OpenFOAM input file")
    folder_name: str = Field(description="Folder where the foamfile should be stored")
    content: str = Field(description="Content of the OpenFOAM file, written in OpenFOAM dictionary format")

class FoamPydantic(BaseModel):
    list_foamfile: List[FoamfilePydantic] = Field(description="List of OpenFOAM configuration files")

def compute_priority(subtask):
    if subtask.folder_name == "constant":
        return 0
    elif subtask.folder_name == "system":
        return 1
    elif subtask.folder_name == "0":
        return 2
    else:
        return 3
        

def input_writer_node(state):
    """
    InputWriter node: Generate the complete OpenFOAM foamfile.
    """
    config = state.config
    subtasks = state.subtasks
    
    subtasks = sorted(subtasks, key=compute_priority)
    
    writed_files = ""
    dir_structure = {}
    
    for subtask in subtasks:
        file_name = subtask.file_name
        folder_name = subtask.folder_name
        
        if folder_name not in dir_structure:
            dir_structure[folder_name] = []
        dir_structure[folder_name].append(file_name)
        
        print(f"Generating file: {file_name} in folder: {folder_name}")
        
        if not file_name or not folder_name:
            raise ValueError(f"Invalid subtask format: {subtask}")

        file_path = os.path.join(state.case_dir, folder_name, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Retrieve a similar reference foamfile from the tutorial.
        similar_file_text = state.tutorial_reference
        
        # Generate the complete foamfile.
        code_system_prompt = (
            "You are an expert in OpenFOAM simulation and numerical modeling."
            f"Your task is to generate a complete and functional file named: <file_name>{file_name}</file_name> within the <folder_name>{folder_name}</folder_name> directory. "
            "Ensure all required values are present and match with the files content already generated."
            "Before finalizing the output, ensure:"
            "- All necessary fields exist (e.g., if `nu` is defined in `constant/transportProperties`, it must be used correctly in `0/U`)."
            "- Cross-check field names between different files to avoid mismatches."
            "- Ensure units and dimensions are correct** for all physical variables."
            "Provide only the code—no explanations, comments, or additional text."
        )

        code_user_prompt = (
            f"User requirement: {state.user_requirement}\n"
            f"Refer to the following similar case file content to ensure the generated file aligns with the user requirement:\n{similar_file_text}\n"
            "Please ensure that the generated file is complete, functional, and logically sound."
            f"The following are files content already generated: {writed_files}\n\n"
            "Additionally, apply your domain expertise to verify that all numerical values are consistent with the user's requirements, maintaining accuracy and coherence."
        )

        generation_response = invoke_llm(config, code_user_prompt, code_system_prompt)
        
        code_context = parse_context(generation_response.content)
        save_file(file_path, code_context)
        
        writed_files += f"<file>file_name: {file_name}, folder_name: {folder_name}, file content: {code_context}</file>\n"
    
    state.dir_structure = dir_structure

    return {"goto": "runner"}
