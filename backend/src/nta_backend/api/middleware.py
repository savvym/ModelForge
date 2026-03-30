from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from nta_backend.core.auth_context import (
    CURRENT_USER_COOKIE,
    CURRENT_USER_HEADER,
    DEFAULT_USER_ID,
    build_session_token,
    parse_session_user_id,
    reset_current_user_id,
    set_current_user_id,
)
from nta_backend.core.config import get_settings
from nta_backend.core.project_context import (
    CURRENT_PROJECT_COOKIE,
    CURRENT_PROJECT_HEADER,
    DEFAULT_PROJECT_ID,
    parse_project_id,
    reset_current_project_id,
    set_current_project_id,
)


def install_middleware(app: FastAPI) -> None:
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        current_user_id = parse_session_user_id(request.cookies.get(CURRENT_USER_COOKIE))
        should_set_auth_cookie = False
        if current_user_id is None and settings.auth_auto_login_enabled:
            current_user_id = DEFAULT_USER_ID
            should_set_auth_cookie = True

        requested_project_id = parse_project_id(
            request.headers.get(CURRENT_PROJECT_HEADER)
            or request.cookies.get(CURRENT_PROJECT_COOKIE)
        )
        current_project_id = requested_project_id or DEFAULT_PROJECT_ID
        user_token = set_current_user_id(current_user_id)
        token = set_current_project_id(current_project_id)
        request.state.current_project_id = current_project_id
        request.state.current_user_id = current_user_id
        try:
            response = await call_next(request)
        finally:
            reset_current_user_id(user_token)
            reset_current_project_id(token)

        response.headers["X-Request-Path"] = request.url.path
        response.headers[CURRENT_PROJECT_HEADER] = str(current_project_id)
        if current_user_id is not None:
            response.headers[CURRENT_USER_HEADER] = str(current_user_id)
            if should_set_auth_cookie:
                response.set_cookie(
                    CURRENT_USER_COOKIE,
                    build_session_token(current_user_id),
                    httponly=True,
                    max_age=settings.auth_session_max_age_seconds,
                    samesite="lax",
                    secure=settings.app_env == "production",
                    path="/",
                )
        return response
