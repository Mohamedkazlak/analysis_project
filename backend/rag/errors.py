class QueryRejected(Exception):
    """A generated query failed validation. detail is safe to show to the client."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class LlmNotConfigured(Exception):
    pass


class LlmUpstreamError(Exception):
    pass
