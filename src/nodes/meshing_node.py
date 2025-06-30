import os
import shutil
from typing import List, Optional
from pydantic import BaseModel, Field
from utils import save_file, remove_file


class MeshInfoPydantic(BaseModel):
    mesh_file_path: str = Field(description="Path to the custom mesh file (e.g., .msh, .stl, .obj)")
    mesh_file_type: str = Field(description="Type of mesh file (gmsh, stl, obj, etc.)")
    mesh_description: str = Field(description="Description of the mesh and any specific requirements")
    requires_blockmesh_removal: bool = Field(description="Whether to remove blockMeshDict file", default=True)


class MeshCommandsPydantic(BaseModel):
    mesh_commands: List[str] = Field(description="List of OpenFOAM commands needed to process the custom mesh")
    mesh_file_destination: str = Field(description="Destination path for the mesh file in the case directory")


def meshing_node(state):
    """
    Meshing node: Handle custom mesh files provided by the user.
    Processes mesh files like Gmsh (.msh), STL, OBJ, etc. using OpenFOAM tools.
    Updates state with:
      - mesh_info: Information about the custom mesh
      - mesh_commands: Commands needed for mesh processing
      - mesh_file_destination: Where the mesh file should be placed
    """
    config = state["config"]
    user_requirement = state["user_requirement"]
    case_dir = state["case_dir"]
    
    # Check if user provided custom mesh information in the requirement
    # This is a mock implementation - in real implementation, this would be parsed from user input
    
    # Mock: Extract mesh information from user requirement
    # In real implementation, this would use LLM to parse mesh requirements
    mesh_system_prompt = (
        "You are an expert in OpenFOAM mesh processing. "
        "Analyze the user requirement to identify if they want to use a custom mesh file. "
        "If a custom mesh is mentioned, extract the mesh file path, type, and description. "
        "Return the information in a structured format."
    )
    
    mesh_user_prompt = (
        f"User requirement: {user_requirement}\n\n"
        "Identify if the user wants to use a custom mesh file. "
        "If yes, extract the mesh file path, type (gmsh, stl, obj, etc.), and description. "
        "If no custom mesh is mentioned, return None for all fields."
    )
    
    # Mock response - in real implementation, this would be from LLM
    mesh_response = state["llm_service"].invoke(mesh_user_prompt, mesh_system_prompt, pydantic_obj=MeshInfoPydantic)
    
    # For mock purposes, let's assume user wants to use a Gmsh mesh
    # In real implementation, this would be the actual parsed response
    mesh_info = {
        "mesh_file_path": "/path/to/user/mesh.msh",  # Mock path
        "mesh_file_type": "gmsh",
        "mesh_description": "Custom mesh for complex geometry with refined regions",
        "requires_blockmesh_removal": True
    }
    
    # If no custom mesh is requested, skip this node
    if not mesh_info["mesh_file_path"] or mesh_info["mesh_file_path"] == "None":
        print("No custom mesh requested. Skipping meshing node.")
        return {
            **state,
            "mesh_info": None,
            "mesh_commands": [],
            "mesh_file_destination": None
        }
    
    print(f"Processing custom mesh: {mesh_info['mesh_file_path']}")
    print(f"Mesh type: {mesh_info['mesh_file_type']}")
    print(f"Description: {mesh_info['mesh_description']}")
    
    # Determine mesh file destination in case directory
    mesh_file_destination = os.path.join(case_dir, "constant", "triSurface", os.path.basename(mesh_info["mesh_file_path"]))
    
    # Generate appropriate OpenFOAM commands based on mesh type
    mesh_commands = []
    
    if mesh_info["mesh_file_type"].lower() == "gmsh":
        # For Gmsh .msh files, we need to convert to OpenFOAM format
        mesh_commands = [
            "gmshToFoam",  # Convert .msh to OpenFOAM format
            "checkMesh",   # Check mesh quality
            "renumberMesh -overwrite"  # Renumber mesh for better performance
        ]
    elif mesh_info["mesh_file_type"].lower() == "stl":
        # For STL files, we need to use snappyHexMesh or surfaceMeshTriangulate
        mesh_commands = [
            "surfaceMeshTriangulate",  # Triangulate surface mesh
            "checkMesh",               # Check mesh quality
        ]
    elif mesh_info["mesh_file_type"].lower() == "obj":
        # For OBJ files, convert to STL first then process
        mesh_commands = [
            "objToSTL",                # Convert OBJ to STL
            "surfaceMeshTriangulate",  # Triangulate surface mesh
            "checkMesh",               # Check mesh quality
        ]
    else:
        # Generic mesh processing
        mesh_commands = [
            "checkMesh",  # Check mesh quality
        ]
    
    # If custom mesh is used, we need to remove blockMeshDict
    if mesh_info["requires_blockmesh_removal"]:
        blockmesh_path = os.path.join(case_dir, "system", "blockMeshDict")
        if os.path.exists(blockmesh_path):
            print(f"Removing blockMeshDict: {blockmesh_path}")
            remove_file(blockmesh_path)
    
    # Generate mesh commands for the InputWriter node
    mesh_commands_pydantic = MeshCommandsPydantic(
        mesh_commands=mesh_commands,
        mesh_file_destination=mesh_file_destination
    )
    
    # Create necessary directories
    os.makedirs(os.path.dirname(mesh_file_destination), exist_ok=True)
    
    # Mock: Copy mesh file to case directory
    # In real implementation, this would copy the actual file
    print(f"Mesh file would be copied to: {mesh_file_destination}")
    
    # Update state with mesh information
    return {
        **state,
        "mesh_info": mesh_info,
        "mesh_commands": mesh_commands,
        "mesh_file_destination": mesh_file_destination,
        "custom_mesh_used": True
    }
