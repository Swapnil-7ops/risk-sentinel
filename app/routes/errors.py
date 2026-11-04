from flask import Blueprint, jsonify, request, render_template

errors_bp = Blueprint("errors", __name__)


def _error_page(code, template, _error):
    if request.path.startswith("/api/"):
        messages = {400: "Bad request.", 401: "Unauthorized.", 403: "Forbidden.", 404: "Not found.", 405: "Method not allowed.", 413: "Request too large.", 429: "Too many requests.", 500: "Internal server error."}
        return jsonify({"error": messages.get(code, "Request failed.")}), code
    return render_template(template), code


@errors_bp.app_errorhandler(400)
def bad_request(error): return _error_page(400, "errors/400.html", error)


@errors_bp.app_errorhandler(401)
def unauthorized(error): return _error_page(401, "errors/401.html", error)


@errors_bp.app_errorhandler(403)
def forbidden(error): return _error_page(403, "errors/403.html", error)


@errors_bp.app_errorhandler(404)
def not_found(error): return _error_page(404, "errors/404.html", error)


@errors_bp.app_errorhandler(405)
def method_not_allowed(error): return _error_page(405, "errors/405.html", error)


@errors_bp.app_errorhandler(413)
def too_large(error): return _error_page(413, "errors/413.html", error)


@errors_bp.app_errorhandler(429)
def rate_limited(error): return _error_page(429, "errors/429.html", error)


@errors_bp.app_errorhandler(500)
def server_error(error): return _error_page(500, "errors/500.html", error)
