import os
import subprocess
import sys
from utils import save_file
from pydantic import BaseModel, Field
from typing import List

VISUALIZATION_SYSTEM_PROMPT = (
    "You are an expert in OpenFOAM post-processing and ParaView Python scripting. "
    "Your task is to generate a ParaView Python script that visualizes the specified data from the OpenFOAM case. "
    "The script should load the OpenFOAM case, display the geometry in a RenderView, and color the surface by the specified field (e.g., 'U' for velocity). "
    "Ensure the script shows the geometry in the render view, resets the camera to fit the data, renders the view, and sets up the colorbar. "
    "The script must save the visualization as a PNG file, and the output image must contain the geometry and the colorbar, not just the colorbar. "
    "IMPORTANT: Return ONLY the Python code without any markdown formatting, code block markers, or explanatory text. "
    "The script should start with the necessary imports and end with the screenshot saving."
)

ERROR_FIX_SYSTEM_PROMPT = (
    "You are an expert in ParaView Python scripting and OpenFOAM visualization. "
    "Your task is to fix the provided ParaView Python script that encountered an error. "
    "Ensure the script loads the OpenFOAM case, displays the geometry in a RenderView, and colors the surface by the specified field. "
    "Make sure the script shows the geometry in the render view, resets the camera to fit the data, renders the view, and sets up the colorbar. "
    "The script must save the visualization as a PNG file, and the output image must contain the geometry and the colorbar, not just the colorbar. "
    "IMPORTANT: Return ONLY the Python code without any markdown formatting, code block markers, or explanatory text. "
    "The script should start with the necessary imports and end with the screenshot saving."
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
    Visualization node: Creates and executes ParaView Python scripts for visualization
    based on user requirements.
    
    Args:
        state: State object containing:
            - case_dir: Absolute path to the OpenFOAM case directory
            - user_requirement: String containing visualization requirements
            - llm_service: LLM service for generating scripts
            - max_loops: Maximum number of retry attempts (default: 3)
    """
    print(f"============================== Visualization ==============================")
    
    # Ensure case_dir is absolute
    case_dir = os.path.abspath(state.case_dir)
    if not os.path.exists(case_dir):
        state.error_logs.append(f"Case directory does not exist: {case_dir}")
        return {"goto": "end"}
    
    # Initialize loop counter if not present
    if not hasattr(state, 'current_loop'):
        state.current_loop = 0
    
    while state.current_loop < max_loop:
        state.current_loop += 1
        print(f"Attempt {state.current_loop} of {max_loop}")
        
        # Create visualization script
        viz_prompt = (
            f"<case_directory>{case_dir}</case_directory>\n"
            f"<visualization_requirements>{state.user_requirement}</visualization_requirements>\n"
            f"<previous_errors>{state.error_logs}</previous_errors>\n"
            "Please create a ParaView Python script that visualizes the specified data and saves it as a PNG file named visualization.png."
            f"<paraview_path>{state.paraview_path}</paraview_path>"
            "Make sure to append the paraview_path to the sys.path before importing ParaView modules."
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
                stdout=sys.stdout,
                stderr=sys.stderr,
                stdin=sys.stdin
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
            state.error_logs.append(f"Error executing visualization script: {str(e)}")
        
        # If we have errors and haven't reached max loops, try to fix them
        if state.error_logs and state.current_loop < max_loop:
            error_fix_prompt = (
                f"<error_logs>{state.error_logs}</error_logs>\n"
                f"<original_script>{state.visualization_script}</original_script>\n"
                f"<attempt_number>{state.current_loop}</attempt_number>\n"
                "Please fix the ParaView Python script based on the error messages."
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
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    stdin=sys.stdin
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
                state.error_logs.append(f"Error executing fixed visualization script: {str(e)}")
    
    # If we've exhausted all attempts
    if state.current_loop >= state.max_loops:
        print(f"Failed to create visualization after {state.max_loops} attempts")
        state.error_logs.append(f"Maximum number of attempts ({state.max_loops}) reached without success")
    
    return {"goto": "end"} 