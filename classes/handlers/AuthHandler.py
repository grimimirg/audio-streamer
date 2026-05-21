from flask import Response, request
from functools import wraps


class AuthHandler:
    """Handles authentication for protected routes."""

    def __init__(self, username: str, password: str):
        """Initialize the authentication handler.
        
        Args:
            username: The expected username for authentication
            password: The expected password for authentication
        """
        self.username = username
        self.password = password

    def check_auth(self, username: str, password: str) -> bool:
        """Check if the provided credentials are valid.

        Args:
            username: Username from HTTP Basic Auth
            password: Password from HTTP Basic Auth

        Returns:
            bool: True if credentials are valid, False otherwise
        """
        return username == self.username and password == self.password

    def authenticate(self) -> Response:
        """Send 401 response with WWW-Authenticate header.

        Returns:
            Response: Flask response with authentication challenge
        """
        return Response(
            'Could not verify your access level for that URL.\n'
            'You have to login with proper credentials', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )

    def requires_auth(self, f):
        """Decorator to require HTTP Basic Authentication for a route.

        Args:
            f: The function to decorate

        Returns:
            The decorated function
        """
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not self.check_auth(auth.username, auth.password):
                return self.authenticate()
            return f(*args, **kwargs)
        return decorated
