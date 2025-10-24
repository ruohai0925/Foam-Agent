import os
from models import GenerateFileIn, GenerateFileOut
from utils import save_file, parse_context


def generate_file_content(inp: GenerateFileIn, llm, case_dir: str, tutorial_reference: str, case_solver: str) -> GenerateFileOut:
    """Generate a single OpenFOAM file content and optionally write it.

    This wraps the initial-write logic in a stateless, file-focused function.
    """
    sys_prompt = (
        "You are an expert in OpenFOAM simulation and numerical modeling. "
        "Your task is to generate a complete and functional file named: "
        f"<file_name>{inp.file}</file_name> within the <folder_name>{inp.folder}</folder_name> directory. "
        "Ensure all required values are present and consistent across files. "
        "Before finalizing the output, ensure: "
        "- All necessary fields exist and are used consistently. "
        "- Cross-check field names between different files to avoid mismatches. "
        "- Ensure units and dimensions are correct. "
        f"- Ensure case solver settings are consistent with the user's requirements. Available solvers are: {case_solver}. "
        "Provide only the code—no explanations, comments, or additional text."
    )
    user_prompt = (
        f"<similar_case_reference>{tutorial_reference}</similar_case_reference>\n"
        f"Generate {inp.folder}/{inp.file} consistent with the reference."
    )
    response = llm.invoke(user_prompt, sys_prompt)
    content = parse_context(response)
    written_path = None
    if inp.write:
        file_path = os.path.join(case_dir, inp.folder, inp.file)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if os.path.exists(file_path) and not inp.overwrite:
            # Do not overwrite; just return the generated content
            written_path = None
        else:
            save_file(file_path, content)
            written_path = file_path
    return GenerateFileOut(content=content, written_path=written_path)


