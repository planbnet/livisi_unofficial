"""Errors for the Livisi Smart Home component."""


class LivisiException(Exception):
    """Base class for Livisi exceptions."""


class ShcUnreachableException(LivisiException):
    """Unable to connect to the Smart Home Controller."""


class WrongCredentialException(LivisiException):
    """The user credentials were wrong."""


class IncorrectIpAddressException(LivisiException):
    """The IP address provided by the user is incorrect."""


class TokenExpiredException(LivisiException):
    """The authentication token is expired."""


class ErrorCodeException(LivisiException):
    """The request sent an errorcode (other than token expired) as response."""

    def __init__(self, error_code: int, *args: object) -> None:
        """Generate error with code."""
        self.error_code = error_code
        super().__init__(*args)
