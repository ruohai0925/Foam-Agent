from typing import Dict
from models import PlanIn, PlanOut, Subtask
from utils import LLMService
from nodes.architect_node import architect_node


def plan_simulation_structure(inp: PlanIn, llm: LLMService, config) -> PlanOut:
    """Plan folders/files using existing architect logic.

    Expects `config` to be an instance of src.config.Config or a compatible object
    that exposes required attributes used by architect_node.
    """
    # Build minimal state for architect_node
    # Note: caller is responsible for placing parsed `user_requirement` into config
    state = {
        "config": config,
        "user_requirement": getattr(config, "user_requirement", ""),
        "llm_service": llm,
        "case_stats": getattr(config, "case_stats", {}),
        "case_dir": getattr(config, "case_dir", ""),
    }
    out = architect_node(state)
    plan = [Subtask(file=s["file_name"], folder=s["folder_name"]) for s in out.get("subtasks", [])]
    case_info = {
        "case_name": out.get("case_name"),
        "solver": out.get("case_solver"),
        "domain": out.get("case_domain"),
        "category": out.get("case_category"),
    }
    return PlanOut(plan=plan, case_info=case_info)


