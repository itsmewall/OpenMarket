# app/core/services.py
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, List, Optional, Tuple, Dict, Any

from flask import current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.core.models import (
    _as_money, _as_qtd, normalize_ean,
    Store, User, Category, Product, Supplier, Customer,
    StockItem, StockMove, StockMoveEnum,
    Purchase, PurchaseItem, PurchaseStatusEnum,
    PriceVersion, Promo,
    CashRegister, Sale, SaleItem, SaleStatusEnum, PaymentEnum,
    Payable, Receivable, PayRecStatusEnum,
    InventorySession, InventoryCount,
    AuditLog
)

# =============================================================================
# Exceções e utilidades
# =============================================================================

class ServiceError(Exception):
    pass

def _ensure(cond: bool, msg: str):
    if not cond:
        raise ServiceError(msg)

def _row_to_dict(obj, keys: Iterable[str]) -> Dict[str, Any]:
    return {k: getattr(obj, k, None) for k in keys}

@contextmanager
def transaction():
    try:
        yield
        db.session.commit()
    except IntegrityError as ie:
        db.session.rollback()
        raise ServiceError(f"Violação de integridade: {ie.orig}") from ie
    except ServiceError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise ServiceError(str(e)) from e

def audit_log(store_id: int, entidade: str, entidade_id: Optional[int], acao: str, payload: dict, user: Optional[User]):
    log = AuditLog(
        store_id=store_id,
        entidade=entidade,
        entidade_id=entidade_id,
        acao=acao,
        payload_json=payload or {},
        user_id=user.id if user else None,
        ip=None
    )
    db.session.add(log)

def require_role(user: User, allowed: Iterable[str]):
    if not user or user.deleted or not user.ativo:
        raise ServiceError("Usuário inválido ou inativo")
    if user.role not in allowed and "*" not in allowed:
        raise ServiceError("Permissão negada")

# =============================================================================
# Produtos e Preços
# =============================================================================

def criar_categoria(store_id: int, nome: str, markup_padrao: Decimal = Decimal("0")) -> Category:
    nome = nome.strip()
    _ensure(len(nome) > 0, "Nome da categoria obrigatório")
    cat = Category(store_id=store_id, nome=nome, markup_padrao=markup_padrao)
    db.session.add(cat)
    return cat

def criar_produto(
    store_id: int,
    nome: str,
    sku: Optional[str] = None,
    ean: Optional[str] = None,
    categoria_id: Optional[int] = None,
    unidade: str = "UN",
    ncm: Optional[str] = None,
    cest: Optional[str] = None,
    custo_atual: Decimal = Decimal("0"),
    preco_venda: Decimal = Decimal("0"),
    estoque_minimo: Decimal = Decimal("0"),
    ponto_pedido: Decimal = Decimal("0"),
    created_by: Optional[User] = None
) -> Product:
    _ensure(nome and nome.strip(), "Nome do produto obrigatório")
    ean = normalize_ean(ean)
    p = Product(
        store_id=store_id,
        nome=nome.strip(),
        sku=(sku or "").strip() or None,
        ean=ean,
        categoria_id=categoria_id,
        unidade=unidade,
        ncm=(ncm or "").strip() or None,
        cest=(cest or "").strip() or None,
        custo_atual=_as_money(custo_atual),
        preco_venda=_as_money(preco_venda),
        estoque_minimo=_as_qtd(estoque_minimo),
        ponto_pedido=_as_qtd(ponto_pedido),
        created_by_id=created_by.id if created_by else None
    )
    db.session.add(p)
    db.session.flush()

    # Cria o registro de estoque se não existir
    si = StockItem(store_id=store_id, product_id=p.id, quantidade=_as_qtd(0), reservado=_as_qtd(0))
    db.session.add(si)

    audit_log(store_id, "Product", p.id, "created", _row_to_dict(p, ["nome", "sku", "ean", "preco_venda"]), created_by)
    return p

