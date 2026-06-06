"""
AI 小说转剧本工具 - 后端服务
基于 FastAPI 框架
"""
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any, Optional

from backend.config import is_llm_ready, DEEPSEEK_MODEL
from backend.llm_client import call_llm
from backend.prompts import SYSTEM_PROMPT, build_user_prompt, build_yaml_prompt
from backend.errors import ErrorCode, ERROR_MESSAGES, AppException
from backend.yaml_parser import parse_yaml_to_script, script_to_yaml
from backend.yaml_validator import validate_and_fix_script, report_to_dict
from backend.chapter_splitter import split_chapters, split_by_length, detect_chapter_pattern
from backend.version_prompts import (
    build_versioned_yaml_prompt, get_version_prompt,
    VERSION_NAMES, VALID_VERSIONS,
)
from backend.character_extractor import extract_characters
from backend.scene_extractor import extract_scenes
from backend.dialogue_separator import extract_dialogue
from backend.fusion_script import generate_fusion_script
from backend.novel_analyzer import analyze_novel
from backend.logic_checker import check_logic
from backend.works_manager import (
    create_work,
    list_works,
    get_work,
    update_work,
    delete_work,
)
from backend.user_manager import (
    init_users_table,
    register_user,
    login_user,
    get_current_user,
    parse_token,
)

# 启动时初始化 users 表
init_users_table()

app = FastAPI(
    title="Novel to Script API",
    description="将小说文本转换为结构化剧本的 AI 工具",
    version="0.6.0",
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
        401: ErrorCode.UNAUTHORIZED,
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


@app.get("/api/health")
def health_check():
    """健康检查接口，包含 LLM 连接状态"""
    return success_response({
        "status": "ok",
        "service": "novel-to-script",
        "version": "0.6.0",
        "llm_ready": is_llm_ready(),
        "llm_model": DEEPSEEK_MODEL,
    })


@app.get("/api/versions")
def list_versions():
    """列出所有支持的剧本版本及其说明"""
    return success_response([
        {"id": "movie", "name": "电影版", "description": "紧凑节奏，视觉化优先"},
        {"id": "tv_series", "name": "电视剧版", "description": "多集分季，注重角色成长弧线"},
        {"id": "stage_play", "name": "舞台剧版", "description": "有限场景，强化对话冲突，适合现场演出"},
    ], message="可用版本列表")


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
    version: str = Field(
        default="movie",
        description="剧本版本：movie（电影版）、tv_series（电视剧版）、stage_play（舞台剧版）",
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


class BatchConvertRequest(BaseModel):
    """批量转换请求体"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容",
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
    split_mode: str = Field(
        default="auto",
        description="分割方式：auto（自动识别）、force（按字数强制分割）、manual（手动指定模式）",
    )
    split_pattern: str = Field(
        default="",
        description="手动指定章节模式（如 中文章节），split_mode=manual 时生效",
    )
    max_chars_per_chapter: int = Field(
        default=5000,
        ge=1000,
        le=50000,
        description="按字数分割时每章最大字数",
    )
    max_chapters: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最多转换章节数（防止超额调用）",
    )
    version: str = Field(
        default="movie",
        description="剧本版本：movie（电影版）、tv_series（电视剧版）、stage_play（舞台剧版）",
    )


class AnalyzeCharactersRequest(BaseModel):
    """角色提取请求体"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容",
    )
    title: str = Field(
        default="",
        max_length=200,
        description="小说标题（可选）",
    )


class AnalyzeScenesRequest(BaseModel):
    """场景提取请求体"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容",
    )
    title: str = Field(
        default="",
        max_length=200,
        description="小说标题（可选）",
    )


class AnalyzeDialogueRequest(BaseModel):
    """对话分离请求体"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容",
    )
    title: str = Field(
        default="",
        max_length=200,
        description="小说标题（可选）",
    )


