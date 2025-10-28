# app/auth/routes.py
from __future__ import annotations

from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import safe_str_cmp

from app.core.forms import LoginForm
from app.core.models import User

bp = Blueprint("auth", __name__, template_folder="../templates")

@bp.get("/login")
def login():
    if getattr(current_user, "is_authenticated", False):
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    return render_template("auth_login.html", form=form)

@bp.post("/login")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        flash("Credenciais inválidas", "danger")
        return render_template("auth_login.html", form=form)

    user = User.query.filter(User.email == form.email.data.lower()).first()
    if not user or not user.check_password(form.password.data) or not user.ativo:
        flash("Usuário ou senha incorretos", "danger")
        return render_template("auth_login.html", form=form)

    login_user(user, remember=form.remember.data)
    flash("Bem-vindo", "success")
    next_url = request.args.get("next") or url_for("dashboard.index")
    return redirect(next_url)

@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada", "info")
    return redirect(url_for("auth.login"))
