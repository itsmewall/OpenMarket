# app/core/models.py
from __future__ import annotations

import os
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import (
    CheckConstraint, Column, Integer, BigInteger, String, DateTime,
    Boolean, ForeignKey, UniqueConstraint, Numeric, Enum, JSON, Index, event,
    func
)
from sqlalchemy.orm import relationship, backref, validates
from werkzeug.security import generate_password_hash as _wzh, check_password_hash as _wzc

from app.extensions import db  # type: ignore


# =============================================================================
# Utilidades e Mixins
# =============================================================================

MONEY = Numeric(12, 2)   # 999.999.999,99 máx
QTD = Numeric(14, 4)     # quantidades com 4 casas

def _as_money(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _as_qtd(value) -> Decimal:
    if value is None:
        return Decimal("0.0000")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

def normalize_ean(ean: Optional[str]) -> Optional[str]:
    if not ean:
        return None
    digits = re.sub(r"\D+", "", ean)
    return digits or None

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

class SoftDeleteMixin:
    deleted = Column(Boolean, default=False, nullable=False, index=True)

class StoreScopedMixin:
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True)

class AuditMixin:
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)


# =============================================================================
# Enums
# =============================================================================

RoleEnum = Enum("admin", "gerente", "estoquista", "operador", name="role_enum")
PurchaseStatusEnum = Enum("rascunho", "emitida", "parcialmente_recebida", "recebida", "cancelada", name="purchase_status_enum")
SaleStatusEnum = Enum("aberta", "concluida", "cancelada", name="sale_status_enum")
PaymentEnum = Enum("dinheiro", "cartao", "pix", "misto", name="payment_enum")
StockMoveEnum = Enum("entrada_compra", "entrada_ajuste", "saida_venda", "saida_ajuste", "devolucao", name="stock_move_enum")
PayRecStatusEnum = Enum("aberto", "pago", "cancelado", name="payrec_status_enum")


# =============================================================================
# Tabelas principais
# =============================================================================

class Store(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    cnpj = Column(String(18), nullable=True)
    ie = Column(String(32), nullable=True)
    uf = Column(String(2), nullable=True)
    cidade = Column(String(80), nullable=True)
    timezone = Column(String(40), default="America/Sao_Paulo", nullable=False)
    ativo = Column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("nome", name="uq_stores_nome"),
    )

    def __repr__(self):
        return f"<Store {self.id} {self.nome}>"


class User(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(180), nullable=False, unique=True, index=True)
    _password_hash = Column("password_hash", String(255), nullable=False)
    role = Column(RoleEnum, nullable=False, default="operador", index=True)
    ativo = Column(Boolean, default=True, nullable=False)
    ultimo_login = Column(DateTime, nullable=True)

    store = relationship("Store", backref=backref("users", lazy="dynamic"))

    def set_password(self, raw: str):
        if not raw or len(raw) < 6:
            raise ValueError("Senha muito curta")
        # PBKDF2 do Werkzeug evita dependência de bcrypt
        self._password_hash = _wzh(raw, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, raw: str) -> bool:
        try:
            return _wzc(self._password_hash, raw)
        except Exception:
            return False

    @validates("email")
    def _val_email(self, key, value):
        if not value or "@" not in value:
            raise ValueError("Email inválido")
        return value.lower()

    def __repr__(self):
        return f"<User {self.id} {self.email} {self.role}>"


