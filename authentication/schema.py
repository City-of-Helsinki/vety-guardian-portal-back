from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApiTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """Documents helusers' ApiTokenAuthentication as a bearer token in the OpenAPI schema."""

    target_class = "helusers.oidc.ApiTokenAuthentication"
    name = "helsinkiProfileApiToken"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
