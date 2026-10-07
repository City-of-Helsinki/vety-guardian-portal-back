"""
Serves the VTJ mock (mock_server.py) from the Django app itself, so dev and
review environments don't need a separate mock container. Only routed when
VTJ_MOCK_ENABLED is on (see core/urls.py); point VTJ_HEL_ENDPOINT at
http://localhost:8000/vtj-mock/api/HenkilonTunnuskysely to use it.
"""

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .mock_server import PATH, handle_request


@csrf_exempt
@require_POST
def henkilon_tunnuskysely(request: HttpRequest) -> JsonResponse:
    status, data = handle_request(PATH, request.body)
    return JsonResponse(data, status=status)
