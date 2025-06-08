import os
import subprocess
import sys
from utils import save_file
from pydantic import BaseModel, Field
from typing import List

# Helper to get the .foam file name

def get_foam_file(case_dir):
    case_dir_name = os.path.basename(os.path.normpath(case_dir))
    return f"{case_dir_name}.foam"

VISUALIZATION_SYSTEM_PROMPT = (
    "You are an expert in OpenFOAM post-processing and PyVista Python scripting. "
    "Your task is to generate a PyVista Python script that visualizes the specified data from the OpenFOAM case. "
    "The script should load the OpenFOAM case data by reading the .foam file (e.g., 'runs.foam') in the case directory using PyVista, display the geometry, and color the surface by the specified field (e.g., 'U' for velocity). "
    "Ensure the script shows the geometry, sets up the colorbar, and saves the visualization as a PNG file. "
    "The script must save the visualization as a PNG file, and the output image must contain the geometry and the colorbar, not just the colorbar. "
    "IMPORTANT: Return ONLY the Python code without any markdown formatting, code block markers, or explanatory text. "
    "The script should start with the necessary imports, read the .foam file using PyVista, and end with the screenshot saving."
)

ERROR_FIX_SYSTEM_PROMPT = (
    "You are an expert in PyVista Python scripting and OpenFOAM visualization. "
    "Your task is to fix the provided PyVista Python script that encountered an error. "
    "Ensure the script loads the OpenFOAM case data by reading the .foam file (e.g., 'runs.foam') in the case directory using PyVista, displays the geometry, and colors the surface by the specified field. "
    "Make sure the script shows the geometry, sets up the colorbar, and saves the visualization as a PNG file. "
    "The script must save the visualization as a PNG file, and the output image must contain the geometry and the colorbar, not just the colorbar. "
    "IMPORTANT: Return ONLY the Python code without any markdown formatting, code block markers, or explanatory text. "
    "The script should start with the necessary imports, read the .foam file using PyVista, and end with the screenshot saving."
)

class VisualizationState(BaseModel):
    case_dir: str  # Absolute path to the OpenFOAM case directory
    visualization_script: str = ""
    error_logs: List[str] = []
    output_image: str = ""
    max_loops: int = 3  # Maximum number of retry attempts
    current_loop: int = 0  # Current attempt number

def visualization_node(state, max_loop):
    """
    Visualization node: Creates and executes PyVista Python scripts for visualization
    based on user requirements.
    
    Args:
        state: State object containing:
            - case_dir: Absolute path to the OpenFOAM case directory
            - user_requirement: String containing visualization requirements
            - llm_service: LLM service for generating scripts
            - max_loops: Maximum number of retry attempts (default: 3)
    """
    print(f"============================== Visualization (PyVista) ==============================")
    
    # Ensure case_dir is absolute
    case_dir = os.path.abspath(state.case_dir)
    if not os.path.exists(case_dir):
        state.error_logs.append(f"Case directory does not exist: {case_dir}")
        return {"goto": "end"}
    
    # Touch the .foam file before generating the visualization script
    foam_file = get_foam_file(case_dir)
    foam_file_path = os.path.join(case_dir, foam_file)
    with open(foam_file_path, 'a'):
        os.utime(foam_file_path, None)
    
    # Initialize loop counter if not present
    if not hasattr(state, 'current_loop'):
        state.current_loop = 0
    
    while state.current_loop < max_loop:
        state.current_loop += 1
        print(f"Attempt {state.current_loop} of {max_loop}")
        
        # Create visualization script
        viz_prompt = (
            f"<case_directory>{case_dir}</case_directory>\n"
            f"<foam_file>{foam_file}</foam_file>\n"
            f"<visualization_requirements>{state.user_requirement}</visualization_requirements>\n"
            f"<previous_errors>{state.error_logs}</previous_errors>\n"
            f"Please create a PyVista Python script that visualizes the specified data by reading the .foam file ('{foam_file}') and saves it as a PNG file named visualization.png."
        )
        
        viz_script = state.llm_service.invoke(viz_prompt, VISUALIZATION_SYSTEM_PROMPT)
        
        # Save the visualization script
        script_path = os.path.join(case_dir, "visualization.py")
        save_file(script_path, viz_script)
        state.visualization_script = viz_script
        
        # Execute the script using Python
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=case_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            print(f"Finished command: Return Code {result.returncode}")
            state.error_logs = []
            
            # Check if the output image was created
            output_image = os.path.join(case_dir, "visualization.png")
            if os.path.exists(output_image):
                state.output_image = output_image
                return {"goto": "end"}
            else:
                state.error_logs.append("Visualization script executed but no output image was created")
                
        except subprocess.CalledProcessError as e:
            error_message = f"Error executing visualization script: {str(e)}"
            if e.stdout:
                error_message += f"\nSTDOUT:\n{e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout}"
            if e.stderr:
                error_message += f"\nSTDERR:\n{e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
            state.error_logs.append(error_message)
        
        # If we have errors and haven't reached max loops, try to fix them
        if state.error_logs and state.current_loop < max_loop:
            error_fix_prompt = (
                f"<error_logs>{state.error_logs}</error_logs>\n"
                f"<foam_file>{foam_file}</foam_file>\n"
                f"<original_script>{state.visualization_script}</original_script>\n"
                f"<attempt_number>{state.current_loop}</attempt_number>\n"
                f"Please fix the PyVista Python script based on the error messages. The script should read the .foam file ('{foam_file}') in the case directory."
            )
            
            fixed_script = state.llm_service.invoke(error_fix_prompt, ERROR_FIX_SYSTEM_PROMPT)
            
            # Save the fixed script
            save_file(script_path, fixed_script)
            state.visualization_script = fixed_script
            
            # Try executing the fixed script
            try:
                result = subprocess.run(
                    [sys.executable, script_path],
                    cwd=case_dir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                print(f"Finished command: Return Code {result.returncode}")
                state.error_logs = []
                
                # Check if the output image was created
                output_image = os.path.join(case_dir, "visualization.png")
                if os.path.exists(output_image):
                    state.output_image = output_image
                    return {"goto": "end"}
                else:
                    state.error_logs.append("Fixed visualization script executed but no output image was created")
                    
            except subprocess.CalledProcessError as e:
                error_message = f"Error executing fixed visualization script: {str(e)}"
                if e.stdout:
                    error_message += f"\nSTDOUT:\n{e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout}"
                if e.stderr:
                    error_message += f"\nSTDERR:\n{e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
                state.error_logs.append(error_message)
    
    # If we've exhausted all attempts
    if state.current_loop >= max_loop:
        print(f"Failed to create visualization after {max_loop} attempts")
        state.error_logs.append(f"Maximum number of attempts ({max_loop}) reached without success")
    
    return {"goto": "end"} 