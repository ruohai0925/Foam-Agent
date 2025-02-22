# utils.py
import re
import subprocess
import os
from typing import Optional, Any, Type
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain_community.vectorstores import FAISS
from langchain_openai.embeddings import OpenAIEmbeddings
from pathlib import Path

# Global dictionary to store loaded FAISS databases
FAISS_DB_CACHE = {}
DATABASE_DIR = f"{Path(__file__).resolve().parent.parent}/database/faiss"

FAISS_DB_CACHE = {
    "openfoam_allrun_scripts": FAISS.load_local(f"{DATABASE_DIR}/openfoam_allrun_scripts", OpenAIEmbeddings(model="text-embedding-3-small"), allow_dangerous_deserialization=True),
    "openfoam_tutorials_structure": FAISS.load_local(f"{DATABASE_DIR}/openfoam_tutorials_structure", OpenAIEmbeddings(model="text-embedding-3-small"), allow_dangerous_deserialization=True),
    "openfoam_tutorials_details": FAISS.load_local(f"{DATABASE_DIR}/openfoam_tutorials_details", OpenAIEmbeddings(model="text-embedding-3-small"), allow_dangerous_deserialization=True),
    "openfoam_command_help": FAISS.load_local(f"{DATABASE_DIR}/openfoam_command_help", OpenAIEmbeddings(model="text-embedding-3-small"), allow_dangerous_deserialization=True)
}

def invoke_llm(
    config: object,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    pydantic_obj: Optional[Type[BaseModel]] = None,
) -> Any:
    model_version = getattr(config, "model_version", "gpt-4o")
    temperature = getattr(config, "temperature", 0.1)
    model_provider = getattr(config, "model_provider", "openai")
    
    llm = init_chat_model(model_version, model_provider=model_provider, temperature=temperature)
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    
    if pydantic_obj:
        structured_llm = llm.with_structured_output(pydantic_obj)
        return structured_llm.invoke(messages)
    else:
        return llm.invoke(messages)

def tokenize(text: str) -> str:
    # Replace underscores with spaces
    text = text.replace('_', ' ')
    # Insert a space between a lowercase letter and an uppercase letter (global match)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    return text.lower()

def save_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    print(f"Saved file at {path}")

def read_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read()
    return ""

def list_case_files(case_dir: str) -> str:
    files = [f for f in os.listdir(case_dir) if os.path.isfile(os.path.join(case_dir, f))]
    return ", ".join(files)

def remove_files(directory: str, prefix: str) -> None:
    for file in os.listdir(directory):
        if file.startswith(prefix):
            os.remove(os.path.join(directory, file))
    print(f"Removed files with prefix '{prefix}' in {directory}")