def atualizar_produto(
    product_id: int,
    dados: Dict[str, Any],
    updated_by: Optional[User] = None
) -> Product:
    p = db.session.get(Product, product_id)
    _ensure(p and not p.deleted, "Produto não encontrado")
    campos_editaveis = {
        "nome", "sku", "ean", "categoria_id", "unidade", "ncm", "cest",
        "estoque_minimo", "ponto_pedido", "margem_alvo", "foto_url", "ativo"
    }
    before = _row_to_dict(p, list(campos_editaveis))
    for k, v in dados.items():
        if k not in campos_editaveis:
            continue
        if k in {"estoque_minimo", "ponto_pedido", "margem_alvo"}:
            setattr(p, k, _as_qtd(v) if k != "margem_alvo" else Decimal(str(v)))
        elif k == "ean":
            setattr(p, k, normalize_ean(v))
        else:
            setattr(p, k, v)
    p.updated_by_id = updated_by.id if updated_by else None
    audit_log(p.store_id, "Product", p.id, "updated", {"before": before, "after": _row_to_dict(p, list(campos_editaveis))}, updated_by)
    return p

def simular_preco(custo: Decimal, markup_percent: Decimal) -> Decimal:
    custo = _as_money(custo)
    mk = Decimal(str(markup_percent or 0)) / Decimal("100")
    preco = custo * (Decimal("1.0") + mk)
    return _as_money(preco)

def publicar_preco(store_id: int, product_id: int, preco: Decimal, origem: str = "manual", user: Optional[User] = None) -> PriceVersion:
    preco = _as_money(preco)
    _ensure(preco >= 0, "Preço inválido")
    p = db.session.get(Product, product_id)
    _ensure(p and p.store_id == store_id and not p.deleted, "Produto inválido")
    pv = PriceVersion(
        store_id=store_id, product_id=product_id, preco=preco,
        origem=origem, valido_de=datetime.utcnow(),
        created_by_id=user.id if user else None
    )
    db.session.add(pv)
    # Atualiza preço atual para facilitar PDV
    before = p.preco_venda
    p.preco_venda = preco
    p.updated_by_id = user.id if user else None
    audit_log(store_id, "Product", product_id, "price_change", {"before": str(before), "after": str(preco), "origem": origem}, user)
    return pv

# =============================================================================
# Estoque e Ajustes
# =============================================================================

def ajuste_estoque(store_id: int, product_id: int, qtd: Decimal, motivo: str, tipo: str, user: Optional[User]) -> StockMove:
    _ensure(tipo in ("entrada_ajuste", "saida_ajuste"), "Tipo de ajuste inválido")
    qtd = _as_qtd(qtd)
    _ensure(qtd > 0, "Quantidade deve ser positiva")
    p = db.session.get(Product, product_id)
    _ensure(p and p.store_id == store_id and not p.deleted, "Produto inválido")
    sm = StockMove(
        store_id=store_id,
        product_id=product_id,
        tipo=tipo,
        qtd=qtd,
        custo=p.custo_atual if tipo == "entrada_ajuste" else Decimal("0.00"),
        motivo=(motivo or "").strip()[:200],
        created_by_id=user.id if user else None
    )
    db.session.add(sm)
    audit_log(store_id, "StockMove", None, "adjust", {"product_id": product_id, "qtd": str(qtd), "tipo": tipo, "motivo": motivo}, user)
    return sm

# =============================================================================
# Compras
# =============================================================================

@dataclass
class ItemCompraDTO:
    product_id: int
    qtd: Decimal
    custo: Decimal
    desconto: Decimal = Decimal("0")

def criar_pedido_compra(store_id: int, supplier_id: int, itens: List[ItemCompraDTO], user: Optional[User]) -> Purchase:
    _ensure(len(itens) > 0, "Lista de itens vazia")
    supplier = db.session.get(Supplier, supplier_id)
    _ensure(supplier and supplier.store_id == store_id and supplier.ativo, "Fornecedor inválido")
    compra = Purchase(
        store_id=store_id, supplier_id=supplier_id, status="rascunho",
        total_previsto=Decimal("0.00"), total_recebido=Decimal("0.00"),
        created_by_id=user.id if user else None
    )
    db.session.add(compra)
    total = Decimal("0.00")
    for dto in itens:
        qtd = _as_qtd(dto.qtd)
        custo = _as_money(dto.custo)
        desc = _as_money(dto.desconto)
        _ensure(qtd > 0, "Quantidade deve ser positiva")
        _ensure(custo >= 0, "Custo negativo")
        prod = db.session.get(Product, dto.product_id)
        _ensure(prod and prod.store_id == store_id and not prod.deleted, "Produto inválido na compra")
        total_item = _as_money(qtd * custo - desc)
        pci = PurchaseItem(purchase_id=compra.id, product_id=prod.id, qtd=qtd, custo=custo, desconto=desc, total=total_item)
        db.session.add(pci)
        total += total_item
    compra.total_previsto = _as_money(total)
    audit_log(store_id, "Purchase", None, "created", {"supplier_id": supplier_id, "itens": len(itens), "total_previsto": str(total)}, user)
    return compra

