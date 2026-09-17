"""Exception classes for the VTJ (Väestötietojärjestelmä) interface."""


class VTJError(Exception):
    """Generic error related to the VTJ interface."""


class VTJParameterError(VTJError):
    """VTJ query parameter error."""


class VTJConnectionError(VTJError):
    """Connection problem (network, certificate, timeout, DNS)."""


class VTJAuthenticationError(VTJError):
    """Credentials or data-use permit are invalid or expired."""


class VTJResponseError(VTJError):
    """VTJ returned a return code (Paluukoodi) indicating an error."""

    def __init__(self, return_code: str, message: str = ""):
        self.return_code = return_code
        super().__init__(f"VTJ returned return code {return_code}: {message}".strip())
