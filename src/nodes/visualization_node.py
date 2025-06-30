# visualization_node.py
import os
from typing import List, Optional
from pydantic import BaseModel, Field

class PlotConfigPydantic(BaseModel):
    """Configuration for plotting parameters"""
    plot_type: str = Field(description="Type of plot (e.g., 'contour', 'vector', 'streamline', 'time_series')")
    field_name: str = Field(description="Field to plot (e.g., 'U', 'p', 'T', 'rho')")
    time_step: Optional[str] = Field(default=None, description="Time step to plot (if None, use latest)")
    output_format: str = Field(default="png", description="Output format for plots")
    output_path: str = Field(description="Path to save the plot")

class VisualizationPlanPydantic(BaseModel):
    """Plan for visualization tasks"""
    plots: List[PlotConfigPydantic] = Field(description="List of plots to generate")

class VisualizationAnalysisPydantic(BaseModel):
    """Analysis of user requirements for visualization needs"""
    primary_field: str = Field(description="Primary field to visualize (e.g., 'U', 'p', 'T', 'rho')")
    plot_type: str = Field(description="Type of plot requested (e.g., 'contour', 'vector', 'streamline', 'time_series')")
    time_step: Optional[str] = Field(default=None, description="Specific time step to plot (if mentioned)")
    plane_info: Optional[str] = Field(default=None, description="Plane information if 2D slice is requested (e.g., 'Z plane', 'X=0.5')")
    additional_fields: List[str] = Field(default=[], description="Additional fields that might be useful to visualize")
    visualization_priority: str = Field(description="Priority of visualization (e.g., 'high', 'medium', 'low')")

def visualization_node(state):
    """
    Visualization node: Creates plots and visualizations from the successfully generated OpenFOAM case.
    This nodeuses the successfully generated code and user_requirement to create plots.
    
    Updates state with:
      - plot_configs: List of plot configurations
      - plot_outputs: List of generated plot file paths
      - visualization_summary: Summary of generated visualizations
    """
    config = state["config"]
    user_requirement = state["user_requirement"]
    case_dir = state["case_dir"]
    
    print(f"============================== Visualization Node ==============================")
    print(f"Creating visualizations for case: {state.get('case_name', 'Unknown')}")
    print(f"Case directory: {case_dir}")
    
    # Step 1: Analyze user requirement to determine what plots to generate
    print("Step 1: Analyzing user requirements for visualization needs...")
    
    visualization_system_prompt = (
        "You are an expert in OpenFOAM visualization and computational fluid dynamics. "
        "Your task is to analyze user requirements and extract key information needed for visualization. "
        "Focus specifically on visualization-related information and ignore other simulation setup details. "
        "Extract the following key elements:\n"
        "- Primary field to visualize (e.g., velocity magnitude, pressure, temperature)\n"
        "- Type of plot requested (e.g., contour, vector, streamline, time series)\n"
        "- Time step information (if specified)\n"
        "- Plane or slice information (if 2D visualization is requested)\n"
        "- Additional fields that might be useful to visualize\n"
        "- Priority of the visualization request\n\n"
        "Your output must strictly follow the JSON schema provided and include no additional information. "
        "If specific visualization details are not mentioned, make reasonable assumptions based on the simulation type."
    )
    
    visualization_user_prompt = (
        f"User Requirement: {user_requirement}\n\n"
        "Please analyze this user requirement and extract the visualization needs. "
        "Focus on what the user wants to visualize, what fields are important, and what type of plots would be most useful. "
        "Ignore simulation setup details like boundary conditions, mesh information, or solver settings unless they directly relate to visualization."
    )
    
    visualization_analysis = state["llm_service"].invoke(
        visualization_user_prompt, 
        visualization_system_prompt, 
        pydantic_obj=VisualizationAnalysisPydantic
    )
    
    print(f"Primary field to visualize: {visualization_analysis.primary_field}")
    print(f"Plot type requested: {visualization_analysis.plot_type}")
    if visualization_analysis.time_step:
        print(f"Time step: {visualization_analysis.time_step}")
    if visualization_analysis.plane_info:
        print(f"Plane information: {visualization_analysis.plane_info}")
    if visualization_analysis.additional_fields:
        print(f"Additional fields: {visualization_analysis.additional_fields}")
    print(f"Visualization priority: {visualization_analysis.visualization_priority}")
    
    # Step 2: Check available OpenFOAM data files and time steps
    # TODO: Scan case directory for available time steps and field data
    pass
    
    # Step 3: Generate visualization plan based on available data and user requirements
    # TODO: Create structured plan for what plots to generate
    pass
    
    # Step 4: Execute plotting commands using OpenFOAM utilities
    # TODO: Run OpenFOAM post-processing tools (postProcess, sample, etc.)
    pass
    
    # Step 5: Generate plots using matplotlib, pyvista, or other visualization libraries
    # TODO: Create actual plots from the processed data
    pass
    
    # Step 6: Save plots and generate summary
    # TODO: Save plots to output directory and create summary report
    pass
    
    # Mock return values for the skeleton
    plot_configs = [
        {
            "plot_type": "contour",
            "field_name": "p",
            "time_step": "latest",
            "output_format": "png",
            "output_path": os.path.join(case_dir, "plots", "pressure_contour.png")
        },
        {
            "plot_type": "vector",
            "field_name": "U",
            "time_step": "latest", 
            "output_format": "png",
            "output_path": os.path.join(case_dir, "plots", "velocity_vectors.png")
        }
    ]
    
    plot_outputs = [
        os.path.join(case_dir, "plots", "pressure_contour.png"),
        os.path.join(case_dir, "plots", "velocity_vectors.png")
    ]
    
    visualization_summary = {
        "total_plots_generated": len(plot_outputs),
        "plot_types": ["contour", "vector"],
        "fields_visualized": ["p", "U"],
        "output_directory": os.path.join(case_dir, "plots")
    }
    
    print(f"Generated {len(plot_outputs)} plots")
    print(f"Plots saved to: {os.path.join(case_dir, 'plots')}")
    print("============================== Visualization Complete ==============================")
    
    # Return updated state
    return {
        **state,
        "visualization_analysis": visualization_analysis,
        "plot_configs": plot_configs,
        "plot_outputs": plot_outputs,
        "visualization_summary": visualization_summary
    }