class Category(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    markup_padrao = Column(Numeric(6, 2), default=Decimal("0.00"), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("store_id", "nome", name="uq_categories_store_nome"),
    )


class Product(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    sku = Column(String(60), nullable=True, index=True)
    ean = Column(String(14), nullable=True, index=True)
    nome = Column(String(200), nullable=False, index=True)
    categoria_id = Column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True)
    unidade = Column(String(4), nullable=False, default="UN")  # UN, KG, L
    ncm = Column(String(10), nullable=True)
    cest = Column(String(10), nullable=True)
    custo_atual = Column(MONEY, default=Decimal("0.00"), nullable=False)
    preco_venda = Column(MONEY, default=Decimal("0.00"), nullable=False)
    margem_alvo = Column(Numeric(6, 2), default=Decimal("0.00"), nullable=False)
    estoque_minimo = Column(QTD, default=Decimal("0.0000"), nullable=False)
    ponto_pedido = Column(QTD, default=Decimal("0.0000"), nullable=False)
    foto_url = Column(String(255), nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)

    categoria = relationship("Category", backref=backref("products", lazy="dynamic"))
    stock_item = relationship("StockItem", uselist=False, back_populates="product")

    __table_args__ = (
        UniqueConstraint("store_id", "ean", name="uq_products_store_ean"),
        UniqueConstraint("store_id", "sku", name="uq_products_store_sku"),
        CheckConstraint("preco_venda >= 0", name="ck_products_preco_nao_negativo"),
        CheckConstraint("custo_atual >= 0", name="ck_products_custo_nao_negativo"),
        CheckConstraint("unidade in ('UN','KG','L')", name="ck_products_unidade"),
    )

    @validates("ean")
    def _val_ean(self, key, value):
        v = normalize_ean(value)
        if v and len(v) not in (8, 12, 13, 14):  # EAN8, UPC-A, EAN13, DUN-14
            raise ValueError("EAN inválido")
        return v

    @validates("preco_venda", "custo_atual")
    def _val_money(self, key, value):
        return _as_money(value)

    @validates("estoque_minimo", "ponto_pedido")
    def _val_qtd(self, key, value):
        v = _as_qtd(value)
        if v < 0:
            raise ValueError("Quantidade negativa")
        return v

    def __repr__(self):
        return f"<Product {self.id} {self.nome} EAN={self.ean}>"


class Supplier(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    nome = Column(String(180), nullable=False)
    cnpj = Column(String(18), nullable=True)
    ie = Column(String(32), nullable=True)
    contato = Column(String(120), nullable=True)
    telefone = Column(String(40), nullable=True)
    email = Column(String(180), nullable=True)
    prazo_dias = Column(Integer, default=0, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("store_id", "nome", name="uq_suppliers_store_nome"),
    )


class Customer(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    nome = Column(String(180), nullable=False)
    cpf = Column(String(14), nullable=True, index=True)
    telefone = Column(String(40), nullable=True)
    email = Column(String(180), nullable=True)
    pontos = Column(Integer, default=0, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("store_id", "cpf", name="uq_customers_store_cpf"),
        CheckConstraint("pontos >= 0", name="ck_customers_pontos"),
    )


class StockItem(db.Model, TimestampMixin, StoreScopedMixin):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    quantidade = Column(QTD, default=Decimal("0.0000"), nullable=False)
    reservado = Column(QTD, default=Decimal("0.0000"), nullable=False)

    product = relationship("Product", back_populates="stock_item")

    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_stock_items_store_product"),
        CheckConstraint("quantidade >= 0", name="ck_stock_items_qtd_nao_negativa"),
        CheckConstraint("reservado >= 0", name="ck_stock_items_reservado_nao_negativo"),
    )


class StockMove(db.Model, TimestampMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "stock_moves"

    id = Column(BigInteger, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    tipo = Column(StockMoveEnum, nullable=False, index=True)
    qtd = Column(QTD, nullable=False)
    custo = Column(MONEY, nullable=False, default=Decimal("0.00"))
    ref_origem = Column(String(30), nullable=True)  # "purchase", "sale" etc
    ref_id = Column(Integer, nullable=True)
    motivo = Column(String(200), nullable=True)

    product = relationship("Product")

    __table_args__ = (
        CheckConstraint("qtd > 0", name="ck_stock_moves_qtd_positiva"),
        CheckConstraint("custo >= 0", name="ck_stock_moves_custo_nao_negativo"),
        Index("ix_stock_moves_store_product_created", "store_id", "product_id", "created_at"),
    )


class Purchase(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(PurchaseStatusEnum, default="rascunho", nullable=False, index=True)
    total_previsto = Column(MONEY, default=Decimal("0.00"), nullable=False)
    total_recebido = Column(MONEY, default=Decimal("0.00"), nullable=False)
    previsto_para = Column(DateTime, nullable=True)

    supplier = relationship("Supplier", backref=backref("purchases", lazy="dynamic"))
    items = relationship("PurchaseItem", cascade="all, delete-orphan", backref="purchase")

    __table_args__ = (
        CheckConstraint("total_previsto >= 0", name="ck_purchases_previsto"),
        CheckConstraint("total_recebido >= 0", name="ck_purchases_recebido"),
    )


class PurchaseItem(db.Model, TimestampMixin):
    __tablename__ = "purchase_items"

    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    qtd = Column(QTD, nullable=False)
    custo = Column(MONEY, nullable=False)
    desconto = Column(MONEY, default=Decimal("0.00"), nullable=False)
    total = Column(MONEY, nullable=False)

    product = relationship("Product")

    __table_args__ = (
        CheckConstraint("qtd > 0", name="ck_purchase_items_qtd"),
        CheckConstraint("custo >= 0", name="ck_purchase_items_custo"),
        CheckConstraint("desconto >= 0", name="ck_purchase_items_desconto"),
        CheckConstraint("total >= 0", name="ck_purchase_items_total"),
        Index("ix_purchase_items_purchase_product", "purchase_id", "product_id"),
    )

    @validates("qtd")
    def _val_qtd(self, key, value):
        return _as_qtd(value)

    @validates("custo", "desconto", "total")
    def _val_money(self, key, value):
        return _as_money(value)


class PriceVersion(db.Model, TimestampMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "price_versions"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    preco = Column(MONEY, nullable=False)
    origem = Column(String(30), nullable=False, default="manual")  # manual, regra_categoria, promocao
    valido_de = Column(DateTime, nullable=False, default=datetime.utcnow)
    valido_ate = Column(DateTime, nullable=True)

    product = relationship("Product", backref=backref("prices", lazy="dynamic"))

    __table_args__ = (
        CheckConstraint("preco >= 0", name="ck_price_versions_preco"),
        Index("ix_price_versions_active", "product_id", "valido_de", "valido_ate"),
    )


class Promo(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "promos"

    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    regra_json = Column(JSON, nullable=False)  # exemplo: {"type":"desconto_percentual","value":10}
    validade_ini = Column(DateTime, nullable=False)
    validade_fim = Column(DateTime, nullable=True)
    prioridade = Column(Integer, default=100, nullable=False)
    ativa = Column(Boolean, default=True, nullable=False)


class CashRegister(db.Model, TimestampMixin, StoreScopedMixin):
    __tablename__ = "cash_registers"

    id = Column(Integer, primary_key=True)
    nome = Column(String(60), nullable=False)
    aberto_em = Column(DateTime, nullable=True)
    fechado_em = Column(DateTime, nullable=True)
    saldo_abertura = Column(MONEY, default=Decimal("0.00"), nullable=False)
    saldo_fechamento = Column(MONEY, default=Decimal("0.00"), nullable=False)
    aberto = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("store_id", "nome", name="uq_cash_registers_store_nome"),
    )


class Sale(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    caixa_id = Column(Integer, ForeignKey("cash_registers.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(SaleStatusEnum, default="aberta", nullable=False, index=True)
    subtotal = Column(MONEY, default=Decimal("0.00"), nullable=False)
    desconto = Column(MONEY, default=Decimal("0.00"), nullable=False)
    total = Column(MONEY, default=Decimal("0.00"), nullable=False)
    pagamento = Column(PaymentEnum, nullable=True)
    troco = Column(MONEY, default=Decimal("0.00"), nullable=False)
    fiscal_chave = Column(String(60), nullable=True)

    caixa = relationship("CashRegister")
    customer = relationship("Customer")
    items = relationship("SaleItem", cascade="all, delete-orphan", backref="sale")

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_sales_subtotal"),
        CheckConstraint("desconto >= 0", name="ck_sales_desconto"),
        CheckConstraint("total >= 0", name="ck_sales_total"),
        CheckConstraint("troco >= 0", name="ck_sales_troco"),
    )


class SaleItem(db.Model, TimestampMixin):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    qtd = Column(QTD, nullable=False)
    preco_unit = Column(MONEY, nullable=False)
    desconto = Column(MONEY, default=Decimal("0.00"), nullable=False)
    promo_id = Column(Integer, ForeignKey("promos.id", ondelete="SET NULL"), nullable=True)
    total = Column(MONEY, nullable=False)

    product = relationship("Product")
    promo = relationship("Promo")

    __table_args__ = (
        CheckConstraint("qtd > 0", name="ck_sale_items_qtd"),
        CheckConstraint("preco_unit >= 0", name="ck_sale_items_preco"),
        CheckConstraint("desconto >= 0", name="ck_sale_items_desc"),
        CheckConstraint("total >= 0", name="ck_sale_items_total"),
    )

    @validates("qtd")
    def _val_qtd(self, key, value):
        return _as_qtd(value)

    @validates("preco_unit", "desconto", "total")
    def _val_money(self, key, value):
        return _as_money(value)


class Payable(db.Model, TimestampMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "payables"

    id = Column(Integer, primary_key=True)
    origem = Column(String(30), nullable=False)  # "purchase"
    ref_id = Column(Integer, nullable=False)
    fornecedor_id = Column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    valor = Column(MONEY, nullable=False)
    vencimento = Column(DateTime, nullable=False)
    status = Column(PayRecStatusEnum, default="aberto", nullable=False, index=True)

    supplier = relationship("Supplier")

    __table_args__ = (
        CheckConstraint("valor >= 0", name="ck_payables_valor"),
    )


class Receivable(db.Model, TimestampMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "receivables"

    id = Column(Integer, primary_key=True)
    origem = Column(String(30), nullable=False)  # "sale"
    ref_id = Column(Integer, nullable=False)
    cliente_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    valor = Column(MONEY, nullable=False)
    vencimento = Column(DateTime, nullable=False)
    status = Column(PayRecStatusEnum, default="aberto", nullable=False, index=True)

    customer = relationship("Customer")

    __table_args__ = (
        CheckConstraint("valor >= 0", name="ck_receivables_valor"),
    )


class InventorySession(db.Model, TimestampMixin, SoftDeleteMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "inventory_sessions"

    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    setor = Column(String(120), nullable=True)
    aberta = Column(Boolean, default=True, nullable=False)

    counts = relationship("InventoryCount", cascade="all, delete-orphan", backref="session")


class InventoryCount(db.Model, TimestampMixin, StoreScopedMixin, AuditMixin):
    __tablename__ = "inventory_counts"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("inventory_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    qtd_contada = Column(QTD, nullable=False)
    qtd_atual = Column(QTD, nullable=False)
    conciliado = Column(Boolean, default=False, nullable=False)

    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("session_id", "product_id", name="uq_inventory_counts_session_product"),
        CheckConstraint("qtd_contada >= 0", name="ck_inventory_counts_contada"),
        CheckConstraint("qtd_atual >= 0", name="ck_inventory_counts_atual"),
    )


class AuditLog(db.Model, TimestampMixin, StoreScopedMixin):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True)
    entidade = Column(String(60), nullable=False)
    entidade_id = Column(Integer, nullable=True)
    acao = Column(String(60), nullable=False)  # created, updated, deleted, inventory_adjust, price_change
    payload_json = Column(JSON, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip = Column(String(45), nullable=True)  # IPv4 ou IPv6

    user = relationship("User")


# =============================================================================
# Índices
# =============================================================================

Index("ix_products_nome_lower", func.lower(Product.nome))
Index("ix_suppliers_nome_lower", func.lower(Supplier.nome))
Index("ix_customers_nome_lower", func.lower(Customer.nome))


# =============================================================================
# Regras de estoque
# =============================================================================

def _apply_stock_move(mapper, connection, target: StockMove):
    """
    Aplica o movimento no StockItem de forma atômica.
    Garante que estoque não fique negativo.
    """
    # Busca ou cria o stock_item
    stock_items = db.session.query(StockItem).filter_by(
        store_id=target.store_id, product_id=target.product_id
    ).with_for_update(nowait=False).all()

    if stock_items:
        si = stock_items[0]
    else:
        si = StockItem(store_id=target.store_id, product_id=target.product_id, quantidade=Decimal("0.0000"))
        db.session.add(si)
        db.session.flush()

    qtd = _as_qtd(target.qtd)

    # Tipos de saída
    if target.tipo in ("saida_venda", "saida_ajuste"):
        novo = _as_qtd(si.quantidade) - qtd
        if novo < 0:
            raise ValueError("Operação causaria estoque negativo")
        si.quantidade = novo
    else:
        # entradas
        si.quantidade = _as_qtd(si.quantidade) + qtd

    # Atualização do custo médio em entradas de compra
    if target.tipo == "entrada_compra":
        prod = db.session.get(Product, target.product_id)
        if prod:
            # Cm = (Qt*Cm + q*c) / (Qt + q)
            Qt = _as_qtd(si.quantidade)
            q = qtd
            if Qt > 0:
                Cm_old = _as_money(prod.custo_atual)
                c = _as_money(target.custo)
                Cm_new = ((Cm_old * (Qt - q)) + (c * q)) / (Qt or Decimal("1.0"))
                prod.custo_atual = _as_money(Cm_new)
            else:
                prod.custo_atual = _as_money(target.custo)

event.listen(StockMove, "after_insert", _apply_stock_move)


# =============================================================================
# Seeds e utilidades
# =============================================================================

def ensure_admin():
    """
    Cria loja padrão e admin, se não existirem.
    Usa variáveis de ambiente ADMIN_EMAIL e ADMIN_PASS.
    """
    admin_email = os.getenv("ADMIN_EMAIL", "admin@local").lower()
    admin_pass = os.getenv("ADMIN_PASS", "admin123")

    store = Store.query.filter_by(nome="Loja Padrão").first()
    if not store:
        store = Store(nome="Loja Padrão", ativo=True)
        db.session.add(store)
        db.session.flush()

    user = User.query.filter_by(email=admin_email).first()
    if not user:
        user = User(
            store_id=store.id,
            nome="Administrador",
            email=admin_email,
            role="admin",
            ativo=True,
        )
        user.set_password(admin_pass)
        db.session.add(user)

    db.session.commit()