"""
AI 小说转剧本工具 - 后端服务
基于 FastAPI 框架
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


class ConvertRequest(BaseModel):
    """小说转换请求体"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容，最少50字，最多50万字",
        examples=["第一章  血月当空\n\n林风醒来时，发现自己躺在一座陌生的山谷中..."],
    )
    title: str = Field(
        default="",
        max_length=200,
        description="小说标题（可选）",
    )


class ConvertResponse(BaseModel):
    """转换结果响应体"""
    success: bool
    message: str
    text_length: int
    title: str


@app.post("/api/convert", response_model=ConvertResponse)
def convert_novel(req: ConvertRequest):
    """接收小说文本，验证参数，返回确认信息"""
    return ConvertResponse(
        success=True,
        message=f"文本已接收，共 {len(req.text)} 字",
        text_length=len(req.text),
        title=req.title or "未命名",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

