import os
from typing import Dict, List
from utils import save_file, parse_context, retrieve_faiss, FoamPydantic, FoamfilePydantic
from services.files import generate_file_content
import re


def compute_priority(subtask):
    if subtask["folder_name"] == "system":
        return 0
    elif subtask["folder_name"] == "constant":
        return 1
    elif subtask["folder_name"] == "0":
        return 2
    else:
        return 3


def initial_write(llm, case_dir: str, subtasks: List[Dict], user_requirement: str, tutorial_reference: str, case_solver: str, file_dependency_flag: bool) -> Dict:
    subtasks = sorted(subtasks, key=compute_priority)
    written_files = []
    dir_structure = {}

    for subtask in subtasks:
        file_name = subtask["file_name"]
        folder_name = subtask["folder_name"]
        if folder_name not in dir_structure:
            dir_structure[folder_name] = []
        dir_structure[folder_name].append(file_name)

        inp = type("GenIn", (), {"file": file_name, "folder": folder_name, "write": True, "overwrite": True})
        out = generate_file_content(inp, llm, case_dir, tutorial_reference, case_solver)
        written_files.append(FoamfilePydantic(file_name=file_name, folder_name=folder_name, content=out.content))

    foamfiles = FoamPydantic(list_foamfile=written_files)
    return {"dir_structure": dir_structure, "foamfiles": foamfiles}


def build_allrun(llm, case_dir: str, config, dir_structure: Dict, case_info: str, allrun_reference: str, mesh_type: str, mesh_commands: List[str]) -> Dict:
    command_path = f"{config.database_path}/raw/openfoam_commands.txt"
    with open(command_path, 'r') as file:
        commands = file.readlines()
    commands = f"[{', '.join([c.strip() for c in commands])}]"

    mesh_commands_info = ""
    if mesh_type == "custom_mesh" and mesh_commands:
        mesh_commands_info = f"\nCustom mesh commands to include: {mesh_commands}"

    command_system_prompt = (
        "You are an expert in OpenFOAM. The user will provide a list of available commands. "
        "Your task is to generate only the necessary OpenFOAM commands required to create an Allrun script for the given user case, based on the provided directory structure. "
        "Return only the list of commands—no explanations, comments, or additional text."
    )
    if mesh_type == "custom_mesh":
        command_system_prompt += "If custom mesh commands are provided, include them in the appropriate order. "

    command_user_prompt = (
        f"Available OpenFOAM commands for the Allrun script: {commands}\n"
        f"Case directory structure: {dir_structure}\n"
        f"User case information: {case_info}\n"
        f"Reference Allrun scripts from similar cases: {allrun_reference}\n"
        "Generate only the required OpenFOAM command list—no extra text."
    )
    command_response = llm.invoke(command_user_prompt, command_system_prompt)

    allrun_system_prompt = (
        "You are an expert in OpenFOAM. Generate an Allrun script based on the provided details."
        f"Available commands with descriptions: {commands}\n\n"
        f"Reference Allrun scripts from similar cases: {allrun_reference}\n\n"
        "CRITICAL: Do not include any post processing commands in the Allrun script."
        "CRITICAL: Do not include any commands to convert mesh to foam format like gmshToFoam or others."
    )
    if mesh_type == "custom_mesh":
        allrun_system_prompt += "CRITICAL: Include custom mesh commands where appropriate."

    allrun_user_prompt = (
        f"Case directory structure: {dir_structure}\n"
        f"User case infomation: {case_info}\n"
        f"{mesh_commands_info}\n"
        "Generate the Allrun script strictly based on the above information. Do not include explanations, comments, or additional text. Put the code in ``` tags."
    )
    allrun_response = llm.invoke(allrun_user_prompt, allrun_system_prompt)
    match = re.search(r'```(.*?)```', allrun_response, re.DOTALL)
    script = match.group(1).strip() if match else allrun_response
    allrun_file_path = os.path.join(case_dir, "Allrun")
    save_file(allrun_file_path, script)
    return {"allrun_path": allrun_file_path, "allrun_script": script}



def rewrite_files(llm, case_dir: str, foamfiles, error_logs, review_analysis, user_requirement: str, dir_structure: Dict) -> Dict:
    """Rewrite OpenFOAM files based on reviewer analysis using LLM and return updated structures.

    Returns a dict with keys: dir_structure, foamfiles, error_logs (cleared on success).
    """
    from utils import FoamPydantic, FoamfilePydantic  # local import to avoid cycles
    import re
    import os

    rewrite_system_prompt = (
        "You are an expert in OpenFOAM simulation and numerical modeling. "
        "Your task is to modify and rewrite the necessary OpenFOAM files to fix the reported error. "
        "Please do not propose solutions that require modifying any parameters declared in the user requirement, try other approaches instead."
        "The user will provide the error content, error command, reviewer's suggestions, and all relevant foam files. "
        "Only return files that require rewriting, modification, or addition; do not include files that remain unchanged. "
        "Return the complete, corrected file contents in the following JSON format: "
        "list of foamfile: [{file_name: 'file_name', folder_name: 'folder_name', content: 'content'}]. "
        "Ensure your response includes only the modified file content with no extra text, as it will be parsed using Pydantic."
    )

    rewrite_user_prompt = (
        f"<foamfiles>{str(foamfiles)}</foamfiles>\n"
        f"<error_logs>{error_logs}</error_logs>\n"
        f"<reviewer_analysis>{review_analysis}</reviewer_analysis>\n\n"
        f"<user_requirement>{user_requirement}</user_requirement>\n\n"
        "Please update the relevant OpenFOAM files to resolve the reported errors, ensuring that all modifications strictly adhere to the specified formats. Ensure all modifications adhere to user requirement."
    )

    response = llm.invoke(rewrite_user_prompt, rewrite_system_prompt, pydantic_obj=FoamPydantic)

    # Prepare updated structures
    updated_dir = dict(dir_structure) if dir_structure else {}
    foamfiles_list = list(foamfiles.list_foamfile) if foamfiles and hasattr(foamfiles, "list_foamfile") else []

    for foamfile in response.list_foamfile:
        file_path = os.path.join(case_dir, foamfile.folder_name, foamfile.file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        save_file(file_path, foamfile.content)

        if foamfile.folder_name not in updated_dir:
            updated_dir[foamfile.folder_name] = []
        if foamfile.file_name not in updated_dir[foamfile.folder_name]:
            updated_dir[foamfile.folder_name].append(foamfile.file_name)

        foamfiles_list = [
            f for f in foamfiles_list
            if not (f.folder_name == foamfile.folder_name and f.file_name == foamfile.file_name)
        ]
        foamfiles_list.append(foamfile)

    updated_foamfiles = FoamPydantic(list_foamfile=foamfiles_list)
    return {
        "dir_structure": updated_dir,
        "foamfiles": updated_foamfiles,
        "error_logs": [],
    }