def remove_file(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
        print(f"Removed file {path}")

def run_command(script_path: str, out_file: str, err_file: str, working_dir: str) -> None:
    print(f"Executing script {script_path} in {working_dir}")
    
    with open(out_file, 'w') as out, open(err_file, 'w') as err:
        process = subprocess.Popen(
            ['bash', script_path],
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True
        )
        stdout, stderr = process.communicate()
        out.write(stdout)
        err.write(stderr)
    print(f"Executed script {script_path}")

def check_foam_errors(directory: str) -> list:
    error_logs = []
    # DOTALL mode allows '.' to match newline characters
    pattern = re.compile(r"ERROR:(.*)", re.DOTALL)
    
    for file in os.listdir(directory):
        if file.startswith("log"):
            filepath = os.path.join(directory, file)
            with open(filepath, 'r') as f:
                content = f.read()
            
            match = pattern.search(content)
            if match:
                error_content = match.group(0).strip()
                error_logs.append({"file": file, "error_content": error_content})
            elif "error" in content.lower():
                print(f"Warning: file {file} contains 'error' but does not match expected format.")
    return error_logs

def extract_commands_from_allrun_out(out_file: str) -> list:
    commands = []
    if not os.path.exists(out_file):
        return commands
    with open(out_file, 'r') as f:
        for line in f:
            if line.startswith("Running "):
                parts = line.split(" ")
                if len(parts) > 1:
                    commands.append(parts[1].strip())
    return commands

def parse_case_name(text: str) -> str:
    match = re.search(r'case name:\s*(.+)', text, re.IGNORECASE)
    return match.group(1).strip() if match else "default_case"

def split_subtasks(text: str) -> list:
    header_match = re.search(r'splits into (\d+) subtasks:', text, re.IGNORECASE)
    if not header_match:
        print("Warning: No subtasks header found in the response.")
        return []
    num_subtasks = int(header_match.group(1))
    subtasks = re.findall(r'subtask\d+:\s*(.*)', text, re.IGNORECASE)
    if len(subtasks) != num_subtasks:
        print(f"Warning: Expected {num_subtasks} subtasks but found {len(subtasks)}.")
    return subtasks

def parse_context(text: str) -> str:
    match = re.search(r'FoamFile\s*\{.*?(?=```|$)', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0).strip()
    
    print("Warning: Could not parse context; returning original text.")
    return text


def parse_file_name(subtask: str) -> str:
    match = re.search(r'openfoam\s+(.*?)\s+foamfile', subtask, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def parse_folder_name(subtask: str) -> str:
    match = re.search(r'foamfile in\s+(.*?)\s+folder', subtask, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def find_similar_file(description: str, tutorial: str) -> str:
    start_pos = tutorial.find(description)
    if start_pos == -1:
        return "None"
    end_marker = "input_file_end."
    end_pos = tutorial.find(end_marker, start_pos)
    if end_pos == -1:
        return "None"
    return tutorial[start_pos:end_pos + len(end_marker)]

def read_commands(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Commands file not found: {file_path}")
    with open(file_path, 'r') as f:
        # join non-empty lines with a comma
        return ", ".join(line.strip() for line in f if line.strip())

def find_input_file(case_dir: str, command: str) -> str:
    for root, _, files in os.walk(case_dir):
        for file in files:
            if command in file:
                return os.path.join(root, file)
    return ""

def retrieve_faiss(database_name: str, query: str, topk: int = 1) -> dict:
    """
    Retrieve a similar case from a FAISS database.
    """
    
    if database_name not in FAISS_DB_CACHE:
        raise ValueError(f"Database '{database_name}' is not loaded.")
    
    # Tokenize the query
    query = tokenize(query)
    
    vectordb = FAISS_DB_CACHE[database_name]
    docs = vectordb.similarity_search(query, k=topk)
    if not docs:
        raise ValueError(f"No documents found for query: {query}")
    
    formatted_results = []
    for doc in docs:
        metadata = doc.metadata or {}
        
        if database_name == "openfoam_allrun_scripts":
            formatted_results.append({
                "index": doc.page_content,
                "full_content": metadata.get("full_content", "unknown"),
                "case_name": metadata.get("case_name", "unknown"),
                "case_domain": metadata.get("case_domain", "unknown"),
                "case_category": metadata.get("case_category", "unknown"),
                "case_solver": metadata.get("case_solver", "unknown"),
                "dir_structure": metadata.get("dir_structure", "unknown"),
                "allrun_script": metadata.get("allrun_script", "N/A")
            })
        elif database_name == "openfoam_command_help":
            formatted_results.append({
                "index": doc.page_content,
                "full_content": metadata.get("full_content", "unknown"),
                "command": metadata.get("command", "unknown"),
                "help_text": metadata.get("help_text", "unknown")
            })
        elif database_name == "openfoam_tutorials_structure":
            formatted_results.append({
                "index": doc.page_content,
                "full_content": metadata.get("full_content", "unknown"),
                "case_name": metadata.get("case_name", "unknown"),
                "case_domain": metadata.get("case_domain", "unknown"),
                "case_category": metadata.get("case_category", "unknown"),
                "case_solver": metadata.get("case_solver", "unknown"),
                "dir_structure": metadata.get("dir_structure", "unknown")
            })
        elif database_name == "openfoam_tutorials_details":
            formatted_results.append({
                "index": doc.page_content,
                "full_content": metadata.get("full_content", "unknown"),
                "case_name": metadata.get("case_name", "unknown"),
                "case_domain": metadata.get("case_domain", "unknown"),
                "case_category": metadata.get("case_category", "unknown"),
                "case_solver": metadata.get("case_solver", "unknown"),
                "dir_structure": metadata.get("dir_structure", "unknown"),
                "tutorials": metadata.get("tutorials", "N/A")
            })
        else:
            raise ValueError(f"Unknown database name: {database_name}")
    
    

    return formatted_results
        

def parse_directory_structure(data: str) -> dict:
    """
    Parses the directory structure string and returns a dictionary where:
      - Keys: directory names
      - Values: count of files in that directory.
    """
    directory_file_counts = {}

    # Find all <dir>...</dir> blocks in the input string.
    dir_blocks = re.findall(r'<dir>(.*?)</dir>', data, re.DOTALL)

    for block in dir_blocks:
        # Extract the directory name (everything after "directory name:" until the first period)
        dir_name_match = re.search(r'directory name:\s*(.*?)\.', block)
        # Extract the list of file names within square brackets
        files_match = re.search(r'File names in this directory:\s*\[(.*?)\]', block)
        
        if dir_name_match and files_match:
            dir_name = dir_name_match.group(1).strip()
            files_str = files_match.group(1)
            # Split the file names by comma, removing any surrounding whitespace
            file_list = [filename.strip() for filename in files_str.split(',')]
            directory_file_counts[dir_name] = len(file_list)

    return directory_file_counts