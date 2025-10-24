import os
import uuid
from pathlib import Path
from typing import Tuple
from models import CreateCaseIn, CreateCaseOut


def create_case(inp: CreateCaseIn) -> CreateCaseOut:
    """Create a new case directory and return identifiers.

    This function is intentionally side-effect minimal and only ensures the
    directory exists. It doesn't generate files.
    """
    case_id = str(uuid.uuid4())[:8]
    base_dir = inp.output_dir or "./runs"
    case_dir = str(Path(base_dir) / case_id)
    Path(case_dir).mkdir(parents=True, exist_ok=True)
    return CreateCaseOut(case_id=case_id, case_dir=case_dir)


