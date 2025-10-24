import os
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field
from utils import retrieve_faiss, parse_directory_structure


class CaseSummaryModel(BaseModel):
    case_name: str = Field(description="name of the case")
    case_domain: str = Field(description="domain of the case")
    case_category: str = Field(description="category of the case")
    case_solver: str = Field(description="solver of the case")


class SubtaskModel(BaseModel):
    file_name: str
    folder_name: str


class OpenFOAMPlanModel(BaseModel):
    subtasks: List[SubtaskModel]


def parse_requirement_to_case_info(user_requirement: str, case_stats: Dict, llm) -> Dict:
    parse_system_prompt = (
        "Please transform the following user requirement into a standard case description using a structured format."
        "The key elements should include case name, case domain, case category, and case solver."
        f"Note: case domain must be one of {case_stats.get('case_domain', [])}."
        f"Note: case category must be one of {case_stats.get('case_category', [])}."
        f"Note: case solver must be one of {case_stats.get('case_solver', [])}."
    )
    parse_user_prompt = f"User requirement: {user_requirement}."
    res = llm.invoke(parse_user_prompt, parse_system_prompt, pydantic_obj=CaseSummaryModel)
    return {
        "case_name": res.case_name.replace(" ", "_"),
        "case_domain": res.case_domain,
        "case_category": res.case_category,
        "case_solver": res.case_solver,
    }


def resolve_case_dir(config, case_name: str) -> str:
    if getattr(config, "case_dir", ""):
        case_dir = config.case_dir
    else:
        if getattr(config, "run_times", 1) > 1:
            case_dir = os.path.join(str(config.run_directory), f"{case_name}_{config.run_times}")
        else:
            case_dir = os.path.join(str(config.run_directory), case_name)
    return case_dir


def retrieve_references(case_name: str, case_solver: str, case_domain: str, case_category: str, config, llm) -> Tuple[str, str, str, bool]:
    # Build case_info
    case_info = f"case name: {case_name}\ncase domain: {case_domain}\ncase category: {case_category}\ncase solver: {case_solver}"
    faiss_structure = retrieve_faiss("openfoam_tutorials_structure", case_info, topk=config.searchdocs)
    faiss_structure = faiss_structure[0]['full_content']
    faiss_structure = re.sub(r"\n{3}", '\n', faiss_structure)
    faiss_detailed = retrieve_faiss("openfoam_tutorials_details", faiss_structure, topk=config.searchdocs)
    faiss_detailed = faiss_detailed[0]['full_content']

    file_dependency_flag = True
    if (faiss_detailed.count('\n') >= config.file_dependency_threshold):
        file_dependency_flag = False

    dir_structure = re.search(r"<directory_structure>(.*?)</directory_structure>", faiss_detailed, re.DOTALL).group(1).strip()
    dir_counts = parse_directory_structure(dir_structure)
    dir_counts_str = ',\n'.join([f"There are {count} files in Directory: {directory}" for directory, count in dir_counts.items()])

    # Build allrun reference
    index_content = f"<index>\ncase name: {case_name}\ncase solver: {case_solver}\n</index>\n<directory_structure>\n{dir_structure}\n</directory_structure>"
    faiss_allrun = retrieve_faiss("openfoam_allrun_scripts", index_content, topk=config.searchdocs)
    allrun_reference = "Similar cases are ordered, with smaller numbers indicating greater similarity. For example, similar_case_1 is more similar than similar_case_2, and similar_case_2 is more similar than similar_case_3.\n"
    for idx, item in enumerate(faiss_allrun):
        allrun_reference += f"<similar_case_{idx + 1}>{item['full_content']}</similar_case_{idx + 1}>\n\n\n"

    return faiss_detailed, dir_structure, dir_counts_str, allrun_reference, file_dependency_flag


def decompose_to_subtasks(user_requirement: str, dir_structure: str, dir_counts_str: str, llm) -> List[Dict]:
    decompose_system_prompt = (
        "You are an experienced Planner specializing in OpenFOAM projects. "
        "Your task is to break down the following user requirement into a series of smaller, manageable subtasks. "
        "For each subtask, identify the file name of the OpenFOAM input file (foamfile) and the corresponding folder name where it should be stored. "
        "Your final output must strictly follow the JSON schema below and include no additional keys or information:\n\n"
        "```\n{\n  \"subtasks\": [\n    {\n      \"file_name\": \"<string>\",\n      \"folder_name\": \"<string>\"\n    }\n    // ... more subtasks\n  ]\n}\n```\n\n"
        "Make sure that your output is valid JSON and strictly adheres to the provided schema."
        "Make sure you generate all the necessary files for the user's requirements."
    )

    decompose_user_prompt = (
        f"User Requirement: {user_requirement}\n\n"
        f"Reference Directory Structure (similar case): {dir_structure}\n\n{dir_counts_str}\n\n"
        "Make sure you generate all the necessary files for the user's requirements."
        "Do not include any gmsh files like .geo etc. in the subtasks."
        "Only include blockMesh or snappyHexMesh if the user hasnt requested for gmsh mesh or user isnt using an external uploaded custom mesh"
        "Please generate the output as structured JSON."
    )

    res = llm.invoke(decompose_user_prompt, decompose_system_prompt, pydantic_obj=OpenFOAMPlanModel)
    return [{"file_name": s.file_name, "folder_name": s.folder_name} for s in res.subtasks]


