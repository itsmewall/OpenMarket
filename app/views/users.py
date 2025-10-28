# app/views/users.py
from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.core.models import User
from app.core.forms import UserCreateForm, UserEditForm

bp = Blueprint("users", __name__, template_folder="../templates")

def _ensure_admin():
    return getattr(current_user, "role", "") == "admin"

@bp.get("/")
@login_required
def list_():
    if not _ensure_admin():
        flash("Acesso negado", "danger")
        return redirect(url_for("dashboard.index"))
    q = request.args.get("q","").strip().lower()
    query = User.query.filter_by(store_id=current_user.store_id).order_by(User.created_at.desc())
    if q:
        like = f"%{q}%"
        query = query.filter(db.func.lower(User.nome).like(like) | db.func.lower(User.email).like(like))
    items = query.limit(200).all()
    return render_template("users_list.html", items=items, q=q)

@bp.route("/new", methods=["GET","POST"])
@login_required
def new():
    if not _ensure_admin():
        flash("Acesso negado", "danger")
        return redirect(url_for("dashboard.index"))
    form = UserCreateForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash("E-mail já cadastrado", "danger")
            return render_template("user_form.html", form=form)
        u = User(
            store_id=current_user.store_id,
            nome=form.nome.data,
            email=form.email.data.lower(),
            role=form.role.data,
            ativo=bool(form.ativo.data),
        )
        u.set_password(form.senha.data)
        db.session.add(u)
        db.session.commit()
        flash("Usuário criado", "success")
        return redirect(url_for("users.list_"))
    return render_template("user_form.html", form=form)

@bp.route("/<int:uid>/edit", methods=["GET","POST"])
@login_required
def edit(uid: int):
    if not _ensure_admin():
        flash("Acesso negado", "danger")
        return redirect(url_for("dashboard.index"))
    u = User.query.filter_by(id=uid, store_id=current_user.store_id).first_or_404()
    form = UserEditForm(obj=u)
    if form.validate_on_submit():
        # Evita trocar para email já existente
        exists = User.query.filter(User.email == form.email.data.lower(), User.id != u.id).first()
        if exists:
            flash("E-mail já cadastrado", "danger")
            return render_template("user_form.html", form=form, user=u)
        u.nome = form.nome.data
        u.email = form.email.data.lower()
        u.role = form.role.data
        u.ativo = bool(form.ativo.data)
        if form.nova_senha.data:
            u.set_password(form.nova_senha.data)
        db.session.commit()
        flash("Usuário atualizado", "success")
        return redirect(url_for("users.list_"))
    return render_template("user_form.html", form=form, user=u)

@bp.post("/<int:uid>/toggle")
@login_required
def toggle(uid: int):
    if not _ensure_admin():
        flash("Acesso negado", "danger")
        return redirect(url_for("dashboard.index"))
    u = User.query.filter_by(id=uid, store_id=current_user.store_id).first_or_404()
    u.ativo = not u.ativo
    db.session.commit()
    flash("Status atualizado", "info")
    return redirect(url_for("users.list_"))
