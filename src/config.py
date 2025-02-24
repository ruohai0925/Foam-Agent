# config.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    max_loop: int = 20
    temperature: float = 0.01
    batchsize: int = 10
    searchdocs: int = 2
    run_times: int = 1  # current run number (for directory naming)
    model: str = "arn:aws:bedrock:us-west-2:991404956194:application-inference-profile/56i8iq1vib3e"
    model_version: str = "arn:aws:bedrock:us-west-2:991404956194:application-inference-profile/56i8iq1vib3e" #"gpt-4o"
    database_path: str = Path(__file__).resolve().parent.parent / "database"
    run_directory: str = Path(__file__).resolve().parent.parent / "runs"
    case_dir: str = ""
    model_provider: str = "bedrock"

