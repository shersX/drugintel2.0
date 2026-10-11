"""账户、会话、额度与审计。密码只存 Argon2 哈希，会话只存令牌哈希。"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, text, update

from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.models.account import AppUser, AuditLog, ReportFile, UserSession

logger = get_logger("auth")

COOKIE_NAME = "drugintel_session"
MIN_PASSWORD = 8
DEFAULT_CHAT_LIMIT = 50
SESSION_DAYS = 7
LOCK_AFTER = 5
LOCK_MINUTES = 15

_hasher = PasswordHasher()


class AuthError(Exception):
    """登录或改密失败。调用方转成 401。"""


class QuotaError(Exception):
    """当日问答次数已用完。调用方转成 429。"""


class AccountError(Exception):
    """开户、停用等管理操作不能完成。调用方转成 400。"""


@dataclass(frozen=True)
class Actor:
    id: int
    email: str
    display_name: str
    role: str
    status: str
    daily_chat_limit: int

    def public(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "daily_chat_limit": self.daily_chat_limit,
        }


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _check_password(password: str) -> str:
    text_value = password or ""
    if len(text_value) < MIN_PASSWORD:
        raise AccountError(f"密码至少 {MIN_PASSWORD} 位")
    return text_value


def _check_email(email: str) -> str:
    value = (email or "").strip().lower()
    if "@" not in value or len(value) > 200 or value.startswith("@") or value.endswith("@"):
        raise AccountError("请填写有效邮箱")
    return value


def _actor_from(row: AppUser) -> Actor:
    return Actor(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        status=row.status,
        daily_chat_limit=row.daily_chat_limit,
    )


def record_audit(
    *,
    actor_id: Optional[int],
    action: str,
    target: str = "",
    ok: bool = True,
    detail: str = "",
) -> None:
    with session_scope() as session:
        session.add(
            AuditLog(
                actor_id=actor_id,
                action=action[:40],
                target=(target or "")[:200],
                ok=ok,
                detail=(detail or "")[:500] or None,
            )
        )


def ensure_first_admin() -> None:
    """库里还没有管理员时，用环境变量创建第一个。已有管理员则不动密码。"""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    with session_scope() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(84123002)"))
        exists = session.scalar(select(AppUser.id).where(AppUser.role == "admin").limit(1))
        if exists is not None:
            return
        if "@" not in email or len(password) < MIN_PASSWORD:
            logger.warning(
                "还没有管理员。请设置 ADMIN_EMAIL，以及至少 %s 位的 ADMIN_PASSWORD，然后重启",
                MIN_PASSWORD,
            )
            return
        row = AppUser(
            email=email,
            display_name="管理员",
            password_hash=hash_password(password),
            role="admin",
            status="active",
            daily_chat_limit=DEFAULT_CHAT_LIMIT,
        )
        session.add(row)
        session.flush()
        session.add(
            AuditLog(
                actor_id=row.id,
                action="admin_bootstrap",
                target=f"user:{row.id}",
                ok=True,
                detail=email,
            )
        )
        logger.info("已创建首个管理员 %s", email)


def bind_watchlist_owners() -> None:
    """把对不上账户的旧订阅挂到最早的管理员，并补上外键。"""
    from backend.src.db.session import get_engine

    with session_scope() as session:
        admin_id = session.scalar(
            select(AppUser.id).where(AppUser.role == "admin").order_by(AppUser.id).limit(1)
        )
        if admin_id is None:
            return
        session.execute(
            text(
                """
                UPDATE watchlist
                SET user_id = :admin_id
                WHERE NOT EXISTS (SELECT 1 FROM app_user u WHERE u.id = watchlist.user_id)
                """
            ),
            {"admin_id": admin_id},
        )
    with get_engine().begin() as conn:
        conn.execute(
            text(
                """
                DO $$ BEGIN
                  ALTER TABLE watchlist
                    ADD CONSTRAINT watchlist_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES app_user(id);
                EXCEPTION
                  WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )


