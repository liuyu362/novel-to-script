"""
AI 小说转剧本工具 - 后端服务
基于 FastAPI 框架
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Optional

from backend.config import is_llm_ready, DEEPSEEK_MODEL
from backend.llm_client import call_llm
from backend.prompts import SYSTEM_PROMPT, build_user_prompt, build_yaml_prompt
from backend.errors import ErrorCode, ERROR_MESSAGES, AppException
from backend.yaml_parser import parse_yaml_to_script, script_to_yaml
from backend.yaml_validator import validate_and_fix_script, report_to_dict

app = FastAPI(
    title="Novel to Script API",
    description="将小说文本转换为结构化剧本的 AI 工具",
    version="0.4.0",
)


class ApiResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


def success_response(data: Any, message: str = "success") -> dict:
    """成功响应快捷方法"""
    return {"code": 0, "message": message, "data": data}


def error_response(code: ErrorCode, detail: str = "") -> JSONResponse:
    """错误响应快捷方法"""
    return JSONResponse(
        status_code=200,  # 始终返回 200，错误码在 body 中
        content={
            "code": int(code),
            "message": detail or ERROR_MESSAGES.get(code, "未知错误"),
            "data": None,
        },
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义 AppException，返回统一错误格式"""
    return JSONResponse(
        status_code=200,
        content={
            "code": int(exc.code),
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """将 FastAPI 的 HTTPException 转为统一格式"""
    code_map = {
        400: ErrorCode.INVALID_PARAMS,
        422: ErrorCode.INVALID_PARAMS,
        503: ErrorCode.LLM_NOT_READY,
        500: ErrorCode.INTERNAL_ERROR,
    }
    err_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return error_response(err_code, str(exc.detail))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常捕获，防止敏感信息泄露"""
    import logging
    logging.exception("Unhandled exception")
    return error_response(ErrorCode.INTERNAL_ERROR, ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR])


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """捕获 Pydantic 参数校验失败（422），转为统一错误格式"""
    try:
        first_err = exc.errors()[0]
        loc = " → ".join(str(x) for x in first_err.get("loc", []))
        msg = first_err.get("msg", "参数错误")
        detail = f"{loc}: {msg}"
    except Exception:
        detail = "请求参数不符合要求"
    return JSONResponse(
        status_code=200,
        content={
            "code": int(ErrorCode.INVALID_PARAMS),
            "message": detail or ERROR_MESSAGES[ErrorCode.INVALID_PARAMS],
            "data": None,
        },
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
    return success_response({
        "service": "novel-to-script",
        "version": "0.3.0",
        "docs": "/docs",
    })


@app.get("/api/health")
def health_check():
    """健康检查接口，包含 LLM 连接状态"""
    return success_response({
        "status": "ok",
        "service": "novel-to-script",
        "version": "0.3.0",
        "llm_ready": is_llm_ready(),
        "llm_model": DEEPSEEK_MODEL,
    })


class ConvertRequest(BaseModel):
    """小说转换请求体"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容，最少50字，最多50万字",
    )
    title: str = Field(
        default="",
        max_length=200,
        description="小说标题（可选）",
    )
    output_format: str = Field(
        default="yaml",
        description="输出格式：yaml（结构化）或 text（纯文本）",
    )


class ValidateRequest(BaseModel):
    """YAML 验证请求体"""
    yaml_text: str = Field(
        ...,
        min_length=1,
        description="要验证的 YAML 文本（剧本格式）",
    )
    source_title: str = Field(
        default="测试作品",
        description="原作标题",
    )


@app.post("/api/convert")
def convert_novel(req: ConvertRequest):
    """接收小说文本，调用 LLM 生成结构化剧本"""
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    # 根据格式选择 Prompt
    if req.output_format == "yaml":
        user_prompt = build_yaml_prompt(req.text, req.title)
    else:
        user_prompt = build_user_prompt(req.text, req.title)

    raw_result = call_llm(SYSTEM_PROMPT, user_prompt)

    # YAML 格式：解析为结构化数据 + 验证修复
    if req.output_format == "yaml":
        try:
            script = parse_yaml_to_script(raw_result, source_title=req.title or "")

            # ── PR8: 验证 + 自动修复 ──
            fixed_script, validation_report = validate_and_fix_script(script)

            script_yaml = script_to_yaml(fixed_script)
            stats = fixed_script.stats()
            return success_response({
                "text_length": len(req.text),
                "title": req.title or "未命名",
                "format": "yaml",
                "script_yaml": script_yaml,
                "script_stats": stats,
                "validation": report_to_dict(validation_report),
                "model": DEEPSEEK_MODEL,
            }, message="剧本生成完成（结构化 YAML）")
        except AppException:
            return success_response({
                "text_length": len(req.text),
                "title": req.title or "未命名",
                "format": "text_fallback",
                "script": raw_result,
                "warning": "YAML 解析失败，返回原始文本，请检查或重试",
                "model": DEEPSEEK_MODEL,
            }, message="剧本生成完成（YAML 解析失败，已降级）")

    # 纯文本格式：直接返回
    return success_response({
        "text_length": len(req.text),
        "title": req.title or "未命名",
        "format": "text",
        "script": raw_result,
        "model": DEEPSEEK_MODEL,
    }, message="剧本生成完成")


@app.post("/api/validate")
def validate_yaml(req: ValidateRequest):
    """独立的 YAML 验证接口（不调用 LLM，仅验证格式）

    用于调试：直接粘贴 YAML 文本，查看验证报告。
    """
    try:
        script = parse_yaml_to_script(req.yaml_text, source_title=req.source_title)
    except AppException as e:
        return success_response({
            "parse_error": e.message,
            "validation": None,
        }, message="YAML 解析失败，无法验证")

    fixed_script, validation_report = validate_and_fix_script(script)
    fixed_yaml = script_to_yaml(fixed_script)
    stats = fixed_script.stats()

    return success_response({
        "validation": report_to_dict(validation_report),
        "script_stats": stats,
        "fixed_yaml": fixed_yaml if validation_report.fixes_applied else None,
    }, message="验证完成")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
