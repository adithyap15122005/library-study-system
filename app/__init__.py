import hmac
from secrets import token_urlsafe

from flask import Flask, g, request, session
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .api import APIError
from .config import load_config
from .extensions import db, migrate
from .models import User


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = token_urlsafe(32)
    return session["csrf_token"]


def create_app(config=None):
    app = Flask(__name__)
    load_config(app, config)
    db.init_app(app)
    migrate.init_app(app, db)

    from .routes.admin import admin
    from .routes.auth import auth
    from .routes.books import books
    from .routes.borrowing import borrowing
    from .routes.learning import learning
    from .routes.pages import pages

    for blueprint in (auth, books, borrowing, learning, admin, pages):
        app.register_blueprint(blueprint)

    @app.before_request
    def protect_api():
        if not request.path.startswith("/api/"):
            return
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            expected = session.get("csrf_token")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not supplied.isascii() or not hmac.compare_digest(expected, supplied):
                raise APIError(403, "The security token expired. Refresh the page and try again.")
        user_id = session.get("user_id")
        g.user = db.session.get(User, user_id) if user_id else None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        db.session.rollback()
        result = {"error": error.message}
        if error.details is not None:
            result["details"] = error.details
        return result, error.status

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        # SQLAlchemy exception strings can include SQL parameters supplied by users.
        app.logger.error("Database operation failed (%s) on %s", type(error).__name__, request.endpoint)
        return {"error": "The database operation failed. Please try again."}, 500

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            messages = {
                404: "The requested resource was not found.", 405: "This method is not supported.",
                413: "The request is too large.", 500: "An unexpected error occurred. Please try again.",
            }
            return {"error": messages.get(error.code, error.name)}, error.code
        return error

    return app
