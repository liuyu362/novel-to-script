"""
AI 小说转剧本工具 - 后端服务
基于 FastAPI 框架
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Novel to Script API",
    description="将小说文本转换为结构化剧本的 AI 工具",
    version="0.1.0",
)

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """根路径"""
    return {"message": "Novel to Script API is running", "version": "0.1.0"}


@app.get("/api/health")
def health_check():
    """健康检查接口"""
    return {"status": "ok", "service": "novel-to-script"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

