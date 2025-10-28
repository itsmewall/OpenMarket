# app/views/products.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional
import csv
from io import StringIO, BytesIO

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, send_file, abort
)
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.core.models import (
    Product, Category, StockItem, PriceVersion
)
from app.core.forms import ProductForm

bp = Blueprint("products", __name__, url_prefix="/products", template_folder="../templates")


# --------------------------------
# Helpers
# --------------------------------
def _require_store() -> int:
    sid = getattr(current_user, "store_id", None)
    if not sid:
        abort(403)
    return sid

def _role_can_edit() -> bool:
    return getattr(current_user, "role", "") in ("admin", "gerente")

def _set_category_choices(form: ProductForm, store_id: int) -> None:
    cats = Category.query.filter_by(store_id=store_id, ativo=True).order_by(Category.nome).all()
    form.categoria_id.choices = [("", "Selecione...")] + [(str(c.id), c.nome) for c in cats]

def _dec(v: Optional[str], places=2) -> Decimal:
    if v in (None, ""):
        return Decimal("0.00") if places == 2 else Decimal("0.0000")
    try:
        return Decimal(str(v).replace(",", "."))
    except Exception:
        return Decimal("0.00") if places == 2 else Decimal("0.0000")


# --------------------------------
# Lista
# --------------------------------
@bp.get("/")
@login_required
def list_():
    store_id = _require_store()
    q = (request.args.get("q") or "").strip().lower()
    show_inactive = request.args.get("all") == "1"

    query = Product.query.filter_by(store_id=store_id)
    if not show_inactive:
        query = query.filter(Product.ativo.is_(True))

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                db.func.lower(Product.nome).like(like),
                db.func.lower(Product.sku).like(like),
                db.func.lower(Product.ean).like(like),
            )
        )

    items = query.order_by(Product.created_at.desc()).limit(300).all()
    return render_template("products_list.html", items=items, q=q, show_inactive=show_inactive)


# --------------------------------
# Criar
# --------------------------------
@bp.get("/new")
@login_required
def new():
    if not _role_can_edit():
        flash("Acesso negado", "danger")
        return redirect(url_for("products.list_"))

    store_id = _require_store()
    form = ProductForm()
    _set_category_choices(form, store_id)
    form.categoria_id.data = None
    return render_template("product_form.html", form=form, product=None)


@bp.post("/new")
@login_required
def new_post():
    if not _role_can_edit():
        flash("Acesso negado", "danger")
        return redirect(url_for("products.list_"))

    store_id = _require_store()
    form = ProductForm()
    _set_category_choices(form, store_id)

    if not form.validate_on_submit():
        return render_template("product_form.html", form=form, product=None)

    try:
        p = Product(
            store_id=store_id,
            nome=form.nome.data.strip(),
            sku=(form.sku.data or None),
            ean=(form.ean.data or None),
            categoria_id=form.categoria_id.data,  # None se não escolher
            unidade=form.unidade.data if isinstance(form.unidade.data, str) else "UN",
            ncm=(form.ncm.data or None),
            cest=(form.cest.data or None),
            custo_atual=form.custo_atual.data or Decimal("0.00"),
            preco_venda=form.preco_venda.data or Decimal("0.00"),
            margem_alvo=form.margem_alvo.data or Decimal("0.00"),
            estoque_minimo=form.estoque_minimo.data or Decimal("0.0000"),
            ponto_pedido=form.ponto_pedido.data or Decimal("0.0000"),
            foto_url=(form.foto_url.data or None),
            ativo=bool(form.ativo.data),
        )
        db.session.add(p)
        db.session.flush()  # pega p.id

        # Garante estoque
        if not StockItem.query.filter_by(store_id=store_id, product_id=p.id).first():
            db.session.add(StockItem(store_id=store_id, product_id=p.id, quantidade=Decimal("0.0000")))

        # Histórico de preço
        if p.preco_venda and p.preco_venda > 0:
            db.session.add(PriceVersion(store_id=store_id, product_id=p.id, preco=p.preco_venda, origem="manual"))

        db.session.commit()
        flash("Produto cadastrado", "success")
        return redirect(url_for("products.list_"))

    except ValueError as e:
        msg = str(e) or "Dados inválidos."
        if "EAN" in msg or "barras" in msg:
            form.ean.errors.append("Código de barras inválido. Use 8, 12, 13 ou 14 números.")
        else:
            flash(msg, "danger")
        return render_template("product_form.html", form=form, product=None)