def enviar_compra(compra_id: int, user: Optional[User]) -> Purchase:
    compra = db.session.get(Purchase, compra_id)
    _ensure(compra and compra.status == "rascunho", "Compra não está em rascunho")
    compra.status = "emitida"
    compra.updated_by_id = user.id if user else None
    audit_log(compra.store_id, "Purchase", compra.id, "submitted", {}, user)
    return compra

@dataclass
class ItemRecebimentoDTO:
    product_id: int
    qtd: Decimal
    custo: Optional[Decimal] = None  # se não vier, usa custo do item do pedido

def receber_compra(compra_id: int, itens: List[ItemRecebimentoDTO], user: Optional[User]) -> Purchase:
    compra = db.session.get(Purchase, compra_id)
    _ensure(compra and compra.status in ("emitida", "parcialmente_recebida"), "Compra não pode ser recebida")
    itens_map = {i.product_id: i for i in db.session.query(PurchaseItem).filter_by(purchase_id=compra.id).all()}
    _ensure(len(itens_map) > 0, "Compra sem itens")

    total_receb = compra.total_recebido or Decimal("0.00")
    for rec in itens:
        _ensure(rec.product_id in itens_map, "Produto não pertence ao pedido")
        qtd = _as_qtd(rec.qtd)
        _ensure(qtd > 0, "Quantidade deve ser positiva")
        custo_base = itens_map[rec.product_id].custo
        custo_rec = _as_money(rec.custo if rec.custo is not None else custo_base)

        # Gera movimento de estoque
        sm = StockMove(
            store_id=compra.store_id,
            product_id=rec.product_id,
            tipo="entrada_compra",
            qtd=qtd,
            custo=custo_rec,
            ref_origem="purchase",
            ref_id=compra.id,
            created_by_id=user.id if user else None
        )
        db.session.add(sm)
        total_receb += _as_money(qtd * custo_rec)

    compra.total_recebido = _as_money(total_receb)
    # Atualiza status
    qtd_pedido = sum((_as_qtd(i.qtd) for i in itens_map.values()), _as_qtd(0))
    qtd_recebida = _as_qtd(0)
    # Aproxima por somatório de entradas da compra
    entradas = db.session.query(StockMove).filter_by(store_id=compra.store_id, ref_origem="purchase", ref_id=compra.id, tipo="entrada_compra").all()
    for e in entradas:
        qtd_recebida += _as_qtd(e.qtd)
    if qtd_recebida == 0:
        compra.status = "emitida"
    elif qtd_recebida < qtd_pedido:
        compra.status = "parcialmente_recebida"
    else:
        compra.status = "recebida"

    compra.updated_by_id = user.id if user else None

    # Payable simples pela compra quando finalizada
    if compra.status == "recebida":
        valor = compra.total_previsto if compra.total_previsto and compra.total_previsto > 0 else compra.total_recebido
        valor = _as_money(valor)
        if valor > 0:
            pv = Payable(
                store_id=compra.store_id,
                origem="purchase",
                ref_id=compra.id,
                fornecedor_id=compra.supplier_id,
                valor=valor,
                vencimento=datetime.utcnow(),
                status="aberto"
            )
            db.session.add(pv)

    audit_log(compra.store_id, "Purchase", compra.id, "received", {"status": compra.status, "total_recebido": str(compra.total_recebido)}, user)
    return compra

# =============================================================================
# PDV e Vendas
# =============================================================================

def abrir_venda(store_id: int, caixa_id: Optional[int], user: User) -> Sale:
    require_role(user, ["admin", "gerente", "operador"])
    sale = Sale(
        store_id=store_id,
        caixa_id=caixa_id,
        status="aberta",
        subtotal=_as_money(0),
        desconto=_as_money(0),
        total=_as_money(0),
        created_by_id=user.id
    )
    db.session.add(sale)
    audit_log(store_id, "Sale", None, "created", {}, user)
    return sale