def login(email: str, password: str) -> tuple[str, Actor]:
    normalized = (email or "").strip().lower()
    error: Optional[AuthError] = None
    token = ""
    actor: Optional[Actor] = None
    with session_scope() as session:
        row = session.scalar(select(AppUser).where(AppUser.email == normalized))
        if row is None:
            session.add(
                AuditLog(actor_id=None, action="login_fail", target=normalized[:200], ok=False, detail="unknown")
            )
            error = AuthError("邮箱或密码错误")
        elif row.locked_until is not None and row.locked_until > _now():
            session.add(
                AuditLog(actor_id=row.id, action="login_fail", target=f"user:{row.id}", ok=False, detail="locked")
            )
            error = AuthError("登录失败次数过多，请稍后再试")
        elif row.status != "active" or not verify_password(password, row.password_hash):
            row.failed_login_count += 1
            detail = "disabled" if row.status != "active" else "bad_password"
            if row.failed_login_count >= LOCK_AFTER:
                row.locked_until = _now() + timedelta(minutes=LOCK_MINUTES)
                detail = "locked"
            session.add(
                AuditLog(actor_id=row.id, action="login_fail", target=f"user:{row.id}", ok=False, detail=detail)
            )
            error = AuthError(
                "登录失败次数过多，请稍后再试" if detail == "locked" else "邮箱或密码错误"
            )
        else:
            row.failed_login_count = 0
            row.locked_until = None
            row.last_login_at = _now()
            token = secrets.token_urlsafe(32)
            session.add(
                UserSession(
                    user_id=row.id,
                    token_hash=_token_hash(token),
                    expires_at=_now() + timedelta(days=SESSION_DAYS),
                )
            )
            session.add(AuditLog(actor_id=row.id, action="login_ok", target=f"user:{row.id}", ok=True))
            actor = _actor_from(row)
    if error is not None or actor is None:
        raise error or AuthError("邮箱或密码错误")
    return token, actor


def resolve_actor(token: Optional[str]) -> Optional[Actor]:
    if not token:
        return None
    with session_scope() as session:
        row = session.scalar(select(UserSession).where(UserSession.token_hash == _token_hash(token)))
        if row is None or row.revoked_at is not None or row.expires_at <= _now():
            return None
        user = session.get(AppUser, row.user_id)
        if user is None or user.status != "active":
            return None
        return _actor_from(user)


