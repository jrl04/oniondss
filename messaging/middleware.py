class RefreshWebSession:
    """Extend authenticated web sessions only for interactive requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        background = request.method in {"GET", "HEAD"} and request.headers.get("X-DSS-Background") == "1"
        if not background and request.user.is_authenticated:
            request.session.modified = True
        return self.get_response(request)
