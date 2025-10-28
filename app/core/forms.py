# app/core/forms.py
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, IntegerField, HiddenField,
    SelectField, DateTimeLocalField, TextAreaField, SubmitField, FieldList,
    FormField
)
from wtforms.validators import (
    DataRequired, Optional as Opt, Length, NumberRange, Email, Regexp
)
from wtforms.widgets import HiddenInput


# =============================================================================
# Utilidades
# =============================================================================

UNIDADE_CHOICES = [("UN", "UN"), ("KG", "KG"), ("L", "L")]

def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _q4(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

def parse_decimal(text: Optional[str], places: int = 2) -> Decimal:
    """
    Converte string para Decimal aceitando vírgula ou ponto.
    Vazio vira 0. Evita crash em inputs ruins.
    """
    if text is None:
        return Decimal("0")
    s = text.strip()
    if s == "":
        return Decimal("0")
    s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 and s.count(".") > 0 else s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError("Valor numérico inválido")
    return _q4(d) if places == 4 else _q2(d)

def normalize_ean(ean: Optional[str]) -> Optional[str]:
    if not ean:
        return None
    digits = re.sub(r"\D+", "", ean)
    return digits or None


# =============================================================================
# Campos customizados
# =============================================================================

from wtforms.fields.core import Field

class DecimalMoneyField(Field):
    """
    Entrada textual que vira Decimal com 2 casas.
    """
    def __init__(self, label=None, validators=None, places: int = 2, **kwargs):
        super().__init__(label, validators, **kwargs)
        self.places = places
        self.data = Decimal("0")

    def _value(self):
        return str(self.data) if isinstance(self.data, Decimal) else (self.data or "")

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = parse_decimal(valuelist[0], places=2)
            except ValueError as e:
                raise ValueError(str(e))

class DecimalQtyField(Field):
    """
    Entrada textual que vira Decimal com 4 casas.
    """
    def __init__(self, label=None, validators=None, **kwargs):
        super().__init__(label, validators, **kwargs)
        self.data = Decimal("0")

    def _value(self):
        return str(self.data) if isinstance(self.data, Decimal) else (self.data or "")

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = parse_decimal(valuelist[0], places=4)
            except ValueError as e:
                raise ValueError(str(e))


# =============================================================================
# Forms de Autenticação
# =============================================================================

class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=72)])
    remember = BooleanField("Manter conectado")
    submit = SubmitField("Entrar")


# =============================================================================
# Cadastros
# =============================================================================

class CategoryForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    markup_padrao = DecimalMoneyField("Markup padrão %", validators=[Opt()])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")

class ProductForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=200)])
    sku = StringField("SKU", validators=[Opt(), Length(max=60)])
    ean = StringField("EAN", validators=[Opt(), Length(max=14)])
    categoria_id = SelectField("Categoria", choices=[], coerce=int, validators=[Opt()])
    unidade = SelectField("Unidade", choices=UNIDADE_CHOICES, validators=[DataRequired()])
    ncm = StringField("NCM", validators=[Opt(), Length(max=10)])
    cest = StringField("CEST", validators=[Opt(), Length(max=10)])
    custo_atual = DecimalMoneyField("Custo atual", validators=[Opt()])
    preco_venda = DecimalMoneyField("Preço de venda", validators=[Opt()])
    margem_alvo = DecimalQtyField("Margem alvo %", validators=[Opt()])
    estoque_minimo = DecimalQtyField("Estoque mínimo", validators=[Opt()])
    ponto_pedido = DecimalQtyField("Ponto de pedido", validators=[Opt()])
    foto_url = StringField("URL da foto", validators=[Opt(), Length(max=255)])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")

    def validate_ean(self, field):
        if field.data:
            digits = normalize_ean(field.data)
            if digits and len(digits) not in (8, 12, 13, 14):
                raise ValueError("EAN inválido")
            field.data = digits

class SupplierForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=180)])
    cnpj = StringField("CNPJ", validators=[Opt(), Length(max=18)])
    ie = StringField("IE", validators=[Opt(), Length(max=32)])
    contato = StringField("Contato", validators=[Opt(), Length(max=120)])
    telefone = StringField("Telefone", validators=[Opt(), Length(max=40)])
    email = StringField("E-mail", validators=[Opt(), Email(), Length(max=180)])
    prazo_dias = IntegerField("Prazo padrão (dias)", validators=[Opt(), NumberRange(min=0, max=365)])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")

class CustomerForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=180)])
    cpf = StringField("CPF", validators=[Opt(), Length(max=14)])
    telefone = StringField("Telefone", validators=[Opt(), Length(max=40)])
    email = StringField("E-mail", validators=[Opt(), Email(), Length(max=180)])
    pontos = IntegerField("Pontos", validators=[Opt(), NumberRange(min=0)])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")


# =============================================================================
# Compras
# =============================================================================

class PurchaseItemInlineForm(FlaskForm):
    product_id = SelectField("Produto", coerce=int, validators=[DataRequired()])
    qtd = DecimalQtyField("Qtd", validators=[DataRequired()])
    custo = DecimalMoneyField("Custo", validators=[DataRequired()])
    desconto = DecimalMoneyField("Desconto", validators=[Opt()])
    total = DecimalMoneyField("Total", validators=[Opt()])

    def validate_total(self, field):
        # total = qtd * custo - desconto, se não vier, calcula
        if not field.data or field.data == Decimal("0.00"):
            try:
                total_calc = _q2(self.qtd.data * self.custo.data - (self.desconto.data or Decimal("0")))
                field.data = total_calc
            except Exception:
                raise ValueError("Não foi possível calcular total")

class PurchaseForm(FlaskForm):
    supplier_id = SelectField("Fornecedor", coerce=int, validators=[DataRequired()])
    previsto_para = DateTimeLocalField("Previsto para", format="%Y-%m-%dT%H:%M", validators=[Opt()])
    itens = FieldList(FormField(PurchaseItemInlineForm), min_entries=1)
    submit = SubmitField("Salvar pedido")

    def validate_itens(self, field):
        if not field.entries:
            raise ValueError("Inclua pelo menos 1 item")
        for entry in field.entries:
            if entry.form.qtd.data <= 0:
                raise ValueError("Quantidade deve ser positiva")


# =============================================================================
# Estoque
# =============================================================================

class StockAdjustForm(FlaskForm):
    product_id = SelectField("Produto", coerce=int, validators=[DataRequired()])
    tipo = SelectField("Tipo", choices=[("entrada_ajuste", "Entrada de ajuste"), ("saida_ajuste", "Saída de ajuste")], validators=[DataRequired()])
    qtd = DecimalQtyField("Quantidade", validators=[DataRequired()])
    motivo = StringField("Motivo", validators=[Opt(), Length(max=200)])
    submit = SubmitField("Aplicar ajuste")


# =============================================================================
# Inventário
# =============================================================================

class InventorySessionForm(FlaskForm):
    nome = StringField("Nome da sessão", validators=[DataRequired(), Length(max=120)])
    setor = StringField("Setor", validators=[Opt(), Length(max=120)])
    submit = SubmitField("Criar sessão")

class InventoryCountForm(FlaskForm):
    session_id = HiddenField()
    product_id = SelectField("Produto", coerce=int, validators=[DataRequired()])
    qtd_contada = DecimalQtyField("Quantidade contada", validators=[DataRequired()])
    submit = SubmitField("Registrar")

    def validate_qtd_contada(self, field):
        if field.data <= 0:
            raise ValueError("Quantidade deve ser positiva")


# =============================================================================
# Preços e Promoções
# =============================================================================

class PricePublishForm(FlaskForm):
    product_id = SelectField("Produto", coerce=int, validators=[DataRequired()])
    preco = DecimalMoneyField("Novo preço", validators=[DataRequired()])
    origem = SelectField("Origem", choices=[("manual", "Manual"), ("regra_categoria", "Regra de categoria"), ("promocao", "Promoção")], validators=[DataRequired()])
    submit = SubmitField("Publicar")

class PromoForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    tipo = SelectField("Tipo", choices=[("desconto_percentual", "Desconto percentual"), ("leve3_pague2", "Leve 3 pague 2"), ("combo", "Combo")], validators=[DataRequired()])
    valor = DecimalMoneyField("Valor/Percentual", validators=[Opt()])
    validade_ini = DateTimeLocalField("Validade inicial", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    validade_fim = DateTimeLocalField("Validade final", format="%Y-%m-%dT%H:%M", validators=[Opt()])
    prioridade = IntegerField("Prioridade", validators=[Opt(), NumberRange(min=1, max=999)], default=100)
    ativa = BooleanField("Ativa", default=True)
    submit = SubmitField("Salvar")

    def to_regra_json(self) -> dict:
        t = self.tipo.data
        if t == "desconto_percentual":
            v = self.valor.data or Decimal("0")
            return {"type": t, "value": float(v)}
        return {"type": t}


# =============================================================================
# PDV
# =============================================================================

class SaleOpenForm(FlaskForm):
    caixa_id = SelectField("Caixa", coerce=int, validators=[Opt()])
    submit = SubmitField("Abrir venda")

class SaleAddItemForm(FlaskForm):
    sale_id = HiddenField(widget=HiddenInput())
    product_id = SelectField("Produto", coerce=int, validators=[DataRequired()])
    qtd = DecimalQtyField("Qtd", validators=[DataRequired()])
    submit = SubmitField("Adicionar")

    def validate_qtd(self, field):
        if field.data <= 0:
            raise ValueError("Quantidade deve ser positiva")

class SalePaymentForm(FlaskForm):
    sale_id = HiddenField(widget=HiddenInput())
    pagamento = SelectField("Pagamento", choices=[("dinheiro", "Dinheiro"), ("cartao", "Cartão"), ("pix", "PIX"), ("misto", "Misto")], validators=[DataRequired()])
    valor_pago = DecimalMoneyField("Valor pago", validators=[DataRequired()])
    customer_id = SelectField("Cliente", coerce=int, validators=[Opt()])
    submit = SubmitField("Finalizar")

    def validate_valor_pago(self, field):
        if field.data < Decimal("0"):
            raise ValueError("Valor pago inválido")

class SaleCancelForm(FlaskForm):
    sale_id = HiddenField(widget=HiddenInput())
    motivo = StringField("Motivo", validators=[Opt(), Length(max=200)])
    submit = SubmitField("Cancelar venda")


# =============================================================================
# Relatórios e Busca
# =============================================================================

class DateRangeForm(FlaskForm):
    data_ini = DateTimeLocalField("De", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    data_fim = DateTimeLocalField("Até", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    submit = SubmitField("Filtrar")

class SearchForm(FlaskForm):
    q = StringField("Buscar", validators=[Opt(), Length(max=120)])
    submit = SubmitField("Pesquisar")

class StoreForm(FlaskForm):
    nome = StringField("Nome da empresa", validators=[DataRequired(), Length(max=120)])
    cnpj = StringField("CNPJ", validators=[Opt(), Length(max=18)])
    ie = StringField("IE", validators=[Opt(), Length(max=32)])
    uf = StringField("UF", validators=[Opt(), Length(max=2)])
    cidade = StringField("Cidade", validators=[Opt(), Length(max=80)])
    timezone = StringField("Timezone", validators=[DataRequired(), Length(max=40)], default="America/Sao_Paulo")
    ativo = BooleanField("Ativa", default=True)
    submit = SubmitField("Salvar")

class UserCreateForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    role = SelectField("Perfil", choices=[("admin","Administrador"),("gerente","Gerente"),("estoquista","Estoquista"),("operador","Operador")], validators=[DataRequired()])
    senha = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=72)])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Criar")

class UserEditForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    role = SelectField("Perfil", choices=[("admin","Administrador"),("gerente","Gerente"),("estoquista","Estoquista"),("operador","Operador")], validators=[DataRequired()])
    nova_senha = PasswordField("Nova senha", validators=[Opt(), Length(min=6, max=72)])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")