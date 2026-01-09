import os
from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from pydantic import BaseModel
import logging
from fastapi.middleware.cors import CORSMiddleware

# --- 1. 初始化与配置 ---

# 配置日志记录，方便我们调试
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从我们之前在 Part A 设置的环境变量中加载 Supabase 的配置
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# 检查环境变量是否已设置，如果缺失则程序无法运行
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.error("FATAL: Supabase credentials are not set in the environment variables.")
    raise RuntimeError("Supabase credentials are not set in the environment variables.")

# 创建 Supabase 客户端实例
# 注意：在后端，我们使用权限更高的 service_role key
# 因为 API 服务器需要有权限无视 RLS 策略来写入数据
logger.info("Initializing Supabase client...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
logger.info("Supabase client initialized successfully.")

# 创建 FastAPI 应用实例
app = FastAPI()

# --- 在这里添加 CORS 中间件 ---

# 1. 定义一个 "白名单" 列表，包含所有我们允许的来源
#    请务必使用你 React 应用的真实访问地址
origins = [
    "http://159.89.201.220:5174/", # 你的 WSL 开发地址
    # 未来你部署到 Vercel 后，还要添加你的域名
    "https://www.cfdqanda.com"
]

# 2. 将 CORS 中间件添加到我们的 FastAPI 应用中
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 允许 "白名单" 中的来源
    allow_credentials=True,    # 允许携带 cookie
    allow_methods=["*"],         # 允许所有 HTTP 方法 (GET, POST, etc.)
    allow_headers=["*"],         # 允许所有 HTTP 请求头
)
# ----------------------------------

# --- 2. 定义数据模型 ---

# 使用 Pydantic 定义前端发送过来的请求体(body)应该长什么样
# 这可以提供自动的数据验证和生成 API 文档
class SimulationRequest(BaseModel):
    prompt: str
    user_id: str # 我们需要前端告诉我们这是哪个用户的请求

class FeedbackRequest(BaseModel):
    file_path: str  # 文件路径，如 "output/log.blockMesh"
    feedback_content: str  # 反馈内容
    user_id: str  # 用户ID，用于权限验证

# --- 3. 创建 API 端点 (Endpoint) ---

@app.post("/api/v1/simulations")
async def create_simulation_task(request: SimulationRequest):
    """
    接收一个新的仿真请求，并将其作为任务插入数据库，状态为 'queued'
    """
    logger.info(f"Received new simulation request for user: {request.user_id}")
    try:
        # 将新任务插入到 'simulations' 表中
        response = supabase.table('simulations').insert({
            'prompt': request.prompt,
            'user_id': request.user_id,
            'status': 'queued'  # 将初始状态明确设置为 '排队中'
        }).execute()

        # 检查 Supabase 的响应，看是否有数据被返回
        if response.data:
            new_task = response.data[0]
            logger.info(f"Successfully queued task {new_task['id']} for user {request.user_id}")
            # 将新创建的任务记录返回给前端，这是一个好的实践
            return {"status": "success", "message": "Simulation task queued successfully.", "task": new_task}
        else:
            # 如果 Supabase 返回了错误（即使没有抛出异常）
            error_message = response.error.message if response.error else "Unknown error from Supabase"
            logger.error(f"Failed to insert task into database: {error_message}")
            raise HTTPException(status_code=500, detail=f"Failed to insert task into database: {error_message}")

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        # 捕获任何其他异常，并返回一个服务器内部错误
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# --- 4. (可选) 创建一个根端点用于测试 ---

@app.get("/")
def read_root():
    """
    一个简单的"健康检查"端点，用于确认服务器是否正在运行。
    """
    return {"message": "Foam-Agent API Server is running!"}


# --- 5. 文件浏览相关端点（可选，用于前端快速获取文件树）---

@app.get("/api/v1/simulations/{job_id}/files")
async def get_file_tree(job_id: int):
    """
    获取任务的文件树结构。
    这个端点是可选的，因为前端可以直接使用Supabase Storage的list() API。
    但提供这个端点可以让前端更快地获取文件树结构（无需遍历Storage）。
    """
    try:
        # 从数据库查询任务信息
        response = supabase.table('simulations').select('*').eq('id', job_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail=f"Simulation {job_id} not found")
        
        job = response.data[0]
        
        # 检查任务是否完成
        if job['status'] not in ['completed', 'failed']:
            raise HTTPException(
                status_code=400, 
                detail=f"Simulation {job_id} is not completed yet. Current status: {job['status']}"
            )
        
        # 从result_data中获取文件树
        result_data = job.get('result_data', {})
        
        if 'file_tree' not in result_data:
            # 如果文件树不存在，返回错误
            raise HTTPException(
                status_code=404,
                detail=f"File tree not found for simulation {job_id}. This might be an old task."
            )
        
        # 返回文件树和存储路径信息
        return {
            "job_id": job_id,
            "status": job['status'],
            "storage_base_path": result_data.get('storage_base_path'),
            "file_tree": result_data.get('file_tree'),
            "upload_stats": result_data.get('upload_stats', {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An error occurred while getting file tree for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")


@app.post("/api/v1/simulations/{job_id}/feedback")
async def submit_feedback(job_id: int, request: FeedbackRequest):
    """
    提交文件反馈。
    将反馈内容保存为文件，文件名格式：{原文件名}_feedback
    保存到Storage的相同目录下。
    """
    try:
        # 1. 验证任务是否存在，并验证用户权限
        response = supabase.table('simulations').select('*').eq('id', job_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail=f"Simulation {job_id} not found")
        
        job = response.data[0]
        
        # 2. 验证用户权限：确保用户只能为自己的任务添加反馈
        if job['user_id'] != request.user_id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to add feedback for this simulation"
            )
        
        # 3. 验证反馈内容大小（5KB = 5120字节）
        feedback_size = len(request.feedback_content.encode('utf-8'))
        if feedback_size > 5120:
            raise HTTPException(
                status_code=400,
                detail=f"Feedback content exceeds 5KB limit. Current size: {feedback_size} bytes"
            )
        
        if feedback_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Feedback content cannot be empty"
            )
        
        # 4. 构建反馈文件路径
        # 原文件路径：如 "output/log.blockMesh"
        # 反馈文件路径：如 "output/log.blockMesh_feedback"
        feedback_file_path = f"{request.file_path}_feedback"
        
        # 5. 构建Storage路径
        storage_base_path = f"public/{request.user_id}/{job_id}"
        storage_feedback_path = f"{storage_base_path}/{feedback_file_path}"
        
        # 6. 上传反馈文件到Storage
        try:
            # 将反馈内容转换为字节
            feedback_bytes = request.feedback_content.encode('utf-8')
            
            # 上传到Storage
            supabase.storage.from_("simulation_results").upload(
                path=storage_feedback_path,
                file=feedback_bytes,
                file_options={"content-type": "text/plain", "upsert": "true"}  # upsert允许覆盖已存在的文件
            )
            
            logger.info(f"Feedback submitted for job {job_id}, file: {request.file_path}")
            
            return {
                "status": "success",
                "message": "Feedback submitted successfully",
                "feedback_path": storage_feedback_path,
                "file_path": request.file_path
            }
            
        except Exception as storage_error:
            logger.error(f"Failed to upload feedback to Storage: {storage_error}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save feedback to storage: {str(storage_error)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An error occurred while submitting feedback for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")