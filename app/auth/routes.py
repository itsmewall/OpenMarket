# app/auth/routes.py
from __future__ import annotations
from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.core.forms import LoginForm
from app.core.models import User, Store

bp = Blueprint("auth", __name__, template_folder="../templates")


def _is_safe_next(nxt: str | None) -> bool:
    """Evita open redirect: só permite caminhos relativos (sem netloc)."""
    if not nxt:
        return False
    # Ex.: "/dashboard" ok; "http://externo" bloqueia
    return urlparse(nxt).netloc == ""


@bp.get("/auth/login")
def login():
    if getattr(current_user, "is_authenticated", False):
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    store = Store.query.first()
    store_count = Store.query.count()
    user_count = User.query.count()
    return render_template(
        "auth_login.html",
        form=form,
        store=store,
        store_count=store_count,
        user_count=user_count,
    )


@bp.post("/auth/login")
def login_post():
    form = LoginForm()
    store = Store.query.first()
    store_count = Store.query.count()
    user_count = User.query.count()

    if not form.validate_on_submit():
        flash("Credenciais inválidas", "danger")
        return render_template("auth_login.html", form=form, store=store, store_count=store_count, user_count=user_count)

    user = User.query.filter(User.email == form.email.data.lower()).first()
    if not user or not user.check_password(form.password.data) or not user.ativo:
        flash("Usuário ou senha incorretos", "danger")
        return render_template("auth_login.html", form=form, store=store, store_count=store_count, user_count=user_count)

    login_user(user, remember=form.remember.data)
    flash("Bem-vindo", "success")

    nxt = request.args.get("next")
    if not _is_safe_next(nxt):
        nxt = url_for("dashboard.index")
    return redirect(nxt)


@bp.get("/auth/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))