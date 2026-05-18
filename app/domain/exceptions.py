class AppError(Exception):
    """Base for all domain errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class PermissionDenied(AppError):
    status_code = 403
    code = "permission_denied"


class ToolFailure(AppError):
    status_code = 502
    code = "tool_failure"


class VaultUnavailableError(AppError):
    status_code = 503
    code = "vault_unavailable"


class ClassifierUnavailableError(AppError):
    status_code = 503
    code = "classifier_unavailable"


class RAGError(AppError):
    status_code = 502
    code = "rag_error"


class EmbeddingError(AppError):
    status_code = 502
    code = "embedding_error"


class AuthError(AppError):
    status_code = 401
    code = "auth_error"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
