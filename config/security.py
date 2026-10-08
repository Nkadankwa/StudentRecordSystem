import logging


class SafeRequestLogFilter(logging.Filter):
    """Log status and severity, not URL identifiers, bodies, secrets, or traces."""
    def filter(self, record):
        status = getattr(record, 'status_code', 'unknown')
        record.msg = 'HTTP request event (status %s)'
        record.args = (status,)
        record.exc_info = record.exc_text = record.stack_info = None
        if hasattr(record, 'request'):
            del record.request
        return True


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, 'user', None) and request.user.is_authenticated:
            response['Cache-Control'] = 'private, no-store, max-age=0'
        return response