def revoke_token(token: Optional[str]) -> None:
    if not token:
        return
    with session_scope() as session:
        session.execute(
            update(UserSession)
            .where(UserSession.token_hash == _token_hash(token), UserSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )


def revoke_user_sessions(user_id: int, *, except_token: Optional[str] = None) -> None:
    with session_scope() as session:
        stmt = update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        if except_token:
            stmt = stmt.where(UserSession.token_hash != _token_hash(except_token))
        session.execute(stmt.values(revoked_at=_now()))


def update_profile(
    actor: Actor,
    *,
    display_name: Optional[str],
    old_password: Optional[str],
    new_password: Optional[str],
    current_token: Optional[str],
) -> Actor:
    new_name = (display_name or "").strip()
    with session_scope() as session:
        row = session.get(AppUser, actor.id)
        if row is None or row.status != "active":
            raise AuthError("请先登录")
        if new_password:
            if not old_password or not verify_password(old_password, row.password_hash):
                raise AuthError("原密码不正确")
            row.password_hash = hash_password(_check_password(new_password))
        if new_name:
            row.display_name = new_name[:80]
        actor_out = _actor_from(row)
        changed_password = bool(new_password)
    if changed_password:
        revoke_user_sessions(actor.id, except_token=current_token)
        record_audit(actor_id=actor.id, action="password_change", target=f"user:{actor.id}")
    return actor_out


def list_users() -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(select(AppUser).order_by(AppUser.id)).all()
        return [_user_admin(row) for row in rows]


def _user_admin(row: AppUser) -> dict:
    return {
        "id": row.id,
        "email": row.email,
        "display_name": row.display_name,
        "role": row.role,
        "status": row.status,
        "daily_chat_limit": row.daily_chat_limit,
        "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
    }


def create_user(
    *,
    email: str,
    display_name: str,
    password: str,
    role: str,
    daily_chat_limit: int,
    actor_id: int,
) -> dict:
    normalized = _check_email(email)
    name = (display_name or "").strip() or normalized.split("@", 1)[0]
    chosen = role if role in {"admin", "user"} else "user"
    limit = _check_limit(daily_chat_limit)
    with session_scope() as session:
        taken = session.scalar(select(AppUser.id).where(AppUser.email == normalized))
        if taken is not None:
            raise AccountError("这个邮箱已经有账户")
        row = AppUser(
            email=normalized,
            display_name=name[:80],
            password_hash=hash_password(_check_password(password)),
            role=chosen,
            status="active",
            daily_chat_limit=limit,
        )
        session.add(row)
        session.flush()
        payload = _user_admin(row)
        user_id = row.id
    record_audit(actor_id=actor_id, action="user_create", target=f"user:{user_id}", detail=normalized)
    return payload


def set_user_status(user_id: int, status: str, actor: Actor) -> dict:
    if status not in {"active", "disabled"}:
        raise AccountError("未知的账户状态")
    with session_scope() as session:
        row = session.get(AppUser, user_id)
        if row is None:
            raise AccountError("账户不存在")
        if row.id == actor.id and status == "disabled":
            raise AccountError("不能停用自己")
        if row.role == "admin" and status == "disabled":
            others = session.scalar(
                select(AppUser.id).where(
                    AppUser.role == "admin",
                    AppUser.status == "active",
                    AppUser.id != row.id,
                ).limit(1)
            )
            if others is None:
                raise AccountError("至少保留一个启用中的管理员")
        row.status = status
        payload = _user_admin(row)
    if status == "disabled":
        revoke_user_sessions(user_id)
    record_audit(
        actor_id=actor.id,
        action="user_disable" if status == "disabled" else "user_enable",
        target=f"user:{user_id}",
    )
    return payload


def reset_user_password(user_id: int, password: str, actor_id: int) -> None:
    with session_scope() as session:
        row = session.get(AppUser, user_id)
        if row is None:
            raise AccountError("账户不存在")
        row.password_hash = hash_password(_check_password(password))
        row.failed_login_count = 0
        row.locked_until = None
    revoke_user_sessions(user_id)
    record_audit(actor_id=actor_id, action="password_reset", target=f"user:{user_id}")


def set_chat_limit(user_id: int, daily_chat_limit: int, actor_id: int) -> dict:
    limit = _check_limit(daily_chat_limit)
    with session_scope() as session:
        row = session.get(AppUser, user_id)
        if row is None:
            raise AccountError("账户不存在")
        row.daily_chat_limit = limit
        payload = _user_admin(row)
    record_audit(
        actor_id=actor_id,
        action="chat_limit",
        target=f"user:{user_id}",
        detail=str(limit),
    )
    return payload


def _check_limit(value: int) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise AccountError("问答上限必须是数字") from exc
    if limit < 0 or limit > 10000:
        raise AccountError("问答上限需在 0 到 10000 之间")
    return limit


def consume_chat_quota(user_id: int) -> None:
    with session_scope() as session:
        limit = session.scalar(select(AppUser.daily_chat_limit).where(AppUser.id == user_id))
        if limit is None:
            raise QuotaError("请先登录")
        if int(limit) < 1:
            raise QuotaError("今日问答次数已用完")
        inserted = session.execute(
            text(
                """
                INSERT INTO chat_usage (user_id, usage_date, count)
                VALUES (:user_id, :usage_date, 1)
                ON CONFLICT (user_id, usage_date)
                DO UPDATE SET count = chat_usage.count + 1
                WHERE chat_usage.count < :limit
                RETURNING count
                """
            ),
            {"user_id": user_id, "usage_date": date.today(), "limit": int(limit)},
        ).scalar()
        if inserted is None:
            raise QuotaError("今日问答次数已用完")


def remember_report(user_id: int, filename: str) -> None:
    with session_scope() as session:
        session.add(ReportFile(user_id=user_id, filename=filename))


def user_owns_report(user_id: int, filename: str) -> bool:
    with session_scope() as session:
        row = session.scalar(
            select(ReportFile.id).where(
                ReportFile.user_id == user_id,
                ReportFile.filename == filename,
            )
        )
        return row is not None
