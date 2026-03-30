from fastapi import Request

from nta_backend.core.config import get_settings


def build_browser_s3_endpoint(request: Request) -> str:
    settings = get_settings()
    if settings.s3_browser_endpoint_url:
        return settings.s3_browser_endpoint_url.rstrip("/")

    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if host:
        return f"{scheme}://{host}"
    return str(request.base_url).rstrip("/")