# --------------------------------
# Editar
# --------------------------------
@bp.route("/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def edit(pid: int):
    store_id = _require_store()
    p = Product.query.filter_by(id=pid, store_id=store_id).first_or_404()

    if request.method == "GET":
        form = ProductForm(obj=p)
        _set_category_choices(form, store_id)
        form.categoria_id.data = p.categoria_id
        return render_template("product_form.html", form=form, product=p)

    if not _role_can_edit():
        flash("Acesso negado", "danger")
        return redirect(url_for("products.list_"))

    form = ProductForm()
    _set_category_choices(form, store_id)

    if not form.validate_on_submit():
        return render_template("product_form.html", form=form, product=p)

    try:
        preco_antigo = p.preco_venda or Decimal("0.00")

        p.nome = form.nome.data.strip()
        p.sku = form.sku.data or None
        p.ean = form.ean.data or None
        p.categoria_id = form.categoria_id.data
        p.unidade = form.unidade.data if isinstance(form.unidade.data, str) else "UN"
        p.ncm = form.ncm.data or None
        p.cest = form.cest.data or None
        p.custo_atual = form.custo_atual.data or Decimal("0.00")
        p.preco_venda = form.preco_venda.data or Decimal("0.00")
        p.margem_alvo = form.margem_alvo.data or Decimal("0.00")
        p.estoque_minimo = form.estoque_minimo.data or Decimal("0.0000")
        p.ponto_pedido = form.ponto_pedido.data or Decimal("0.0000")
        p.foto_url = form.foto_url.data or None
        p.ativo = bool(form.ativo.data)

        if p.preco_venda != preco_antigo:
            db.session.add(PriceVersion(store_id=store_id, product_id=p.id, preco=p.preco_venda, origem="manual"))

        db.session.commit()
        flash("Produto atualizado", "success")
        return redirect(url_for("products.list_"))

    except ValueError as e:
        msg = str(e) or "Dados inválidos."
        if "EAN" in msg or "barras" in msg:
            form.ean.errors.append("Código de barras inválido. Use 8, 12, 13 ou 14 números.")
        else:
            flash(msg, "danger")
        return render_template("product_form.html", form=form, product=p)


# --------------------------------
# Ativar/Desativar
# --------------------------------
@bp.post("/<int:pid>/toggle")
@login_required
def toggle(pid: int):
    if not _role_can_edit():
        flash("Acesso negado", "danger")
        return redirect(url_for("products.list_"))

    store_id = _require_store()
    p = Product.query.filter_by(id=pid, store_id=store_id).first_or_404()
    p.ativo = not p.ativo
    db.session.commit()
    flash("Status atualizado", "info")
    return redirect(url_for("products.list_"))


# --------------------------------
# Remoção lógica
# --------------------------------
@bp.post("/<int:pid>/delete")
@login_required
def delete(pid: int):
    if not _role_can_edit():
        flash("Acesso negado", "danger")
        return redirect(url_for("products.list_"))

    store_id = _require_store()
    p = Product.query.filter_by(id=pid, store_id=store_id).first_or_404()
    p.deleted = True
    p.ativo = False
    db.session.commit()
    flash("Produto removido", "info")
    return redirect(url_for("products.list_"))


# --------------------------------
# Exportar CSV
# --------------------------------
@bp.get("/export.csv")
@login_required
def export_csv():
    store_id = _require_store()
    qs = Product.query.filter_by(store_id=store_id).order_by(Product.id.asc()).all()

    buf = StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([
        "id","produto","sku","ean","categoria_id","unidade","ncm","cest",
        "preco_compra","preco_venda","lucro_desejado","estoque_minimo","ponto_pedido","ativo"
    ])
    for p in qs:
        w.writerow([
            p.id, p.nome or "", p.sku or "", p.ean or "", p.categoria_id or "",
            p.unidade or "", p.ncm or "", p.cest or "",
            str(p.custo_atual or Decimal("0.00")),
            str(p.preco_venda or Decimal("0.00")),
            str(p.margem_alvo or Decimal("0.00")),
            str(p.estoque_minimo or Decimal("0.0000")),
            str(p.ponto_pedido or Decimal("0.0000")),
            1 if p.ativo else 0
        ])

    data = buf.getvalue().encode("utf-8-sig")
    bio = BytesIO(data)
    bio.seek(0)
    return send_file(
        bio,
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name="produtos.csv"
    )


# --------------------------------
# Importar CSV simples
# --------------------------------
@bp.post("/import")
@login_required
def import_csv():
    if not _role_can_edit():
        flash("Acesso negado", "danger")
        return redirect(url_for("products.list_"))

    store_id = _require_store()
    f = request.files.get("file")
    if not f:
        flash("Envie um arquivo CSV", "warning")
        return redirect(url_for("products.list_"))

    decoded = f.read().decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(StringIO(decoded))
    count_new = 0
    count_upd = 0

    for row in reader:
        nome = (row.get("produto") or row.get("nome") or "").strip()
        if not nome:
            continue

        ean = (row.get("ean") or "").strip() or None
        sku = (row.get("sku") or "").strip() or None

        q = Product.query.filter_by(store_id=store_id)
        if ean:
            q = q.filter(Product.ean == ean)
        elif sku:
            q = q.filter(Product.sku == sku)
        else:
            q = q.filter(Product.nome == nome)
        p = q.first()

        def intval(s: Optional[str]) -> Optional[int]:
            try:
                return int(s) if s not in (None, "",) else None
            except Exception:
                return None

        cat_id = intval(row.get("categoria_id"))
        if cat_id:
            ok = Category.query.filter_by(id=cat_id, store_id=store_id).first()
            if not ok:
                cat_id = None

        payload = dict(
            store_id=store_id,
            nome=nome,
            sku=sku,
            ean=ean,
            categoria_id=cat_id,
            unidade=(row.get("unidade") or "UN"),
            ncm=(row.get("ncm") or None),
            cest=(row.get("cest") or None),
            custo_atual=_dec(row.get("preco_compra") or row.get("custo_atual"), 2),
            preco_venda=_dec(row.get("preco_venda"), 2),
            margem_alvo=_dec(row.get("lucro_desejado") or row.get("margem_alvo"), 2),
            estoque_minimo=_dec(row.get("estoque_minimo"), 4),
            ponto_pedido=_dec(row.get("ponto_pedido"), 4),
            ativo=(str(row.get("ativo") or "1").strip().lower() in ("1", "true", "sim")),
        )

        if p:
            for k, v in payload.items():
                setattr(p, k, v)
            count_upd += 1
        else:
            p = Product(**payload)
            db.session.add(p)
            db.session.flush()
            if not StockItem.query.filter_by(store_id=store_id, product_id=p.id).first():
                db.session.add(StockItem(store_id=store_id, product_id=p.id, quantidade=Decimal("0.0000")))
            count_new += 1

        if payload["preco_venda"] and payload["preco_venda"] > 0:
            db.session.add(PriceVersion(store_id=store_id, product_id=p.id, preco=payload["preco_venda"], origem="import"))

    db.session.commit()
    flash(f"Importação concluída: {count_new} criados, {count_upd} atualizados.", "success")
    return redirect(url_for("products.list_"))
