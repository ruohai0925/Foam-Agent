from typing import List
from models import ApplyFixIn, ApplyFixOut
from utils import save_file
import os


def apply_fix(inp: ApplyFixIn, case_dir: str) -> ApplyFixOut:
    written = []
    for mod in inp.modifications:
        file = mod.get("file") or mod.get("file_name")
        folder = mod.get("folder") or mod.get("folder_name")
        content = mod.get("content", "")
        if not file or not folder:
            continue
        path = os.path.join(case_dir, folder, file)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_file(path, content)
        written.append(path)
    return ApplyFixOut(status="ok", written=written)


