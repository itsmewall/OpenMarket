# app/views/pos.py
from __future__ import annotations

from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.core.models import Product, Sale, SaleItem
from app.core.forms import SaleOpenForm, SaleAddItemForm, SalePaymentForm, SaleCancelForm, SearchForm
from app.core.services import transaction, abrir_venda, adicionar_item_venda, pagar_venda, cancelar_venda

bp = Blueprint("pos", __name__, template_folder="../templates")

@bp.get("/")
@login_required
def pos_home():
    sale_id = request.args.get("sale_id", type=int)
    sale = Sale.query.filter_by(id=sale_id, store_id=current_user.store_id).first() if sale_id else None
    form_open = SaleOpenForm()
    form_add = SaleAddItemForm()
    form_pay = SalePaymentForm()
    form_cancel = SaleCancelForm()
    form_search = SearchForm()
    # Preencher selects
    form_add.product_id.choices = _product_choices()
    form_pay.customer_id.choices = [("", "Sem cliente")]
    return render_template("pos.html", sale=sale, form_open=form_open, form_add=form_add, form_pay=form_pay, form_cancel=form_cancel, form_search=form_search)

@bp.post("/sale/open")
@login_required
def sale_open():
    with transaction():
        sale = abrir_venda(current_user.store_id, None, current_user)
    return redirect(url_for("pos.pos_home", sale_id=sale.id))

@bp.post("/sale/<int:sale_id>/add")
@login_required
def sale_add(sale_id: int):
    form = SaleAddItemForm()
    form.product_id.choices = _product_choices()
    if not form.validate_on_submit():
        flash("Informe produto e quantidade válida", "danger")
        return redirect(url_for("pos.pos_home", sale_id=sale_id))
    with transaction():
        adicionar_item_venda(sale_id, form.product_id.data, form.qtd.data or Decimal("1"), current_user)
    return redirect(url_for("pos.pos_home", sale_id=sale_id))

@bp.post("/sale/<int:sale_id>/pay")
@login_required
def sale_pay(sale_id: int):
    form = SalePaymentForm()
    if not form.validate_on_submit():
        flash("Pagamento inválido", "danger")
        return redirect(url_for("pos.pos_home", sale_id=sale_id))
    with transaction():
        pagar_venda(sale_id, form.pagamento.data, form.valor_pago.data, form.customer_id.data or None, current_user)
    flash("Venda concluída", "success")
    return redirect(url_for("pos.pos_home"))

@bp.post("/sale/<int:sale_id>/cancel")
@login_required
def sale_cancel(sale_id: int):
    form = SaleCancelForm()
    if not form.validate_on_submit():
        flash("Informe o motivo", "warning")
    with transaction():
        cancelar_venda(sale_id, form.motivo.data or "Cancelamento", current_user)
    flash("Venda cancelada", "info")
    return redirect(url_for("pos.pos_home"))

def _product_choices():
    prods = Product.query.filter_by(store_id=current_user.store_id, deleted=False, ativo=True).order_by(Product.nome).limit(500).all()
    return [(p.id, f"{p.nome} [{p.ean or 'sem EAN'}]") for p in prods]
