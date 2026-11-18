from django.db import DatabaseError, connections
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness probe: process is up and can serve HTTP. No external dependencies checked."""
    return JsonResponse({"status": "ok"})


@require_safe
def readiness(request: HttpRequest) -> JsonResponse:
    """Readiness probe: process can actually serve traffic, i.e. the database is reachable."""
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "error", "detail": "database unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
