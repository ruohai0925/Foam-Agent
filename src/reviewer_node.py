# reviewer_node.py
import os
from utils import invoke_llm, save_file, read_file, find_input_file, parse_file_name

def reviewer_node(state):
    """
    Reviewer node: Reviews the error logs and determines if the error
    is related to the input file. If yes, triggers a rewrite.
    If the error is fixed, returns control to the InputWriter node
    (targeting the problematic subtask).
    """
    config = state.config
    if not state.error_command:
        print("No error to review.")
        return {"goto": "end"}
    
    # Find the input file corresponding to error_command.
    file_path = find_input_file(state.case_dir, state.error_command)
    if not file_path:
        print(f"Input file for command {state.error_command} not found.")
        return {"goto": "end"}
    
    file_text = read_file(file_path)
    error_file_path = os.path.join(state.case_dir, f"{state.error_command}.err")
    error_content = read_file(error_file_path)
    
    prompt_review = (
        f"The command {state.error_command} produced the following error:\n{error_content}\n"
        f"The corresponding input file ({os.path.basename(file_path)}) content is:\n{file_text}\n"
        f"Analyze if the error is related to the input file.\n"
        f"If yes, return exactly 'yes'. If not, return exactly 'no'.\n"
    )
    review_response = invoke_llm(prompt_review, config)
    review_result = review_response.get("result", "").strip().lower()
    
    if review_result == "yes":
        # Store the error command locally for mapping.
        error_cmd = state.error_command
        prompt_rewrite = (
            f"Rewrite the OpenFOAM file {os.path.basename(file_path)} located in {os.path.dirname(file_path)} to fix the error:\n"
            f"{error_content}\n"
            f"Return the complete modified file content with no extra text.\n"
        )
        rewrite_response = invoke_llm(prompt_rewrite, config)
        rewritten_content = rewrite_response.get("result", "")
        save_file(file_path, rewritten_content)
        
        # Determine which subtask corresponds to this file.
        target_index = None
        for i, subtask in enumerate(state.subtasks):
            fn = parse_file_name(subtask)
            if fn == error_cmd:
                target_index = i
                break
        if target_index is not None:
            state.current_subtask_index = target_index
        else:
            print("Could not match the error command to any subtask. Proceeding without re-generation.")
        
        # Clear the error info.
        state.error_command = None
        state.error_content = None
        return {"goto": "input_writer"}
    else:
        print("Error not related to input file; no changes made.")
        return {"goto": "end"}