class FusionConvertRequest(BaseModel):
    """融合转换请求体（串联 PR11+PR12+PR13 分析后生成剧本）"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容",
    )
    title: str = Field(
        default="",
        max_length=200,
        description="小说标题（可选）",
    )
    version: str = Field(
        default="movie",
        description="剧本版本：movie（电影版）、tv_series（电视剧版）、stage_play（舞台剧版）",
    )


class AnalyzeNovelRequest(BaseModel):
    """综合解读请求体"""
    text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文内容",
    )
    title: str = Field(
        default="",
        max_length=200,
        description="小说标题（可选）",
    )
    chapter_wise: bool = Field(
        default=True,
        description="是否按章节逐章分析（长文本建议开启）",
    )


class LogicCheckRequest(BaseModel):
    """逻辑检测请求体"""
    script_yaml: str = Field(
        ...,
        min_length=10,
        max_length=500000,
        description="要检测的剧本 YAML 文本",
    )
    original_text: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="小说原文（用作参考基准）",
    )
    title: str = Field(
        default="",
        max_length=200,
        description="作品标题（可选）",
    )


@app.post("/api/convert")
def convert_novel(req: ConvertRequest):
    """接收小说文本，调用 LLM 生成结构化剧本"""
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    # ── PR10: 版本化 Prompt ──
    if req.version not in VALID_VERSIONS:
        req.version = "movie"

    if req.output_format == "yaml":
        sys_prompt, user_prompt = build_versioned_yaml_prompt(req.version, req.text, req.title)
    else:
        sys_prompt, _ = get_version_prompt(req.version, req.title)
        user_prompt = build_user_prompt(req.text, req.title)

    raw_result = call_llm(sys_prompt, user_prompt)

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
                "version": VERSION_NAMES.get(req.version, "电影版"),
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
                "version": VERSION_NAMES.get(req.version, "电影版"),
                "format": "text_fallback",
                "script": raw_result,
                "warning": "YAML 解析失败，返回原始文本，请检查或重试",
                "model": DEEPSEEK_MODEL,
            }, message="剧本生成完成（YAML 解析失败，已降级）")

    # 纯文本格式：直接返回
    return success_response({
        "text_length": len(req.text),
        "title": req.title or "未命名",
        "version": VERSION_NAMES.get(req.version, "电影版"),
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


@app.post("/api/split")
def preview_split(req: ConvertRequest):
    """章节分割预览接口（不调用 LLM，仅展示分割结果）

    用于在正式转换前预览章节分割情况。
    """
    if req.text.strip():
        detected = detect_chapter_pattern(req.text)
        result = split_chapters(req.text)

        chapters_preview = [
            {
                "index": ch.index,
                "title": ch.title,
                "char_count": len(ch.content),
                "preview": ch.content[:80] + ("..." if len(ch.content) > 80 else ""),
                "pattern": ch.pattern_name,
            }
            for ch in result.chapters
        ]

        return success_response({
            "total_chapters": result.total_chapters,
            "detected_pattern": detected,
            "pattern_used": result.pattern_used,
            "prelude_length": len(result.prelude) if result.prelude else 0,
            "message": result.message,
            "chapters": chapters_preview,
        }, message="分割预览完成")
    else:
        return success_response({
            "total_chapters": 0,
            "detected_pattern": "",
            "chapters": [],
        }, message="文本为空")


@app.post("/api/convert/batch")
def batch_convert(req: BatchConvertRequest):
    """批量转换：自动分割章节 → 逐章调用 LLM → 汇总返回

    流程：
    1. 按 split_mode 分割文本为若干章节
    2. 逐章调用 LLM 生成剧本
    3. 返回每章结果 + 总体统计
    """
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    # ── 1. 分割章节 ──
    if req.split_mode == "force":
        chapters = split_by_length(req.text, req.max_chars_per_chapter)
        split_msg = f"按字数强制分割（每章≤{req.max_chars_per_chapter}字）"
    elif req.split_mode == "manual" and req.split_pattern:
        result = split_chapters(req.text, pattern_override=req.split_pattern)
        chapters = result.chapters
        split_msg = result.message
    else:
        result = split_chapters(req.text)
        chapters = result.chapters
        split_msg = result.message

    total = min(len(chapters), req.max_chapters)
    chapters = chapters[:total]

    # ── 2. 逐章转换 ──
    chapter_results = []
    success_count = 0

    for ch in chapters:
        if req.version not in VALID_VERSIONS:
            req.version = "movie"

        chapter_title = f"{req.title or '作品'} - {ch.title}"

        if req.output_format == "yaml":
            sys_prompt, user_prompt = build_versioned_yaml_prompt(
                req.version, ch.content, chapter_title
            )
        else:
            sys_prompt, _ = get_version_prompt(req.version, chapter_title)
            user_prompt = build_user_prompt(ch.content, chapter_title)

        try:
            raw_result = call_llm(sys_prompt, user_prompt)

            if req.output_format == "yaml":
                try:
                    script = parse_yaml_to_script(raw_result, source_title=ch.title)
                    fixed_script, val_report = validate_and_fix_script(script)
                    chapter_results.append({
                        "chapter_index": ch.index,
                        "chapter_title": ch.title,
                        "format": "yaml",
                        "script_yaml": script_to_yaml(fixed_script),
                        "script_stats": fixed_script.stats(),
                        "validation": report_to_dict(val_report),
                        "status": "completed",
                    })
                    success_count += 1
                except AppException:
                    chapter_results.append({
                        "chapter_index": ch.index,
                        "chapter_title": ch.title,
                        "format": "text_fallback",
                        "script": raw_result,
                        "status": "completed",
                        "warning": "YAML 解析失败，降级为纯文本",
                    })
                    success_count += 1
            else:
                chapter_results.append({
                    "chapter_index": ch.index,
                    "chapter_title": ch.title,
                    "format": "text",
                    "script": raw_result,
                    "status": "completed",
                })
                success_count += 1

        except Exception as e:
            chapter_results.append({
                "chapter_index": ch.index,
                "chapter_title": ch.title,
                "format": "error",
                "status": "failed",
                "error": str(e),
            })

    return success_response({
        "total_chapters": total,
        "success_count": success_count,
        "failed_count": total - success_count,
        "split_info": {
            "message": split_msg,
            "total_text_length": len(req.text),
        },
        "chapters": chapter_results,
        "model": DEEPSEEK_MODEL,
    }, message=f"批量转换完成（{success_count}/{total} 成功）")


@app.post("/api/analyze/characters")
def analyze_characters(req: AnalyzeCharactersRequest):
    """角色列表自动提取

    从小说文本中识别所有出场角色，
    输出姓名、性别、年龄、角色类型、描述等结构化信息。
    """
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    result = extract_characters(req.text)

    return success_response({
        "title": req.title or "未命名",
        "text_length": len(req.text),
        **result,
    }, message=f"角色提取完成，共识别 {result['总数']} 个角色")


@app.post("/api/analyze/scenes")
def analyze_scenes(req: AnalyzeScenesRequest):
    """场景列表自动提取

    从小说文本中识别所有场景/地点转换，
    输出地点、时间、天气、出场角色、关键事件等结构化信息。
    """
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    result = extract_scenes(req.text)

    return success_response({
        "title": req.title or "未命名",
        "text_length": len(req.text),
        **result,
    }, message=f"场景提取完成，共识别 {result['总数']} 个场景")


@app.post("/api/analyze/dialogue")
def analyze_dialogue(req: AnalyzeDialogueRequest):
    """对白与叙述文本分离

    从小说文本中区分对话（双引号内/角色说话）和叙述性文字，
    标记每条对话的发言者、语气、引号风格。
    """
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    result = extract_dialogue(req.text)

    return success_response({
        "title": req.title or "未命名",
        "text_length": len(req.text),
        **result,
    }, message=f"对话分离完成，共 {result['对话数']} 条对话 / {result['叙述数']} 段叙述")


@app.post("/api/convert/fusion")
def fusion_convert(req: FusionConvertRequest):
    """融合分析生成剧本

    串联角色提取 + 场景提取 + 对话分离三阶段分析，
    将分析结果注入 Prompt 生成上下文更丰富的剧本。
    """
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    if req.version not in VALID_VERSIONS:
        req.version = "movie"

    result = generate_fusion_script(req.text, req.title, req.version)

    msg_parts = [result["版本"]]
    ch = result["分析数据"]["角色分析"]
    sc = result["分析数据"]["场景分析"]
    if ch.get("总数"):
        msg_parts.append(f"{ch['总数']}个角色")
    if sc.get("总数"):
        msg_parts.append(f"{sc['总数']}个场景")

    return success_response(result, message=f"融合生成完成（{' + '.join(msg_parts)}）")


@app.post("/api/analyze/novel")
def analyze_novel_endpoint(req: AnalyzeNovelRequest):
    """综合解读小说

    支持两种模式：
    - chapter_wise=True（默认）：先按章节分割，逐章分析后合并，适合长文本
    - chapter_wise=False：全文一次性分析，适合短文本
    """
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    result = analyze_novel(req.text, chapter_wise=req.chapter_wise)

    summary = result["汇总"]
    chapter_info = result.get("分章信息", {})

    response_data = {
        "title": req.title or "未命名",
        "text_length": len(req.text),
        "角色分析": result["角色分析"],
        "场景分析": result["场景分析"],
        "对话分析": result["对话分析"],
        "汇总": summary,
    }
    if chapter_info:
        response_data["分章信息"] = chapter_info

    chapter_msg = ""
    if chapter_info:
        chapter_msg = f"分{chapter_info['章节数']}章处理，"

    return success_response(
        response_data,
        message=f"解读完成：{chapter_msg}{summary['角色总数']}个角色、{summary['场景总数']}个场景、{summary['对话总数']}条对话"
    )


@app.post("/api/check/logic")
def check_logic_endpoint(req: LogicCheckRequest):
    """剧本逻辑矛盾检测

    对生成的剧本进行四类逻辑问题检测：
    - 角色一致性：角色无故消失/出现、前后描述矛盾
    - 场景连续性：场景间缺少过渡、地点跳跃不合理
    - 时间线：时间顺序混乱、跨度过大无交代
    - 情节漏洞：因果关系断裂、人物行为逻辑矛盾
    """
    if not is_llm_ready():
        raise AppException(ErrorCode.LLM_NOT_READY)

    result = check_logic(req.script_yaml, req.original_text, req.title)

    summary = result["汇总"]
    return success_response({
        "title": req.title or "未命名",
        "问题列表": result["问题列表"],
        "汇总": summary,
    }, message=f"检测完成：共发现 {summary['总数']} 个问题（{summary['严重']}严重/{summary['警告']}警告/{summary['提示']}提示）")


# ── 作品管理 API ─────────────────────────────────────

class CreateWorkRequest(BaseModel):
    """新建作品请求体"""
    title: str = Field(
        default="",
        max_length=200,
        description="作品标题（可选，默认为『未命名作品』）",
    )
    original_text: str = Field(
        ...,
        min_length=1,
        max_length=500000,
        description="小说原文内容",
    )


class UpdateWorkRequest(BaseModel):
    """更新作品请求体（所有字段可选）"""
    title: Optional[str] = Field(default=None, max_length=200, description="新标题")
    original_text: Optional[str] = Field(default=None, description="新原文")
    analysis_data: Optional[str] = Field(default=None, description="综合解读结果 JSON")
    script_data: Optional[str] = Field(default=None, description="剧本生成结果 JSON")
    logic_data: Optional[str] = Field(default=None, description="逻辑检测结果 JSON")
    current_step: Optional[int] = Field(default=None, ge=1, le=5, description="当前步骤 (1-5)")


@app.get("/api/works")
def api_list_works(request: Request):
    """获取作品列表（摘要，不含原文和分析结果）—— 需登录"""
    user_id = get_current_user(request)
    works = list_works(user_id)
    return success_response(works, message=f"共 {len(works)} 部作品")


@app.post("/api/works")
def api_create_work(req: CreateWorkRequest, request: Request):
    """新建作品 —— 需登录"""
    user_id = get_current_user(request)
    work_id = create_work(req.title or "未命名作品", req.original_text, user_id)
    work = get_work(work_id, user_id)
    return success_response(work, message="作品创建成功")


@app.get("/api/works/{work_id:int}")
def api_get_work(work_id: int, request: Request):
    """获取单部作品完整数据（含原文、分析结果等）—— 需登录"""
    user_id = get_current_user(request)
    work = get_work(work_id, user_id)
    if work is None:
        return error_response(ErrorCode.NOT_FOUND, f"作品 #{work_id} 不存在")
    return success_response(work, message="获取成功")


@app.put("/api/works/{work_id:int}")
def api_update_work(work_id: int, req: UpdateWorkRequest, request: Request):
    """更新作品字段（支持部分更新）—— 需登录"""
    user_id = get_current_user(request)

    if get_work(work_id, user_id) is None:
        return error_response(ErrorCode.NOT_FOUND, f"作品 #{work_id} 不存在")

    updates = {}
    if req.title is not None:
        updates["title"] = req.title
    if req.original_text is not None:
        updates["original_text"] = req.original_text
    if req.analysis_data is not None:
        updates["analysis_data"] = req.analysis_data
    if req.script_data is not None:
        updates["script_data"] = req.script_data
    if req.logic_data is not None:
        updates["logic_data"] = req.logic_data
    if req.current_step is not None:
        updates["current_step"] = req.current_step

    if not updates:
        return success_response(get_work(work_id, user_id), message="无任何变更")

    ok = update_work(work_id, user_id, **updates)
    if not ok:
        return error_response(ErrorCode.INTERNAL_ERROR, "更新失败")

    return success_response(get_work(work_id, user_id), message="更新成功")


@app.delete("/api/works/{work_id:int}")
def api_delete_work(work_id: int, request: Request):
    """删除作品 —— 需登录"""
    user_id = get_current_user(request)

    if get_work(work_id, user_id) is None:
        return error_response(ErrorCode.NOT_FOUND, f"作品 #{work_id} 不存在")

    ok = delete_work(work_id, user_id)
    if not ok:
        return error_response(ErrorCode.INTERNAL_ERROR, "删除失败")

    return success_response({"deleted_id": work_id}, message="删除成功")


# ── 用户注册 / 登录 ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=20, description="昵称（2-20字）")
    password: str = Field(..., min_length=4, max_length=32, description="密码（4-32位）")

class LoginRequest(BaseModel):
    nickname: str = Field(..., min_length=1, description="昵称")
    password: str = Field(..., min_length=1, description="密码")


@app.post("/api/users/register")
def api_register(req: RegisterRequest):
    """用户注册"""
    try:
        result = register_user(req.nickname, req.password)
        return success_response({
            "id": result["id"],
            "nickname": result["nickname"],
            "token": result["token"],
        }, message="注册成功")
    except ValueError as e:
        return error_response(ErrorCode.INVALID_PARAMS, str(e))


@app.post("/api/users/login")
def api_login(req: LoginRequest):
    """用户登录"""
    try:
        result = login_user(req.nickname, req.password)
        return success_response({
            "id": result["id"],
            "nickname": result["nickname"],
            "token": result["token"],
        }, message="登录成功")
    except ValueError as e:
        return error_response(ErrorCode.UNAUTHORIZED, str(e))


# ── 前端静态文件挂载 ──
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="frontend_static")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """SPA 路由：所有非 /api 的 GET 请求返回前端入口（包括根路径 /）"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Frontend not found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
