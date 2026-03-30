---
name: foam
description: Run a complete OpenFOAM CFD simulation (Foundation OpenFOAM v10 only) from a natural language prompt using Foam-Agent's MCP tools
user_invocable: true
---

# Foam-Agent: Automated CFD Simulation

You are orchestrating a complete OpenFOAM CFD simulation workflow using the Foam-Agent MCP tools. Follow these steps in order:

## Input

The user provides: `$ARGUMENTS`

If no arguments are provided, ask the user to describe their CFD simulation requirements (e.g., "Simulate lid-driven cavity flow at Re=1000" or "Simulate flow over a backward-facing step").

## Workflow

### Step 1: Plan
Call the `plan` MCP tool with the user's requirement:
```
plan({ user_requirement: "<user's description>" })
```
Show the user the planned case name, solver, domain, category, and subtask list. Ask for confirmation before proceeding.

### Step 2: Generate Files
Call the `input_writer` MCP tool with all fields from the plan response:
```
input_writer({
  case_name: "<from plan>",
  subtasks: <from plan>,
  user_requirement: "<user's description>",
  case_solver: "<from plan>",
  case_domain: "<from plan>",
  case_category: "<from plan>"
})
```
Report the case directory and number of generated files.

### Step 3: Run Simulation
Call the `run` MCP tool:
```
run({ case_dir: "<from input_writer>", timeout: 3600 })
```
Report the status (success/failed) and any errors.

### Step 4: Error Correction Loop (if errors)
If the simulation failed, enter the review-fix-rerun loop (max 5 iterations):

1. Call `review` with the case_dir, errors, and user_requirement
2. Show the user the error analysis
3. Call `apply_fixes` with the review analysis
4. Call `run` again
5. Repeat until success or max iterations reached

### Step 5: Visualization (optional)
If the simulation succeeded and the user wants visualization, call:
```
visualization({ case_dir: "<case_dir>", quantity: "<e.g., pressure, velocity>" })
```

## Guidelines
- **This workflow targets Foundation OpenFOAM v10 (openfoam.org) exclusively.** Generated files use v10 dictionary names (e.g., `momentumTransport`, `physicalProperties`) and solver binaries (e.g., `buoyantFoam`). ESI OpenFOAM (openfoam.com, e.g., v2312, v2406, v2512) is not compatible.
- Always show the plan to the user and get confirmation before generating files
- Report progress at each step
- If any step fails after retries, explain the error clearly and suggest manual intervention
- The case directory contains all OpenFOAM files - the user can inspect/modify them directly
