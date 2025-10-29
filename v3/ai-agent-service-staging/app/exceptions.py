class AppError(Exception):
    """Base class for all application errors"""
    pass


class NotFoundError(AppError):
    """Exception for resource not found"""

    def __init__(self, message="Resource not found"):
        super().__init__(message)


class ValidationError(AppError):
    """Exception for invalid data"""

    def __init__(self, field, message="Invalid input"):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class BadImageAndEmptyDescription(AppError):
    def __init__(self, image_id):
        super().__init__(f"Bad image {image_id} and empty description")
