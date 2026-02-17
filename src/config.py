# config.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    max_loop: int = 25
    
    batchsize: int = 10
    searchdocs: int = 10 # max(10, searchdocs)
    run_times: int = 1  # current run number (for directory naming)
    database_path: str = Path(__file__).resolve().parent.parent / "database"
    run_directory: str = Path(__file__).resolve().parent.parent / "runs"
    case_dir: str = ""
    max_time_limit: int = 3600 # Max time limit after which the openfoam run will be terminated, in seconds
    recursion_limit: int = 100  # LangGraph recursion limit
    # Input writer generation mode:
    # - "sequential_dependency": generate files sequentially; use already-generated files as context to enforce consistency.
    # - "parallel_no_context": generate files in parallel without cross-file context (faster, may need more reviewer iterations).
    input_writer_generation_mode: str = "parallel_no_context"
    # LLM backend:
    # - "openai": OpenAI Platform usage-based (API key)
    # - "openai-codex": ChatGPT/Codex subscription sign-in (Codex auth cache)
    # - "ollama": local models
    # - "bedrock": AWS Bedrock
    model_provider: str = "openai-codex"  # [openai, openai-codex, ollama, bedrock]
    # model_version examples:
    # - OpenAI: "gpt-5-mini"
    # - OpenAI Codex subscription: "gpt-5.3-codex" (or whichever Codex model you have access to)
    # - Ollama: "qwen2.5:32b-instruct"
    # - Bedrock: application inference profile ARN
    model_version: str = "gpt-5.3-codex"
    temperature: float = 1
    
    # Embedding Configuration
    embedding_provider: str = "openai" # [openai, huggingface, ollama]
    embedding_model: str = "text-embedding-3-small" # e.g. "text-embedding-3-small", "text-embedding-3-large", "Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-8B"
