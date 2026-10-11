"""从 Cookie 取出当前登录用户。"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request, Response

from backend.src.auth.service import COOKIE_NAME, SESSION_DAYS, Actor, resolve_actor


def current_actor(request: Request) -> Actor:
    actor = resolve_actor(request.cookies.get(COOKIE_NAME))
    if actor is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return actor


def admin_actor(actor: Actor = Depends(current_actor)) -> Actor:
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return actor


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "").strip() in {"1", "true", "yes"},
        path="/",
        max_age=SESSION_DAYS * 24 * 3600,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", httponly=True, samesite="lax")
