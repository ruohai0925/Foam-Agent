import os
import subprocess
import sys
import shutil
from utils import save_file
from pydantic import BaseModel, Field
from typing import List, Optional

BOUNDARY_SYSTEM_PROMPT = (
    "You are an expert in OpenFOAM mesh processing and simulations. "
    "Your role is to analyze and modify boundary conditions in OpenFOAM polyMesh boundary file. "
    "You understand both 2D and 3D simulations and know how to properly set boundary conditions. "
    "For 2D simulations, you know which boundaries should be set to 'empty' type and 'empty' physicalType. "
    "You are precise and only return the exact boundary file content without any additional text or explanations. "
    "IMPORTANT: Only change the specified boundary to 'empty' type and leave all other boundaries exactly as they are."
)

CONTROLDICT_SYSTEM_PROMPT = (
    "You are an expert in OpenFOAM simulation setup. "
    "Your role is to create a basic controlDict file for mesh conversion. "
    "You understand the minimal requirements needed for gmshToFoam to work. "
    "You are precise and only return the exact controlDict file content without any additional text or explanations."
)

class PreprocessorState(BaseModel):
    case_dir: str  # Absolute path to the OpenFOAM case directory
    mesh_file: str  # Path to the input .msh file
    error_logs: List[str] = []
    max_loops: int = 10  # Maximum number of retry attempts
    current_loop: int = 0  # Current attempt number

def preprocessor_node(state, max_loop):
    """
    Preprocessor node: Converts .msh file to OpenFOAM format and handles boundary conditions.
    
    Args:
        state: State object containing:
            - case_dir: Absolute path to the OpenFOAM case directory
            - mesh_file: Path to the input .msh file
            - user_requirement: String containing mesh and boundary requirements
            - llm_service: LLM service for generating scripts
            - max_loops: Maximum number of retry attempts (default: 10)
    """
    print(f"============================== Preprocessor ==============================")
    
    # Ensure case_dir is absolute
    case_dir = os.path.abspath(state.config.case_dir)
    if os.path.exists(case_dir):
        print(f"Warning: Case directory {case_dir} already exists. Overwriting.")
        shutil.rmtree(case_dir)
    os.makedirs(case_dir)
    print(f"Created case directory: {case_dir}")
    if not os.path.exists(case_dir):
        state.error_logs.append(f"Case directory does not exist: {case_dir}")
        return {"goto": "end"}
    
    # Ensure mesh file exists
    mesh_file = os.path.abspath(state.mesh_file)
    if not os.path.exists(mesh_file):
        state.error_logs.append(f"Mesh file does not exist: {mesh_file}")
        return {"goto": "end"}
    
    # Initialize loop counter if not present
    if not hasattr(state, 'current_loop'):
        state.current_loop = 0
    
    while state.current_loop < max_loop:
        state.current_loop += 1
        print(f"Attempt {state.current_loop} of {max_loop}")
        
        try:
            # Create constant directory if it doesn't exist
            constant_dir = os.path.join(case_dir, "constant")
            os.makedirs(constant_dir, exist_ok=True)
            
            # Create system directory if it doesn't exist
            system_dir = os.path.join(case_dir, "system")
            os.makedirs(system_dir, exist_ok=True)
            
            # Create basic controlDict file
            controldict_prompt = (
                f"<user_requirements>{state.user_requirement}</user_requirements>\n"
                "Please create a basic controlDict file for mesh conversion. "
                "The file should include only the essential settings needed for gmshToFoam to work. "
                "IMPORTANT: Return ONLY the complete controlDict file content without any additional text."
            )
            
            controldict_content = state.llm_service.invoke(controldict_prompt, CONTROLDICT_SYSTEM_PROMPT).strip()
            
            if controldict_content:
                # Save the controlDict file
                controldict_file = os.path.join(system_dir, "controlDict")
                save_file(controldict_file, controldict_content)
                print("Created basic controlDict file for mesh conversion")
            
            # Copy mesh file to case directory
            mesh_copy = os.path.join(case_dir, os.path.basename(mesh_file))
            if os.path.exists(mesh_copy):
                os.remove(mesh_copy)
            shutil.copy2(mesh_file, mesh_copy)
            
            # Run gmshToFoam command
            result = subprocess.run(
                ["gmshToFoam", mesh_copy],
                cwd=case_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print(f"gmshToFoam command output: {result.stdout}")
            
            # Check if the mesh was converted successfully
            polyMesh_dir = os.path.join(constant_dir, "polyMesh")
            if not os.path.exists(polyMesh_dir):
                state.error_logs.append("Mesh conversion failed: polyMesh directory not created")
                continue
            
            # Handle boundary conditions based on user requirements
            boundary_file = os.path.join(polyMesh_dir, "boundary")
            if os.path.exists(boundary_file):
                # Read the boundary file
                with open(boundary_file, 'r') as f:
                    boundary_content = f.read()
                
                # Parse user requirements to determine boundary modifications
                boundary_prompt = (
                    f"<user_requirements>{state.user_requirement}</user_requirements>\n"
                    f"<boundary_file_content>{boundary_content}</boundary_file_content>\n"
                    "Please analyze the user requirements and boundary file content. "
                    "Identify which boundary is to be modified based on the boundaries mentioned in the user requirements."
                    "If this is a 2D simulation, modify ONLY the appropriate boundary to 'empty' type and 'empty' physicalType. "
                    "Based on the no slip boundaries mentioned in the user requirements, modify the appropriate boundary/boundaries to type 'wall' and physicalType 'wall'. "
                    "If this is a 3D simulation, only modify the appropriate boundary/boundaries to type 'wall' and physicalType 'wall'."
                    "IMPORTANT: Do not change any other boundaries - leave them exactly as they are. "
                    "Return ONLY the complete boundary file content with any necessary modifications. No additional text."
                )
                
                updated_boundary_content = state.llm_service.invoke(boundary_prompt, BOUNDARY_SYSTEM_PROMPT).strip()
                
                if updated_boundary_content:
                    # Save the updated boundary file
                    save_file(boundary_file, updated_boundary_content)
                    print("Boundary file updated based on simulation requirements")
            
            # Create .foam file
            foam_file = os.path.join(case_dir, f"{os.path.basename(case_dir)}.foam")
            with open(foam_file, 'w') as f:
                pass
            
            return {"goto": "architect"}
            
        except subprocess.CalledProcessError as e:
            error_message = f"Error in mesh conversion: {str(e)}"
            if e.stdout:
                error_message += f"\nSTDOUT:\n{e.stdout}"
            if e.stderr:
                error_message += f"\nSTDERR:\n{e.stderr}"
            state.error_logs.append(error_message)
            
            if state.current_loop >= max_loop:
                print(f"Failed to process mesh after {max_loop} attempts")
                state.error_logs.append(f"Maximum number of attempts ({max_loop}) reached without success")
                return {"goto": "end"}
    
    return {"goto": "end"} 