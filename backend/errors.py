"""
错误码定义
统一所有 API 错误响应格式
"""
from enum import IntEnum


class ErrorCode(IntEnum):
    """错误码枚举"""

    # 客户端错误 4xxx
    INVALID_PARAMS  = 4001   # 参数校验失败
    TEXT_TOO_SHORT  = 4002    # 文本太短
    TEXT_TOO_LONG   = 4003    # 文本太长
    TITLE_TOO_LONG  = 4004    # 标题太长
    NOT_FOUND       = 4005    # 资源不存在（作品/章节等）
    UNAUTHORIZED    = 4006    # 未登录 / token 无效

    # 服务端错误 5xxx
    LLM_NOT_READY = 5001     # LLM 服务未配置
    LLM_CALL_FAILED = 5002    # LLM 调用失败
    LLM_TIMEOUT = 5003        # LLM 调用超时
    LLM_RATE_LIMIT = 5004     # LLM 速率限制（配额用尽）
    YAML_INVALID = 5005       # YAML 格式错误
    LLM_PARSE_ERROR = 5006    # LLM 输出解析失败
    INTERNAL_ERROR = 5000     # 内部未知错误


ERROR_MESSAGES = {
    ErrorCode.INVALID_PARAMS: "请求参数错误",
    ErrorCode.TEXT_TOO_SHORT: "小说文本太短，至少需要 50 字",
    ErrorCode.TEXT_TOO_LONG: "小说文本太长，最多支持 50 万字",
    ErrorCode.TITLE_TOO_LONG: "标题过长，最多 200 字",
    ErrorCode.NOT_FOUND: "请求的资源不存在",
    ErrorCode.LLM_NOT_READY: "LLM 服务未配置，请联系管理员配置 API Key",
    ErrorCode.LLM_CALL_FAILED: "AI 服务调用失败，请稍后重试",
    ErrorCode.LLM_TIMEOUT: "AI 服务响应超时，请稍后重试",
    ErrorCode.LLM_RATE_LIMIT: "AI 服务配额用尽，请稍后重试",
    ErrorCode.YAML_INVALID: "剧本格式解析错误",
    ErrorCode.LLM_PARSE_ERROR: "AI 输出解析失败，请重试",
    ErrorCode.INTERNAL_ERROR: "服务内部错误，请联系管理员",
}


class AppException(Exception):
    """自定义应用异常，携带错误码"""

    def __init__(self, code: ErrorCode, message: str = ""):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "未知错误")
        super().__init__(self.message)
