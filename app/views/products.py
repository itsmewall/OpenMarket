# app/views/products.py
from __future__ import annotations

from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.core.models import Product, Category
from app.core.forms import ProductForm
from app.core.services import (
    transaction, criar_produto, atualizar_produto, publicar_preco, simular_preco
)

bp = Blueprint("products", __name__, template_folder="../templates")

@bp.get("/")
@login_required
def list_():
    q = request.args.get("q", "").strip()
    query = Product.query.filter_by(store_id=current_user.store_id, deleted=False)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(db.func.lower(Product.nome).like(like))
    items = query.order_by(Product.created_at.desc()).limit(200).all()
    return render_template("products_list.html", items=items, q=q)

@bp.get("/new")
@login_required
def new():
    form = ProductForm()
    _fill_choices(form)
    return render_template("product_form.html", form=form)

@bp.post("/")
@login_required
def create():
    form = ProductForm()
    _fill_choices(form)
    if not form.validate_on_submit():
        flash("Corrija os erros do formulário", "danger")
        return render_template("product_form.html", form=form)

    with transaction():
        p = criar_produto(
            store_id=current_user.store_id,
            nome=form.nome.data,
            sku=form.sku.data,
            ean=form.ean.data,
            categoria_id=form.categoria_id.data or None,
            unidade=form.unidade.data,
            ncm=form.ncm.data,
            cest=form.cest.data,
            custo_atual=form.custo_atual.data or Decimal("0"),
            preco_venda=form.preco_venda.data or Decimal("0"),
            estoque_minimo=form.estoque_minimo.data or Decimal("0"),
            ponto_pedido=form.ponto_pedido.data or Decimal("0"),
            created_by=current_user,
        )
        if form.preco_venda.data and form.preco_venda.data > 0:
            publicar_preco(current_user.store_id, p.id, form.preco_venda.data, "manual", current_user)

    flash("Produto criado", "success")
    return redirect(url_for("products.list_"))

@bp.get("/<int:pid>/edit")
@login_required
def edit(pid: int):
    p = Product.query.filter_by(id=pid, store_id=current_user.store_id, deleted=False).first_or_404()
    form = ProductForm(obj=p)
    _fill_choices(form, selected=p.categoria_id)
    return render_template("product_form.html", form=form, produto=p)

@bp.post("/<int:pid>/update")
@login_required
def update(pid: int):
    p = Product.query.filter_by(id=pid, store_id=current_user.store_id, deleted=False).first_or_404()
    form = ProductForm()
    _fill_choices(form)
    if not form.validate_on_submit():
        flash("Corrija os erros do formulário", "danger")
        return render_template("product_form.html", form=form, produto=p)

    dados = {
        "nome": form.nome.data,
        "sku": form.sku.data,
        "ean": form.ean.data,
        "categoria_id": form.categoria_id.data or None,
        "unidade": form.unidade.data,
        "ncm": form.ncm.data,
        "cest": form.cest.data,
        "estoque_minimo": form.estoque_minimo.data or Decimal("0"),
        "ponto_pedido": form.ponto_pedido.data or Decimal("0"),
        "margem_alvo": form.margem_alvo.data or Decimal("0"),
        "foto_url": form.foto_url.data,
        "ativo": bool(form.ativo.data),
    }
    with transaction():
        atualizar_produto(p.id, dados, current_user)
        # Atualiza preço atual se informado
        if form.preco_venda.data is not None:
            publicar_preco(current_user.store_id, p.id, form.preco_venda.data, "manual", current_user)

    flash("Produto atualizado", "success")
    return redirect(url_for("products.list_"))

def _fill_choices(form: ProductForm, selected=None):
    cats = Category.query.filter_by(store_id=current_user.store_id, deleted=False, ativo=True).order_by(Category.nome).all()
    form.categoria_id.choices = [("", "Sem categoria")] + [(c.id, c.nome) for c in cats]
    if selected:
        form.categoria_id.data = selected
