"""
DeepSeek API 客户端封装
"""
from openai import OpenAI
from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, is_llm_ready


def get_client() -> OpenAI | None:
    """获取 DeepSeek API 客户端实例，未配置 Key 时返回 None"""
    if not is_llm_ready():
        return None
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    调用 DeepSeek 大模型

    Args:
        system_prompt: 系统提示词（设定角色和任务）
        user_prompt: 用户输入内容

    Returns:
        模型生成的文本

    Raises:
        RuntimeError: API Key 未配置时
        Exception: API 调用失败时
    """
    client = get_client()
    if client is None:
        raise RuntimeError(
            "DeepSeek API Key 未配置。请创建 backend/.env 文件，"
            "参考 .env.example 填写 DEEPSEEK_API_KEY"
        )

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4096,
    )

    return response.choices[0].message.content
