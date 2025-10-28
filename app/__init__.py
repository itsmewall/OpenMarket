# app/__init__.py
from __future__ import annotations

from flask import Flask, render_template, jsonify
from .extensions import init_extensions, db
from .core.models import ensure_admin
from .views.setup import bp as setup_bp
from .views.users import bp as users_bp

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )
    app.config.from_object("config.Config")

    init_extensions(app)

    from .auth.routes import bp as auth_bp
    from .views.dashboard import bp as dashboard_bp
    from .views.products import bp as products_bp
    from .views.pos import bp as pos_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(pos_bp, url_prefix="/pos")
    app.register_blueprint(setup_bp)    
    app.register_blueprint(users_bp, url_prefix="/users")

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    with app.app_context():
        db.create_all()

    return app