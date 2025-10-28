# app/views/setup.py
from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import current_user
from app.extensions import db
from app.core.models import Store, User
from app.core.forms import StoreForm, UserCreateForm

bp = Blueprint("setup", __name__, template_folder="../templates")

def _needs_setup() -> bool:
    return (Store.query.count() == 0) or (User.query.count() == 0)

@bp.before_app_request
def redirect_if_missing_setup():
    # Se app não está configurado, libera somente /setup/*
    if _needs_setup():
        # Permite acessar as rotas de setup e estáticos e login para redirecionar
        allowed = request.endpoint and (
            request.endpoint.startswith("setup.") or
            request.endpoint.startswith("static") or
            request.endpoint == "auth.login" or
            request.endpoint == "auth.login_post"
        )
        if not allowed:
            return redirect(url_for("setup.welcome"))

@bp.get("/setup")
def welcome():
    if not _needs_setup():
        return redirect(url_for("dashboard.index"))
    return render_template("setup_welcome.html")

@bp.route("/setup/company", methods=["GET","POST"])
def setup_company():
    if not _needs_setup():
        return redirect(url_for("dashboard.index"))
    form = StoreForm()
    if form.validate_on_submit():
        st = Store(
            nome=form.nome.data,
            cnpj=form.cnpj.data or None,
            ie=form.ie.data or None,
            uf=(form.uf.data or "").upper() or None,
            cidade=form.cidade.data or None,
            timezone=form.timezone.data or "America/Sao_Paulo",
            ativo=bool(form.ativo.data),
        )
        db.session.add(st)
        db.session.commit()
        flash("Empresa criada", "success")
        return redirect(url_for("setup.setup_admin"))
    return render_template("setup_company.html", form=form)

@bp.route("/setup/admin", methods=["GET","POST"])
def setup_admin():
    if not _needs_setup():
        return redirect(url_for("dashboard.index"))
    store = Store.query.first()
    if not store:
        return redirect(url_for("setup.setup_company"))
    form = UserCreateForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash("E-mail já cadastrado", "danger")
            return render_template("setup_admin.html", form=form)
        u = User(
            store_id=store.id,
            nome=form.nome.data,
            email=form.email.data.lower(),
            role=form.role.data,
            ativo=bool(form.ativo.data),
        )
        u.set_password(form.senha.data)
        db.session.add(u)
        db.session.commit()
        flash("Administrador criado. Faça login.", "success")
        return redirect(url_for("auth.login"))
    return render_template("setup_admin.html", form=form)
