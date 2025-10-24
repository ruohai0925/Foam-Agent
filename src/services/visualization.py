import os
import sys
import subprocess
import glob
from typing import Dict, List, Tuple
from utils import save_file


def ensure_foam_file(case_dir: str) -> str:
    case_dir = os.path.abspath(case_dir)
    foam = f"{os.path.basename(case_dir)}.foam"
    foam_path = os.path.join(case_dir, foam)
    with open(foam_path, 'a'):
        os.utime(foam_path, None)
    return foam


def generate_pyvista_script(llm, case_dir: str, foam_file: str, user_requirement: str, previous_errors: List[str]) -> str:
    system_prompt = (
        "You are an expert in OpenFOAM post-processing and PyVista Python scripting. "
        "Generate a PyVista script that loads the .foam file, renders geometry colored by requested field, uses coolwarm colormap, and saves a PNG. "
        "Return ONLY Python code, no markdown."
    )
    prompt = (
        f"<case_directory>{case_dir}</case_directory>\n"
        f"<foam_file>{foam_file}</foam_file>\n"
        f"<visualization_requirements>{user_requirement}</visualization_requirements>\n"
        f"<previous_errors>{previous_errors}</previous_errors>\n"
    )
    return llm.invoke(prompt, system_prompt)


def run_pyvista_script(case_dir: str, script: str, filename: str = "visualization.py") -> Tuple[bool, str, List[str]]:
    script_path = os.path.join(case_dir, filename)
    save_file(script_path, script)
    try:
        result = subprocess.run([sys.executable, script_path], cwd=case_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        png_files = glob.glob(os.path.join(case_dir, "*.png"))
        if png_files:
            return True, png_files[0], []
        return False, "", ["Visualization script executed but no PNG output image was created"]
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else str(e.stdout)
        return False, "", [f"Error executing visualization script: {e}\nSTDOUT:\n{out}\nSTDERR:\n{err}"]


def fix_pyvista_script(llm, foam_file: str, original_script: str, error_logs: List[str]) -> str:
    system_prompt = (
        "You are an expert in PyVista visualization. Fix the provided script to load the .foam file, render geometry, and save a PNG with colorbar. Return ONLY Python code."
    )
    prompt = (
        f"<error_logs>{error_logs}</error_logs>\n"
        f"<foam_file>{foam_file}</foam_file>\n"
        f"<original_script>{original_script}</original_script>\n"
    )
    return llm.invoke(prompt, system_prompt)