def _preco_com_promos(store_id: int, product: Product, qtd: Decimal) -> Tuple[Decimal, Optional[int], Decimal]:
    """
    Estratégia simples de promo.
    Retorna: preco_unit_final, promo_id, desconto_total
    """
    preco_unit = _as_money(product.preco_venda)
    desconto_total = _as_money(0)
    promo_id = None
    if not product.ativo:
        return preco_unit, None, _as_money(0)

    # Exemplo: aplica promo percentual se existir válida
    agora = datetime.utcnow()
    promo = db.session.query(Promo).filter(
        Promo.store_id == store_id,
        Promo.ativa.is_(True),
        Promo.validade_ini <= agora,
        (Promo.validade_fim.is_(None)) | (Promo.validade_fim >= agora)
    ).order_by(Promo.prioridade.asc()).first()
    if promo and isinstance(promo.regra_json, dict):
        r = promo.regra_json
        if r.get("type") == "desconto_percentual":
            perc = Decimal(str(r.get("value", 0)))
            desconto = (preco_unit * qtd) * (perc / Decimal("100"))
            desconto_total = _as_money(desconto)
            promo_id = promo.id

    return preco_unit, promo_id, desconto_total

def adicionar_item_venda(sale_id: int, product_id: int, qtd: Decimal, user: User) -> SaleItem:
    sale = db.session.get(Sale, sale_id)
    _ensure(sale and sale.status == "aberta", "Venda inválida ou não está aberta")
    p = db.session.get(Product, product_id)
    _ensure(p and p.store_id == sale.store_id and not p.deleted, "Produto inválido")
    qtd = _as_qtd(qtd)
    _ensure(qtd > 0, "Quantidade deve ser positiva")

    preco_unit, promo_id, desconto_total = _preco_com_promos(sale.store_id, p, qtd)

    total_sem_desc = _as_money(preco_unit * qtd)
    total = _as_money(total_sem_desc - desconto_total)

    si = SaleItem(
        sale_id=sale.id,
        product_id=p.id,
        qtd=qtd,
        preco_unit=preco_unit,
        desconto=desconto_total,
        promo_id=promo_id,
        total=total
    )
    db.session.add(si)

    # Atualiza totais da venda
    sale.subtotal = _as_money((sale.subtotal or 0) + total_sem_desc)
    sale.desconto = _as_money((sale.desconto or 0) + desconto_total)
    sale.total = _as_money((sale.total or 0) + total)

    audit_log(sale.store_id, "Sale", sale.id, "item_added", {"product_id": p.id, "qtd": str(qtd), "total_item": str(total)}, user)
    return si

def remover_item_venda(sale_item_id: int, user: User) -> Sale:
    si = db.session.get(SaleItem, sale_item_id)
    _ensure(si, "Item não encontrado")
    sale = db.session.get(Sale, si.sale_id)
    _ensure(sale and sale.status == "aberta", "Venda não está aberta")

    sale.subtotal = _as_money(sale.subtotal - (si.preco_unit * si.qtd))
    sale.desconto = _as_money(sale.desconto - si.desconto)
    sale.total = _as_money(sale.total - si.total)

    db.session.delete(si)
    audit_log(sale.store_id, "Sale", sale.id, "item_removed", {"sale_item_id": sale_item_id}, user)
    return sale

def pagar_venda(sale_id: int, pagamento: str, valor_pago: Decimal, customer_id: Optional[int], user: User) -> Sale:
    sale = db.session.get(Sale, sale_id)
    _ensure(sale and sale.status == "aberta", "Venda inválida ou já finalizada")
    _ensure(len(sale.items) > 0, "Venda vazia")
    _ensure(pagamento in ("dinheiro", "cartao", "pix", "misto"), "Pagamento inválido")

    sale.pagamento = pagamento
    sale.troco = _as_money(max(_as_money(valor_pago) - sale.total, Decimal("0")))
    sale.status = "concluida"
    if customer_id:
        cust = db.session.get(Customer, customer_id)
        _ensure(not cust or cust.store_id == sale.store_id, "Cliente inválido")
        sale.customer_id = customer_id

    # Gera movimentos de estoque de saída por item
    for it in sale.items:
        sm = StockMove(
            store_id=sale.store_id,
            product_id=it.product_id,
            tipo="saida_venda",
            qtd=_as_qtd(it.qtd),
            custo=Decimal("0.00"),
            ref_origem="sale",
            ref_id=sale.id,
            created_by_id=user.id if user else None
        )
        db.session.add(sm)

    audit_log(sale.store_id, "Sale", sale.id, "paid", {"pagamento": pagamento, "valor_pago": str(valor_pago)}, user)
    return sale

