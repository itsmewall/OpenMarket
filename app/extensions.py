# app/extensions.py
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, AnonymousUserMixin
from flask_wtf import CSRFProtect
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

    # Rota de login padrão
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # Ativa FKs no SQLite
    with app.app_context():
        if app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite"):
            from sqlalchemy import event
            from sqlalchemy.engine import Engine

            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    # Import tardio para evitar import circular
    from app.core.models import User  # noqa

    # Se o modelo não usa UserMixin, garante a interface esperada
    if not hasattr(User, "get_id"):
        User.get_id = lambda self: str(self.id)
    if not hasattr(User, "is_active"):
        User.is_active = property(lambda self: bool(getattr(self, "ativo", True) and not getattr(self, "deleted", False)))
    if not hasattr(User, "is_authenticated"):
        # Objetos User reais são autenticados quando carregados da sessão
        User.is_authenticated = property(lambda self: True)
    if not hasattr(User, "is_anonymous"):
        User.is_anonymous = property(lambda self: False)

    class _Anon(AnonymousUserMixin):
        pass
    login_manager.anonymous_user = _Anon

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None
