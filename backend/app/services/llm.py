"""LLM多模型适配层 - 统一接口，可切换DeepSeek/通义千问/OpenAI"""

from __future__ import annotations

from openai import AsyncOpenAI
from app.config import settings


def get_llm_client() -> tuple[AsyncOpenAI, str]:
    """根据配置返回对应的LLM客户端和模型名"""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "deepseek":
        client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
        model = settings.DEEPSEEK_MODEL
    elif provider == "qwen":
        client = AsyncOpenAI(
            api_key=settings.QWEN_API_KEY,
            base_url=settings.QWEN_BASE_URL,
        )
        model = settings.QWEN_MODEL
    elif provider == "openai":
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        model = settings.OPENAI_MODEL
    else:
        raise ValueError(f"不支持的LLM提供商: {provider}")

    return client, model


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    response_format: dict | None = None,
) -> str:
    """统一的聊天补全接口"""
    client, model = get_llm_client()

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def chat_completion_json(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    """强制JSON输出的聊天补全"""
    return await chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )


_vl_client: AsyncOpenAI | None = None


def get_vl_client() -> tuple[AsyncOpenAI, str]:
    """视觉模型客户端（舌诊用，独立于 LLM_PROVIDER 配置）。

    复用单例：AsyncOpenAI 内部维护 httpx 连接池，每次新建会重做 TCP+TLS 握手
    （对 DashScope 约 100~300ms）。舌诊调用频繁，单例可省掉这部分固定开销。
    """
    global _vl_client
    if not settings.VL_API_KEY:
        raise RuntimeError("未配置 VL_API_KEY，舌诊视觉分析不可用")
    if _vl_client is None:
        _vl_client = AsyncOpenAI(
            api_key=settings.VL_API_KEY,
            base_url=settings.VL_BASE_URL,
        )
    return _vl_client, settings.VL_MODEL


async def vision_completion(
    system: str,
    user_text: str,
    image_data_url: str,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> str:
    """带单张图片的视觉补全（OpenAI 兼容 image_url 内容块，支持 base64 data URL）。

    注意：不传 response_format —— 部分 VL 模型不支持 json_object 会直接 400，
    JSON 约束靠提示词，调用方用容错解析兜底。
    """
    client, model = get_vl_client()
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_url}},
                {"type": "text", "text": user_text},
            ],
        },
    ]
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        # 关闭 qwen3 思考链：舌象是「门控+受控词表抽取」的轻任务，无需 CoT。
        # 实测 qwen3.6-plus 开思考 ~10s（reasoning≈369token），关掉后 ~3s，模型/词表不变。
        extra_body={"enable_thinking": False},
        # 识别超时上限 180s：极端慢路径也别被默认超时截断（前端轮询窗口同为 180s）。
        timeout=180,
    )
    return response.choices[0].message.content