def cancelar_venda(sale_id: int, motivo: str, user: User) -> Sale:
    sale = db.session.get(Sale, sale_id)
    _ensure(sale and sale.status in ("aberta", "concluida"), "Venda não pode ser cancelada")
    sale.status = "cancelada"

    # Reverte estoque apenas se já estava concluída
    if len(sale.items) > 0:
        if sale.total > 0 and sale.status == "cancelada":
            for it in sale.items:
                sm = StockMove(
                    store_id=sale.store_id,
                    product_id=it.product_id,
                    tipo="devolucao",
                    qtd=_as_qtd(it.qtd),
                    custo=Decimal("0.00"),
                    ref_origem="sale",
                    ref_id=sale.id,
                    motivo=(motivo or "Cancelamento de venda")[:200],
                    created_by_id=user.id if user else None
                )
                db.session.add(sm)

    audit_log(sale.store_id, "Sale", sale.id, "canceled", {"motivo": motivo}, user)
    return sale

# =============================================================================
# Inventário
# =============================================================================

def criar_sessao_inventario(store_id: int, nome: str, setor: Optional[str], user: Optional[User]) -> InventorySession:
    _ensure(nome and nome.strip(), "Nome obrigatório")
    sess = InventorySession(store_id=store_id, nome=nome.strip(), setor=(setor or "").strip() or None, aberta=True, created_by_id=user.id if user else None)
    db.session.add(sess)
    audit_log(store_id, "InventorySession", None, "created", {"nome": nome, "setor": setor}, user)
    return sess

def registrar_contagem(store_id: int, session_id: int, product_id: int, qtd_contada: Decimal, user: Optional[User]) -> InventoryCount:
    sess = db.session.get(InventorySession, session_id)
    _ensure(sess and sess.store_id == store_id and sess.aberta, "Sessão inválida")
    p = db.session.get(Product, product_id)
    _ensure(p and p.store_id == store_id, "Produto inválido")
    si = db.session.query(StockItem).filter_by(store_id=store_id, product_id=product_id).first()
    qtd_atual = _as_qtd(si.quantidade if si else 0)
    ic = db.session.query(InventoryCount).filter_by(session_id=session_id, product_id=product_id).first()
    if ic:
        before = _row_to_dict(ic, ["qtd_contada", "qtd_atual", "conciliado"])
        ic.qtd_contada = _as_qtd(qtd_contada)
        ic.qtd_atual = qtd_atual
        ic.conciliado = False
        audit_log(store_id, "InventoryCount", ic.id, "updated", {"before": before, "after": _row_to_dict(ic, ["qtd_contada", "qtd_atual", "conciliado"])}, user)
        return ic
    ic = InventoryCount(
        store_id=store_id,
        session_id=session_id,
        product_id=product_id,
        qtd_contada=_as_qtd(qtd_contada),
        qtd_atual=qtd_atual,
        conciliado=False,
        created_by_id=user.id if user else None
    )
    db.session.add(ic)
    audit_log(store_id, "InventoryCount", None, "created", {"product_id": product_id, "qtd_contada": str(qtd_contada)}, user)
    return ic

def conciliar_inventario(store_id: int, session_id: int, user: Optional[User]) -> Tuple[int, int]:
    sess = db.session.get(InventorySession, session_id)
    _ensure(sess and sess.store_id == store_id and sess.aberta, "Sessão inválida")
    counts = db.session.query(InventoryCount).filter_by(session_id=session_id).all()
    _ensure(len(counts) > 0, "Sessão sem contagens")

    entradas = 0
    saidas = 0
    for ic in counts:
        if ic.conciliado:
            continue
        dif = _as_qtd(ic.qtd_contada) - _as_qtd(ic.qtd_atual)
        if dif == 0:
            ic.conciliado = True
            continue
        tipo = "entrada_ajuste" if dif > 0 else "saida_ajuste"
        qtd = abs(dif)
        sm = StockMove(
            store_id=store_id,
            product_id=ic.product_id,
            tipo=tipo,
            qtd=_as_qtd(qtd),
            custo=Decimal("0.00"),
            ref_origem="inventory",
            ref_id=session_id,
            motivo="Inventário",
            created_by_id=user.id if user else None
        )
        db.session.add(sm)
        ic.conciliado = True
        entradas += 1 if dif > 0 else 0
        saidas += 1 if dif < 0 else 0

    sess.aberta = False
    audit_log(store_id, "InventorySession", sess.id, "reconciled", {"entradas": entradas, "saidas": saidas}, user)
    return entradas, saidas

