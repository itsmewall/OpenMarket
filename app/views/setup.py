# app/views/setup.py
from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.extensions import db
from app.core.models import Store, User
from app.core.forms import StoreForm, UserCreateForm

bp = Blueprint("setup", __name__, template_folder="../templates")

def _needs_setup() -> bool:
    return (Store.query.count() == 0) or (User.query.count() == 0)

@bp.before_app_request
def guard_setup():
    # Se faltar empresa ou usuário, só libera rotas de setup, estáticos e login
    if not _needs_setup():
        return
    allowed = request.endpoint and (
        request.endpoint.startswith("setup.")
        or request.endpoint.startswith("static")
        or request.endpoint == "auth.login"
        or request.endpoint == "auth.login_post"
    )
    if not allowed:
        # Se já tem empresa e faltam usuários, manda para criar admin
        if Store.query.count() > 0 and User.query.count() == 0:
            return redirect(url_for("setup.setup_admin"))
        return redirect(url_for("setup.welcome"))

@bp.get("/setup")
def welcome():
    # Se já tem empresa mas não tem usuário, pula direto para admin
    if Store.query.count() > 0 and User.query.count() == 0:
        return redirect(url_for("setup.setup_admin"))
    if not _needs_setup():
        return redirect(url_for("dashboard.index"))
    return render_template("setup_welcome.html")

@bp.route("/setup/company", methods=["GET", "POST"])
def setup_company():
    # Se já existe empresa, volta para criar admin ou login
    if Store.query.count() > 0:
        flash("Já existe uma empresa cadastrada neste ambiente.", "info")
        if User.query.count() == 0:
            return redirect(url_for("setup.setup_admin"))
        return redirect(url_for("auth.login"))

    form = StoreForm()
    if form.validate_on_submit():
        st = Store(
            nome=form.nome.data,
            cnpj=(form.cnpj.data or None),
            ie=(form.ie.data or None),
            uf=(form.uf.data or None).upper() if form.uf.data else None,
            cidade=(form.cidade.data or None),
            timezone=form.timezone.data or "America/Sao_Paulo",
            ativo=bool(form.ativo.data),
        )
        db.session.add(st)
        db.session.commit()
        flash("Empresa criada", "success")
        return redirect(url_for("setup.setup_admin"))
    return render_template("setup_company.html", form=form)

@bp.route("/setup/admin", methods=["GET", "POST"])
def setup_admin():
    # Se não existe empresa ainda, volte para criar empresa
    if Store.query.count() == 0:
        return redirect(url_for("setup.setup_company"))
    # Se já existe usuário, não precisa deste passo
    if not _needs_setup():
        return redirect(url_for("dashboard.index"))

    store = Store.query.first()
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