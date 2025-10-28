# app/__init__.py
from __future__ import annotations

import os
from flask import Flask, render_template, jsonify
from .extensions import init_extensions, db
from .core.models import ensure_admin

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )

    # Config básica
    app.config.from_object("config.Config")
    # Segurança adicional padrão
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)

    init_extensions(app)

    # Blueprints
    from .auth.routes import bp as auth_bp
    from .views.dashboard import bp as dashboard_bp
    from .views.products import bp as products_bp
    from .views.pos import bp as pos_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(pos_bp, url_prefix="/pos")

    # Healthcheck simples
    @app.get("/health")
    def health():
        return jsonify(ok=True)

    # Erros básicos
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    # Primeira execução: cria admin e loja padrão
    with app.app_context():
        db.create_all()
        try:
            ensure_admin()
        except Exception:
            pass

    return app