# =============================================================================
# Financeiro simples
# =============================================================================

def listar_fluxo_caixa(store_id: int, data_ini: datetime, data_fim: datetime) -> Dict[str, Any]:
    """Retorna um resumo simples de fluxo de caixa por período."""
    recs = db.session.query(Receivable).filter(
        Receivable.store_id == store_id,
        Receivable.vencimento >= data_ini,
        Receivable.vencimento < data_fim
    ).all()
    pays = db.session.query(Payable).filter(
        Payable.store_id == store_id,
        Payable.vencimento >= data_ini,
        Payable.vencimento < data_fim
    ).all()
    total_receber = sum((_as_money(r.valor) for r in recs if r.status == "aberto"), _as_money(0))
    total_pagar = sum((_as_money(p.valor) for p in pays if p.status == "aberto"), _as_money(0))
    return {
        "a_receber": str(_as_money(total_receber)),
        "a_pagar": str(_as_money(total_pagar)),
        "saldo_previsto": str(_as_money(total_receber - total_pagar)),
        "count_recebiveis": len(recs),
        "count_pagaveis": len(pays),
    }

# =============================================================================
# Relatórios básicos
# =============================================================================

def relatorio_vendas_por_dia(store_id: int, data_ini: datetime, data_fim: datetime) -> List[Dict[str, Any]]:
    q = (
        db.session.query(
            Sale.created_at.label("dia"),
            db.func.sum(Sale.total).label("total"),
            db.func.count(Sale.id).label("qtd")
        )
        .filter(
            Sale.store_id == store_id,
            Sale.status == "concluida",
            Sale.created_at >= data_ini,
            Sale.created_at < data_fim
        )
        .group_by(db.func.date(Sale.created_at))
        .order_by(db.func.date(Sale.created_at))
    )
    out = []
    for row in q:
        out.append({"dia": row.dia.date().isoformat(), "total": str(_as_money(row.total or 0)), "qtd": int(row.qtd or 0)})
    return out

def relatorio_giro_estoque(store_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Top produtos por vendas (qtd) em toda a base. Ajuste filtros no controlador conforme necessário.
    """
    q = (
        db.session.query(
            Product.id, Product.nome,
            db.func.sum(SaleItem.qtd).label("qtd"),
            db.func.sum(SaleItem.total).label("faturamento")
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(
            Product.store_id == store_id,
            Product.deleted.is_(False),
            Sale.status == "concluida"
        )
        .group_by(Product.id, Product.nome)
        .order_by(db.desc("qtd"))
        .limit(limit)
    )
    out = []
    for row in q:
        out.append({
            "product_id": row.id,
            "nome": row.nome,
            "qtd": str(_as_qtd(row.qtd or 0)),
            "faturamento": str(_as_money(row.faturamento or 0))
        })
    return out

# =============================================================================
# Operações de inicialização
# =============================================================================

def criar_loja_e_admin(nome_loja: str, admin_email: str, admin_pass: str) -> Tuple[Store, User]:
    if not nome_loja.strip():
        raise ServiceError("Nome da loja obrigatório")
    loja = Store(nome=nome_loja.strip(), ativo=True)
    db.session.add(loja)
    db.session.flush()
    user = User(store_id=loja.id, nome="Administrador", email=admin_email.lower(), role="admin", ativo=True)
    user.set_password(admin_pass)
    db.session.add(user)
    audit_log(loja.id, "Store", loja.id, "created", {"nome": nome_loja}, user)
    return loja, user

# =============================================================================
# Padrões de uso transacional
# =============================================================================
# Exemplo de uso no controller:
# with transaction():
#     compra = criar_pedido_compra(store_id, supplier_id, itens, current_user)
#     enviar_compra(compra.id, current_user)
#
# with transaction():
#     venda = abrir_venda(store_id, caixa_id, current_user)
#     adicionar_item_venda(venda.id, product_id, Decimal("1"), current_user)
#     pagar_venda(venda.id, "dinheiro", Decimal("100"), None, current_user)
