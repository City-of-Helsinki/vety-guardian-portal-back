"""
Test-data cleanup API for e2e tests. Only routed when TEST_DATA_API_ENABLED is on (see core/urls.py),
and every request must carry the shared secret TEST_DATA_API_KEY in the X-Test-Data-Api-Key header.
Excluded from the OpenAPI schema so it doesn't end up in the frontend's generated client.
"""

import secrets

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from guardian.test_data import delete_all_applications, delete_data_for_hetu

API_KEY_HEADER = "X-Test-Data-Api-Key"


class HasTestDataApiKey(BasePermission):
    """The request's X-Test-Data-Api-Key header matches TEST_DATA_API_KEY. Always denied when the key is not set."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        expected: str = settings.TEST_DATA_API_KEY
        provided = request.headers.get(API_KEY_HEADER, "")
        return bool(expected) and secrets.compare_digest(provided.encode(), expected.encode())


class HetuSerializer(serializers.Serializer):
    hetu = serializers.CharField(max_length=11)


class TestDataApiView(APIView):
    authentication_classes = []
    permission_classes = [HasTestDataApiKey]


@extend_schema(exclude=True)
class DeleteTestDataForHetuView(TestDataApiView):
    """
    POST /test-data/delete/  {"hetu": "<child's or guardian's hetu>"}

    Deletes the applications and VTJ person records linked to the hetu.
    The hetu is in the body, not the URL, to keep it out of access logs.
    """

    def post(self, request: Request) -> Response:
        serializer = HetuSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(delete_data_for_hetu(serializer.validated_data["hetu"]))


@extend_schema(exclude=True)
class DeleteAllTestDataView(TestDataApiView):
    """
    POST /test-data/delete-all/

    Deletes all rows from the PreschoolApplication table.
    """

    def post(self, request: Request) -> Response:
        return Response(delete_all_applications())
