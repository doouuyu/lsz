"""项目配置。旧接口保留多模型配置，V2 固定使用百炼模型快照。"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    # --- 应用 ---
    APP_NAME: str = "李时珍智能医师"
    DEBUG: bool = True

    # --- 服务监听地址（绑定到局域网 192 IP，供 PC/小程序访问） ---
    HOST: str = "192.168.50.145"
    PORT: int = 8000

    # --- 数据库 ---
    DATABASE_URL: str = "sqlite:///./data/lsz.db"  # 开发阶段先用SQLite
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- 大模型 API（OpenAI兼容格式，可切换） ---
    LLM_PROVIDER: str = "deepseek"  # deepseek / qwen / openai

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-max"

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"

    # --- 舌诊视觉模型（独立于 LLM_PROVIDER，任意 OpenAI 兼容 VLM 均可） ---
    VL_API_KEY: str = ""  # 阿里云百炼 API Key；为空时舌诊接口降级返回 vl_unavailable
    VL_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    VL_MODEL: str = "qwen3.6-plus"
    TONGUE_MAX_IMAGE_BYTES: int = 8 * 1024 * 1024  # 上传图片大小上限
    TONGUE_IMAGE_MAX_SIDE: int = 1024  # 预处理后最长边像素（控制视觉token消耗）

    # --- 化验单/检查报告（复用 VL 视觉模型读取，决断时注入辨证） ---
    LAB_MAX_IMAGE_BYTES: int = 12 * 1024 * 1024  # 单份化验单/PDF 上限
    LAB_IMAGE_MAX_SIDE: int = 1600  # 预处理后最长边（化验单数字小，比舌诊放大些保清晰）
    LAB_PDF_MAX_PAGES: int = 8  # PDF 最多栅格化页数（防超长报告撑爆视觉 token）

    # 语音转写已改用端侧「微信同声传译」插件（小程序内），后端不再提供 ASR。

    # --- V2 多模态问诊（除 ASR 外不允许切换备用模型） ---
    BAILIAN_API_KEY: str = ""
    BAILIAN_WORKSPACE_ID: str = ""
    BAILIAN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    BAILIAN_ASR_WS_URL: str = ""
    MULTIMODAL_MODEL: str = "qwen3.7-plus-2026-05-26"
    ASR_MODEL: str = "fun-asr-realtime-2026-02-28"
    ASR_VOCABULARY_ID: str = ""
    PREPARE_MODEL_TIMEOUT_SECONDS: int = 180
    INQUIRY_MODEL_TIMEOUT_SECONDS: int = 120
    RETRIEVAL_MODEL_TIMEOUT_SECONDS: int = 180
    FINAL_MODEL_TIMEOUT_SECONDS: int = 600
    MODEL_MAX_RETRIES: int = 1

    # --- V2 附件、会话和日志 ---
    ATTACHMENT_MAX_COUNT: int = 5
    ATTACHMENT_MAX_BYTES: int = 10 * 1024 * 1024
    ATTACHMENT_TOTAL_MAX_BYTES: int = 30 * 1024 * 1024
    PDF_MAX_PAGES: int = 8
    PDF_RENDER_DPI: int = 200
    ATTACHMENT_IMAGE_MAX_SIDE: int = 4096
    CONSULTATION_TTL_SECONDS: int = 1800
    TEXT_LOG_RETENTION_DAYS: int = 7
    CONSULTATION_TEMP_DIR: str = str(
        Path(__file__).resolve().parent.parent / "data" / "consultation_tmp"
    )
    CONSULTATION_LOG_DIR: str = str(
        Path(__file__).resolve().parent.parent / "data" / "consultation_logs"
    )

    # --- 向量库 ---
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    EMBEDDING_MODEL: str = "shibing624/text2vec-base-chinese"  # 中文embedding

    # --- RAG ---
    RAG_TOP_K: int = 5
    RAG_VECTOR_WEIGHT: float = 0.6
    RAG_BM25_WEIGHT: float = 0.4

settings = Settings()
