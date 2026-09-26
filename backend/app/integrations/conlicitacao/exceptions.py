class ConlicitacaoError(RuntimeError):
    """Base error for the provider integration."""


class ConlicitacaoConfigurationError(ConlicitacaoError):
    pass


class ConlicitacaoAPIError(ConlicitacaoError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ConlicitacaoAuthenticationError(ConlicitacaoAPIError):
    pass


class ConlicitacaoRateLimitError(ConlicitacaoAPIError):
    pass


class ConlicitacaoResponseError(ConlicitacaoAPIError):
    pass


class ConlicitacaoUnsupportedOperation(ConlicitacaoError):
    pass
