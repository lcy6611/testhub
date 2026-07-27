import os
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class StripSessionCookieForAPIMiddleware(MiddlewareMixin):
    """
    For /api/ requests, remove the session cookie from the request so that
    SessionMiddleware does not try to decode it. This avoids 400 Bad Request
    when the browser sends a stale/corrupted session cookie (e.g. from a
    different SECRET_KEY or previous backend run), which would otherwise
    trigger SuspiciousSession.
    """
    def process_request(self, request):
        if request.path.startswith('/api/'):
            session_cookie_name = getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid')
            if session_cookie_name in request.COOKIES:
                request.COOKIES = request.COOKIES.copy()
                del request.COOKIES[session_cookie_name]


class DisableCSRFMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # 对所有API路径禁用CSRF检查
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)


class ServerMarkMiddleware(MiddlewareMixin):
    """
    Debug middleware: adds a unique response header so we can confirm
    which Django process actually handled a request.
    """

    SERVER_MARK = f"RUNSERVER_MARK_A pid={os.getpid()}"

    def process_response(self, request, response):
        try:
            response["X-TestHub-Server-Mark"] = self.SERVER_MARK
        except Exception:
            pass
        return response
