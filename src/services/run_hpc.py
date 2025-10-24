from typing import Optional, Tuple, Dict
import os
import json
import subprocess
import re
from models import HPCScriptIn, HPCScriptOut, RunIn, RunOut, JobStatusIn, JobStatusOut
from utils import check_foam_errors, save_file


def create_slurm_script(case_dir: str, cluster_info: dict, llm) -> str:
    system_prompt = (
        "You are an expert in HPC cluster job submission and SLURM scripting. "
        "Create a complete SLURM script for running OpenFOAM simulations. "
        "The script should include: "
        "1. Proper SLURM directives (#SBATCH) based on the cluster information provided"
        "2. Do not load openfoam"
        "3. Load libaraies for openfoam for run in parallel"
        "4. Directory navigation and execution of the Allrun script"
        "5. Error handling and status reporting"
        "6. Any cluster-specific optimizations or requirements"
        "7. Use your understanding of the documentation of the cluster and figure out the syntax of their jobscript."
        "Return ONLY the complete SLURM script content. Do not include any explanations or markdown formatting."
        "Make sure the script is executable and follows best practices for the specified cluster."
    )
    user_prompt = (
        f"Create a SLURM script for OpenFOAM simulation with the following parameters:\n"
        f"Cluster: {cluster_info['cluster_name']}\n"
        f"Account: {cluster_info['account_number']}\n"
        f"Partition: {cluster_info['partition']}\n"
        f"Nodes: {cluster_info['nodes']}\n"
        f"Tasks per node: {cluster_info['ntasks_per_node']}\n"
        f"Time limit: {cluster_info['time_limit']} hours\n"
        f"Memory: {cluster_info['memory']} GB per node\n"
        f"Case directory: {case_dir}\n"
        f"Generate a complete SLURM script that will run the OpenFOAM simulation using the Allrun script."
    )
    response = llm.invoke(user_prompt, system_prompt)
    script_content = response.strip()
    if script_content.startswith('```bash'):
        script_content = script_content[7:]
    elif script_content.startswith('```'):
        script_content = script_content[3:]
    if script_content.endswith('```'):
        script_content = script_content[:-3]
    script_content = script_content.strip()
    if not script_content.startswith('#!/bin/bash'):
        script_content = '#!/bin/bash\n' + script_content
    script_path = os.path.join(case_dir, "submit_job.slurm")
    save_file(script_path, script_content)
    return script_path


def create_slurm_script_with_error_context(case_dir: str, cluster_info: dict, llm, error_message: str = "", previous_script_content: str = "") -> str:
    system_prompt = (
        "You are an expert in HPC cluster job submission and SLURM scripting. "
        "Create a complete SLURM script for running OpenFOAM simulations. "
        "The script should include: "
        "1. Proper SLURM directives (#SBATCH) based on the cluster information provided"
        "2. Do not load OpenFOAM"
        "3. Load libaraies for openfoam for run in parallel"
        "4. Directory navigation and execution of the Allrun script"
        "5. Error handling and status reporting"
        "6. Any cluster-specific optimizations or requirements"
        "7. Use your understanding of the documentation of the cluster and figure out the syntax of their jobscript."
        "If a previous script and error message are provided, analyze them and fix issues."
        "Return ONLY the complete SLURM script content. Do not include any explanations or markdown formatting."
    )
    user_prompt = (
        f"Create a SLURM script for OpenFOAM simulation with the following parameters:\n"
        f"Cluster: {cluster_info['cluster_name']}\n"
        f"Account: {cluster_info['account_number']}\n"
        f"Partition: {cluster_info['partition']}\n"
        f"Nodes: {cluster_info['nodes']}\n"
        f"Tasks per node: {cluster_info['ntasks_per_node']}\n"
        f"Time limit: {cluster_info['time_limit']} hours\n"
        f"Memory: {cluster_info['memory']} GB per node\n"
        f"Case directory: {case_dir}\n"
    )
    if error_message and previous_script_content:
        user_prompt += f"\nPrevious submission failed with error: {error_message}\nPrevious script:\n```bash\n{previous_script_content}\n```\n"
    user_prompt += "Generate a complete SLURM script that will run the OpenFOAM simulation using the Allrun script. Return ONLY the script."
    response = llm.invoke(user_prompt, system_prompt)
    script_content = response.strip()
    if script_content.startswith('```bash'):
        script_content = script_content[7:]
    elif script_content.startswith('```'):
        script_content = script_content[3:]
    if script_content.endswith('```'):
        script_content = script_content[:-3]
    script_content = script_content.strip()
    if not script_content.startswith('#!/bin/bash'):
        script_content = '#!/bin/bash\n' + script_content
    script_path = os.path.join(case_dir, "submit_job.slurm")
    save_file(script_path, script_content)
    return script_path


