import uvicorn
from fastapi import FastAPI
import subprocess
import tempfile
import json
from pathlib import Path

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "foam-agent"}

@app.post("/api/v1/foam/execute")
async def execute_foam(request: dict):
    # 保存用户需求到临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(request.get("requirements", ""))
        prompt_path = f.name
    
    # 执行Foam-Agent
    try:
        result = subprocess.run([
            "conda", "run", "-n", "openfoamAgent",
            "python", "foambench_main.py",
            "--prompt_path", prompt_path,
            "--output", "./output"
        ], capture_output=True, text=True, timeout=3600)
        
        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "output_dir": "./output"
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "Execution timed out"}
    finally:
        Path(prompt_path).unlink(missing_ok=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
