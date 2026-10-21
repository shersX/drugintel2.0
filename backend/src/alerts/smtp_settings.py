"""SMTP 配置读写（DB 优先，.env 回退）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.config import SmtpEnvConfig
from backend.src.core.keystore import open_secret, seal
from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.models.smtp_config import SmtpConfig

logger = get_logger("alerts.smtp")


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    use_tls: bool
    enabled: bool
    source: str  # "db" | "env"


def get_or_create_smtp_config(session: Session) -> SmtpConfig:
    row = session.scalar(select(SmtpConfig).order_by(SmtpConfig.id.asc()).limit(1))
    if row is None:
        env = SmtpEnvConfig.load()
        row = SmtpConfig(
            host=env.host or "",
            port=int(env.port or 587),
            user=env.user or "",
            password=seal(env.password) if env.password else "",
            from_addr=env.from_addr or env.user or "",
            use_tls=bool(env.use_tls),
            enabled=True,
        )
        session.add(row)
        session.flush()
        if env.host:
            logger.info("已从 .env 初始化 smtp_config")
    return row


def _settings_from_row(row: SmtpConfig) -> SmtpSettings:
    pwd = open_secret(row.password or "")
    host = (row.host or "").strip()
    user = (row.user or "").strip()
    from_addr = (row.from_addr or "").strip() or user
    # DB 有 host 时以 DB 为准；否则回退 env（兼容仅配 .env 未入库字段）
    if host:
        return SmtpSettings(
            host=host,
            port=int(row.port or 587),
            user=user,
            password=pwd,
            from_addr=from_addr,
            use_tls=bool(row.use_tls),
            enabled=bool(row.enabled),
            source="db",
        )
    env = SmtpEnvConfig.load()
    if env.host:
        return SmtpSettings(
            host=env.host,
            port=int(env.port or 587),
            user=env.user,
            password=env.password,
            from_addr=env.from_addr or env.user,
            use_tls=bool(env.use_tls),
            enabled=bool(row.enabled),
            source="env",
        )
    return SmtpSettings(
        host="",
        port=int(row.port or 587),
        user=user,
        password=pwd,
        from_addr=from_addr,
        use_tls=bool(row.use_tls),
        enabled=bool(row.enabled),
        source="db",
    )


def load_smtp_settings() -> SmtpSettings:
    try:
        with session_scope() as session:
            row = get_or_create_smtp_config(session)
            return _settings_from_row(row)
    except Exception as exc:
        logger.warning("读取 smtp_config 失败，回退环境变量: %s", exc)
        env = SmtpEnvConfig.load()
        return SmtpSettings(
            host=env.host,
            port=int(env.port or 587),
            user=env.user,
            password=env.password,
            from_addr=env.from_addr or env.user,
            use_tls=bool(env.use_tls),
            enabled=True,
            source="env",
        )


def smtp_missing_fields(settings: Optional[SmtpSettings] = None) -> list[str]:
    cfg = settings or load_smtp_settings()
    missing: list[str] = []
    if not (cfg.host or "").strip():
        missing.append("SMTP 主机")
    if not ((cfg.user or "").strip() or (cfg.from_addr or "").strip()):
        missing.append("用户名或发件人")
    if not (cfg.password or "").strip():
        missing.append("密码")
    return missing


def is_smtp_ready(settings: Optional[SmtpSettings] = None) -> bool:
    cfg = settings or load_smtp_settings()
    if not cfg.enabled:
        return False
    return not smtp_missing_fields(cfg)


def mail_status_dict() -> dict[str, Any]:
    cfg = load_smtp_settings()
    ready = is_smtp_ready(cfg)
    if ready:
        message = "邮件通道已就绪"
    elif not cfg.enabled:
        message = "邮件通道已禁用，命中订阅后不会发信"
    else:
        missing = smtp_missing_fields(cfg)
        if missing:
            message = f"邮件通道未就绪，缺少：{'、'.join(missing)}"
        else:
            message = "邮件通道未配置，命中订阅后不会发信"
    return {
        "ready": ready,
        "enabled": bool(cfg.enabled),
        "source": cfg.source,
        "message": message,
        "missing": smtp_missing_fields(cfg) if not ready and cfg.enabled else [],
    }


def smtp_config_to_admin_dict(row: SmtpConfig) -> dict[str, Any]:
    """管理端表单：展示生效值（DB 优先，否则 env），永不返回明文/脱敏密码。"""
    cfg = _settings_from_row(row)
    ready = is_smtp_ready(cfg)
    missing = smtp_missing_fields(cfg) if not ready and cfg.enabled else []
    if ready:
        message = "邮件通道已就绪"
    elif not cfg.enabled:
        message = "邮件通道已禁用，命中订阅后不会发信"
    elif missing:
        message = f"邮件通道未就绪，缺少：{'、'.join(missing)}"
    else:
        message = "邮件通道未就绪"
    return {
        "host": cfg.host,
        "port": int(cfg.port or 587),
        "user": cfg.user,
        "from_addr": cfg.from_addr,
        "use_tls": bool(cfg.use_tls),
        "enabled": bool(row.enabled if row.enabled is not None else cfg.enabled),
        "password_set": bool(cfg.password),
        "ready": ready,
        "message": message,
        "missing": missing,
        "source": cfg.source,
        "env_host": SmtpEnvConfig.load().host or "",
    }


def update_smtp_settings(
    session: Session,
    *,
    host: str,
    port: int,
    user: str,
    from_addr: str,
    use_tls: bool,
    enabled: bool,
    password: Optional[str] = None,
) -> SmtpConfig:
    row = get_or_create_smtp_config(session)
    row.host = (host or "").strip()
    row.port = max(1, min(65535, int(port or 587)))
    row.user = (user or "").strip()
    row.from_addr = (from_addr or "").strip()
    row.use_tls = bool(use_tls)
    row.enabled = bool(enabled)
    if password is not None and str(password).strip():
        row.password = seal(str(password).strip())
    session.flush()
    return row