def submit_slurm_job(script_path: str) -> tuple:
    try:
        result = subprocess.run(["sbatch", script_path], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        job_id_match = re.search(r'Submitted batch job (\d+)', output)
        if job_id_match:
            return job_id_match.group(1), True, ""
        return None, False, f"Could not extract job ID from output: {output}"
    except subprocess.CalledProcessError as e:
        return None, False, f"Failed to submit job: {e.stderr}"
    except Exception as e:
        return None, False, f"Unexpected error: {str(e)}"


def check_job_status(job_id: str) -> tuple:
    try:
        result = subprocess.run(["squeue", "-j", job_id, "--noheader", "-o", "%T"], capture_output=True, text=True, check=True)
        status = result.stdout.strip()
        if status:
            return status, True, ""
        return "COMPLETED", True, ""
    except subprocess.CalledProcessError as e:
        return None, False, f"Failed to check job status: {e.stderr}"
    except Exception as e:
        return None, False, f"Unexpected error: {str(e)}"


def generate_hpc_script(inp: HPCScriptIn, llm, case_dir: str) -> HPCScriptOut:
    script_path = create_slurm_script(case_dir, inp.hpc_config, llm)
    with open(script_path, "r") as f:
        content = f.read()
    return HPCScriptOut(script_content=content, script_path=script_path)


def run_simulation_hpc(script_path: str) -> RunOut:
    job_id, ok, err = submit_slurm_job(script_path)
    status = "submitted" if ok else f"failed: {err}"
    return RunOut(job_id=job_id, status=status)


def check_job(inp: JobStatusIn) -> JobStatusOut:
    status, ok, err = check_job_status(inp.job_id)
    return JobStatusOut(status=status if ok else f"error: {err}")


def extract_cluster_info_from_requirement(user_requirement: str, case_dir: str, llm) -> Dict:
    """Stateless extraction of cluster info using LLM and optional decomposeParDict."""
    decompose_par_dict_content = ""
    decompose_par_dict_path = os.path.join(case_dir, "system", "decomposeParDict")
    if os.path.exists(decompose_par_dict_path):
        try:
            with open(decompose_par_dict_path, 'r') as f:
                decompose_par_dict_content = f.read()
        except Exception:
            pass

    system_prompt = (
        "You are an expert in HPC cluster analysis. "
        "Analyze the user requirement to extract cluster information. "
        "Look for cluster name, account number, partition/queue, nodes, tasks per node, time limit and memory. "
        "If decomposeParDict content is provided, align ntasks with decomposition. "
        "Return ONLY JSON with keys: cluster_name, account_number, partition, nodes, ntasks_per_node, time_limit, memory."
    )

    user_prompt = f"User requirement: {user_requirement}\n\n"
    if decompose_par_dict_content:
        user_prompt += (
            f"decomposeParDict content:\n{decompose_par_dict_content}\n\n"
            "Use this to infer ntasks_per_node if relevant.\n"
        )
    user_prompt += "Return JSON only."

    response = llm.invoke(user_prompt, system_prompt)
    try:
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()
        cfg = json.loads(response)
    except Exception:
        cfg = {}
    defaults = {
        'cluster_name': 'default_cluster',
        'account_number': 'default_account',
        'partition': 'normal',
        'nodes': 1,
        'ntasks_per_node': 1,
        'time_limit': 24,
        'memory': 64,
    }
    for k, v in defaults.items():
        if k not in cfg or cfg[k] is None:
            cfg[k] = v
    return cfg


def check_logs_for_errors(case_dir: str):
    """Return parsed OpenFOAM error logs for a case directory."""
    return check_foam_errors(case_dir)


def wait_for_job(job_id: str, max_wait_time: int = 3600, wait_interval: int = 30) -> Tuple[str, bool, str]:
    """Poll job status until finished or timeout. Returns (status, ok, err)."""
    import time
    elapsed = 0
    last_status = "PENDING"
    while elapsed < max_wait_time:
        status, ok, err = check_job_status(job_id)
        if not ok:
            return status or "UNKNOWN", False, err
        last_status = status
        if status in ["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"]:
            return status, True, ""
        time.sleep(wait_interval)
        elapsed += wait_interval
    return last_status or "TIMEOUT", True, ""


