# app/extensions.py
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()

def init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

    # Flask-Login config
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # Ativa FKs no SQLite
    with app.app_context():
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            from sqlalchemy import event
            from sqlalchemy.engine import Engine

            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    # Compatibilidade se o modelo User não usa UserMixin
    from app.core.models import User  # evita import circular
    if not hasattr(User, "get_id"):
        User.get_id = lambda self: str(self.id)
    if not hasattr(User, "is_active"):
        User.is_active = property(lambda self: bool(getattr(self, "ativo", True) and not getattr(self, "deleted", False)))
    if not hasattr(User, "is_authenticated"):
        User.is_authenticated = property(lambda self: True)
    if not hasattr(User, "is_anonymous"):
        User.is_anonymous = property(lambda self: False)

    @login_manager.user_loader
    def load_user(user_id: str):
        from app.core.models import User
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None
