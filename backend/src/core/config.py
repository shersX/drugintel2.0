"""环境变量与运行时配置（最小集）。"""
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class LLMEnvConfig:
    """SiliconFlow（OpenAI 兼容）调用参数，从环境变量读取。"""

    api_key: str
    base_url: str
    model: str
    timeout_sec: float
    max_retries: int

    @staticmethod
    def load():
        return LLMEnvConfig(
            api_key=os.getenv("SILICONFLOW_API_KEY", "").strip(),
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").strip().rstrip("/"),
            model=os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V4-Flash").strip(),
            timeout_sec=float(os.getenv("LLM_TIMEOUT_SEC", "180")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        )

if __name__ == "__main__":
    print(LLMEnvConfig.load())