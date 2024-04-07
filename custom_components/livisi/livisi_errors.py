"""Errors for the Livisi Smart Home component."""

# Taken from https://developer.services-smarthome.de/api_reference/errorcodes/
ERROR_CODES = {
    # General Errors
    1000: "An unknown error has occurred.",
    1001: "Service unavailable.",
    1002: "Service timeout.",
    1003: "Internal API error.",
    1004: "SHC invalid operation.",
    1005: "Missing argument or wrong value.",
    1006: "Service too busy.",
    1007: "Unsupported request.",
    1008: "Precondition failed.",
    # Authentication and Authorization Errors
    2000: "An unknown error has occurred during Authentication or Authorization process.",
    2001: "Access not allowed.",
    2002: "Invalid token request.",
    2003: "Invalid client credentials.",
    2004: "The token signature is invalid.",
    2005: "Failed to initialize user session.",
    2006: "A connection already exists for the current session.",
    2007: "The lifetime of the token has expired.",
    2008: "Login attempted from a different client provider.",
    2009: "Invalid user credentials.",
    2010: "Controller access not allowed.",
    2011: "Insufficient permissions.",
    2012: "Session not found.",
    2013: "Account temporary locked.",
    # Entities Errors
    3000: "The requested entity does not exist.",
    3001: "The provided request content is invalid and can't be parsed.",
    3002: "No change performed.",
    3003: "The provided entity already exists.",
    3004: "The provided interaction is not valid.",
    3005: "Too many entities of this type.",
    # Products Errors
    3500: "Premium Services can't be directly enabled.",
    3501: "Cannot remove a product that was paid.",
    # Actions Errors
    4000: "The triggered action is invalid.",
    4001: "Invalid parameter.",
    4002: "Permission to trigger action not allowed.",
    4003: "Unsupported action type.",
    # Configuration Errors
    5000: "The configuration could not be updated.",
    5001: "Could not obtain exclusive access on the configuration.",
    5002: "Communication with the SHC failed.",
    5003: "The owner did not accept the TaC latest version.",
    5004: "One SHC already registered.",
    5005: "The user has no SHC.",
    5006: "Controller offline.",
    5009: "Registration failure.",
    # SmartCodes Errors
    6000: "SmartCode request not allowed.",
    6001: "The SmartCode cannot be redeemed.",
    6002: "Restricted access.",
}


class LivisiException(Exception):
    """Base class for Livisi exceptions."""

    def __init__(self, message: str = "", *args: object) -> None:
        """Initialize the exception with a message."""
        self.message = message
        super().__init__(message, *args)


class ShcUnreachableException(LivisiException):
    """Unable to connect to the Smart Home Controller."""

    def __init__(
        self,
        message: str = "Unable to connect to the Smart Home Controller.",
        *args: object,
    ) -> None:
        """Generate error with default message."""
        super().__init__(message, *args)


class WrongCredentialException(LivisiException):
    """The user credentials were wrong."""

    def __init__(
        self, message: str = "The user credentials are wrong.", *args: object
    ) -> None:
        """Generate error with default message."""
        super().__init__(message, *args)


class IncorrectIpAddressException(LivisiException):
    """The IP address provided by the user is incorrect."""

    def __init__(
        self,
        message: str = "The IP address provided by the user is incorrect.",
        *args: object,
    ) -> None:
        """Generate error with default message."""
        super().__init__(message, *args)


class TokenExpiredException(LivisiException):
    """The authentication token is expired."""

    def __init__(
        self, message: str = "The authentication token is expired.", *args: object
    ) -> None:
        """Generate error with default message."""
        super().__init__(message, *args)


class ErrorCodeException(LivisiException):
    """The request sent an errorcode (other than token expired) as response."""

    def __init__(self, error_code: int, message: str = None, *args: object) -> None:
        """Generate error with code."""
        self.error_code = error_code
        if (message is None) and (error_code in ERROR_CODES):
            message = ERROR_CODES[error_code]
        elif message is None:
            message = f"Unknown error code from shc: {error_code}"
        super().__init__(message, *args)
