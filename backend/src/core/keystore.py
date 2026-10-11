"""模型 API Key 的本地加密。密文进数据库，密钥文件留在 data/secrets。"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.src.core.logger import get_logger

logger = get_logger("core.keystore")

_PREFIX = "fernet:"
_fernet: Fernet | None = None


def is_sealed(value: str) -> bool:
    return (value or "").startswith(_PREFIX)


def seal(plain: str) -> str:
    text = (plain or "").strip()
    if not text or is_sealed(text):
        return text
    token = _get_fernet().encrypt(text.encode()).decode()
    return f"{_PREFIX}{token}"


def open_secret(stored: str) -> str:
    text = stored or ""
    if not text:
        return ""
    if not is_sealed(text):
        return text.strip()
    try:
        return _get_fernet().decrypt(text[len(_PREFIX) :].encode()).decode().strip()
    except InvalidToken:
        logger.error("模型密钥无法解密，请确认 data/secrets 里的密钥文件没有被换掉")
        return ""


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key().encode())
    return _fernet


def _load_key() -> str:
    explicit = os.getenv("LLM_KEY_SECRET", "").strip()
    if explicit:
        return explicit
    path = Path(os.getenv("LLM_KEY_FILE", "").strip() or _default_key_path())
    if path.is_file():
        key = path.read_text(encoding="utf-8").strip()
        if key:
            return key
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key().decode()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return path.read_text(encoding="utf-8").strip()
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(key)
    logger.info("已生成模型密钥加密文件: %s", path)
    return key


def _default_key_path() -> Path:
    if Path("/run/drugintel-secrets").is_dir():
        return Path("/run/drugintel-secrets/llm.key")
    return Path("data/secrets/llm.key")
