"""
helusers (1.3.0) validates tokens with PyJWT's default leeway of 0 and has no setting for it, so a token
from a Tunnistus server whose clock is slightly ahead of ours fails with "The token is not yet valid (iat)"
(reported as "JWT verification failed."). Swap the PyJWT module helusers uses for one that adds a leeway.
Covers both the API token (ApiTokenAuthentication) and the profile API token (validate_profile_token).

Relies on helusers.jwt importing PyJWT as `pyjwt`; recheck when upgrading helusers.
"""

import jwt
from django.conf import settings
from helusers import jwt as helusers_jwt


class _PyJWTWithLeeway:
    def __getattr__(self, name):
        return getattr(jwt, name)

    def decode(self, *args, **kwargs):
        kwargs.setdefault("leeway", settings.OIDC_API_TOKEN_AUTH_LEEWAY)
        return jwt.decode(*args, **kwargs)


def install():
    helusers_jwt.pyjwt = _PyJWTWithLeeway()
