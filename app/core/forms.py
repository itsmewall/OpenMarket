# app/core/forms.py
from __future__ import annotations

from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    DecimalField, SelectField, IntegerField, TextAreaField,
    DateField
)
from wtforms.validators import (
    DataRequired, Length, Email, Optional as Opt, NumberRange, ValidationError
)
import re
# se quiser upload CSV simples no admin
try:
    from flask_wtf.file import FileField, FileAllowed
    _HAS_FILE = True
except Exception:
    _HAS_FILE = False


# ========================
# Helpers
# ========================

def _to_int_or_none(v):
    """Coerce seguro para SelectField com placeholder vazio."""
    try:
        if v in ("", None):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_decimal_or_zero(s: str | None, places: int = 2) -> Decimal:
    if s in (None, ""):
        return Decimal("0.00") if places == 2 else Decimal("0.0000")
    s = str(s).replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0.00") if places == 2 else Decimal("0.0000")


# ========================
# Auth
# ========================

class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=72)])
    remember = BooleanField("Manter conectado", default=False)
    submit = SubmitField("Entrar")


# ========================
# Empresa e Usuários
# ========================

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
    role = SelectField(
        "Perfil",
        choices=[("admin","Administrador"),("gerente","Gerente"),("estoquista","Estoquista"),("operador","Operador")],
        validators=[DataRequired()]
    )
    senha = PasswordField("Senha", validators=[DataRequired(), Length(min=6, max=72)])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Criar")


class UserEditForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=180)])
    role = SelectField(
        "Perfil",
        choices=[("admin","Administrador"),("gerente","Gerente"),("estoquista","Estoquista"),("operador","Operador")],
        validators=[DataRequired()]
    )
    nova_senha = PasswordField("Nova senha", validators=[Opt(), Length(min=6, max=72)])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")


# ========================
# Busca genérica
# ========================

class SearchForm(FlaskForm):
    q = StringField("Buscar", validators=[Opt(), Length(max=200)])
    submit = SubmitField("Buscar")


# ========================
# Categorias
# ========================

class CategoryForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    markup_padrao = DecimalField("Markup padrão (%)", places=2, rounding=None,
                                 validators=[Opt(), NumberRange(min=0)])
    ativo = BooleanField("Ativa", default=True)
    submit = SubmitField("Salvar")


# ========================
# Produtos
# ========================

class ProductForm(FlaskForm):
    nome = StringField("Produto", validators=[DataRequired(), Length(max=200)])
    sku = StringField("Código interno (opcional)", validators=[Opt(), Length(max=60)])
    ean = StringField("Código de barras (opcional)", validators=[Opt(), Length(max=20)])
    categoria_id = SelectField("Categoria", coerce=_to_int_or_none, validators=[Opt()], default=None)
    unidade = SelectField("Unidade de venda", choices=[("UN","Unidade"), ("KG","Quilo"), ("L","Litro")], validators=[DataRequired()])
    ncm = StringField("NCM (opcional)", validators=[Opt(), Length(max=10)])
    cest = StringField("CEST (opcional)", validators=[Opt(), Length(max=10)])
    custo_atual = DecimalField("Preço de compra", places=2, rounding=None, validators=[Opt(), NumberRange(min=0)])
    preco_venda = DecimalField("Preço de venda", places=2, rounding=None, validators=[Opt(), NumberRange(min=0)])
    margem_alvo = DecimalField("Lucro desejado (%) (opcional)", places=2, rounding=None, validators=[Opt(), NumberRange(min=0)])
    estoque_minimo = DecimalField("Avisar quando tiver menos que", places=4, rounding=None, validators=[Opt(), NumberRange(min=0)])
    ponto_pedido = DecimalField("Repor quando chegar em", places=4, rounding=None, validators=[Opt(), NumberRange(min=0)])
    foto_url = StringField("Foto (link)", validators=[Opt(), Length(max=255)])
    ativo = BooleanField("Produto ativo", default=True)
    submit = SubmitField("Salvar")

    def validate_ean(self, field):
        txt = (field.data or "").strip()
        if not txt:
            return
        digits = re.sub(r"\D+", "", txt)
        if digits == "":
            # se a pessoa digitou só letras/espaços, trate como vazio
            field.data = ""
            return
        if len(digits) not in (8, 12, 13, 14):
            raise ValidationError("Código de barras deve ter 8, 12, 13 ou 14 números.")
        # normaliza para só dígitos
        field.data = digits


# ========================
# Fornecedores e Clientes
# ========================

class SupplierForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=180)])
    cnpj = StringField("CNPJ", validators=[Opt(), Length(max=18)])
    ie = StringField("IE", validators=[Opt(), Length(max=32)])
    contato = StringField("Contato", validators=[Opt(), Length(max=120)])
    telefone = StringField("Telefone", validators=[Opt(), Length(max=40)])
    email = StringField("E-mail", validators=[Opt(), Email(), Length(max=180)])
    prazo_dias = IntegerField("Prazo (dias)", validators=[Opt(), NumberRange(min=0)], default=0)
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")


class CustomerForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=180)])
    cpf = StringField("CPF", validators=[Opt(), Length(max=14)])
    telefone = StringField("Telefone", validators=[Opt(), Length(max=40)])
    email = StringField("E-mail", validators=[Opt(), Email(), Length(max=180)])
    pontos = IntegerField("Pontos", validators=[Opt(), NumberRange(min=0)], default=0)
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar")


# ========================
# Promoções
# ========================

class PromoForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    # a regra é um JSON na model, aqui mantemos um campo de texto para edição rápida
    regra_json = TextAreaField("Regra (JSON)", validators=[DataRequired(), Length(max=2000)])
    validade_ini = DateField("Validade inicial", validators=[DataRequired()], format="%Y-%m-%d")
    validade_fim = DateField("Validade final", validators=[Opt()], format="%Y-%m-%d")
    prioridade = IntegerField("Prioridade", validators=[Opt(), NumberRange(min=0)], default=100)
    ativa = BooleanField("Ativa", default=True)
    submit = SubmitField("Salvar")


# ========================
# Inventário
# ========================

class InventorySessionForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(max=120)])
    setor = StringField("Setor", validators=[Opt(), Length(max=120)])
    aberta = BooleanField("Aberta", default=True)
    submit = SubmitField("Salvar")


class InventoryCountForm(FlaskForm):
    session_id = SelectField("Sessão", coerce=_to_int_or_none, validators=[DataRequired()])
    product_id = SelectField("Produto", coerce=_to_int_or_none, validators=[DataRequired()])
    qtd_contada = DecimalField("Quantidade contada", places=4, rounding=None,
                               validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Lançar contagem")


# ========================
# Caixa
# ========================

class CashOpenForm(FlaskForm):
    nome = StringField("Nome do caixa", validators=[DataRequired(), Length(max=60)])
    saldo_abertura = DecimalField("Saldo de abertura", places=2, rounding=None,
                                  validators=[Opt(), NumberRange(min=0)], default=Decimal("0.00"))
    submit = SubmitField("Abrir caixa")


class CashCloseForm(FlaskForm):
    saldo_fechamento = DecimalField("Saldo de fechamento", places=2, rounding=None,
                                    validators=[Opt(), NumberRange(min=0)], default=Decimal("0.00"))
    submit = SubmitField("Fechar caixa")


# ========================
# Compras
# ========================

class PurchaseForm(FlaskForm):
    supplier_id = SelectField("Fornecedor", coerce=_to_int_or_none, validators=[DataRequired()])
    previsto_para = DateField("Previsto para", validators=[Opt()], format="%Y-%m-%d")
    submit = SubmitField("Salvar")


class PurchaseItemForm(FlaskForm):
    product_id = SelectField("Produto", coerce=_to_int_or_none, validators=[DataRequired()])
    qtd = DecimalField("Quantidade", places=4, rounding=None,
                       validators=[DataRequired(), NumberRange(min=0.0001)])
    custo = DecimalField("Custo", places=2, rounding=None,
                         validators=[DataRequired(), NumberRange(min=0)])
    desconto = DecimalField("Desconto (R$)", places=2, rounding=None,
                            validators=[Opt(), NumberRange(min=0)], default=Decimal("0.00"))
    submit = SubmitField("Adicionar item")


# ========================
# PDV / Vendas
# ========================

class SaleOpenForm(FlaskForm):
    customer_id = SelectField("Cliente", coerce=_to_int_or_none, validators=[Opt()], default=None)
    submit = SubmitField("Abrir venda")


class SaleAddItemForm(FlaskForm):
    product_id = SelectField("Produto", coerce=_to_int_or_none, validators=[DataRequired()])
    qtd = DecimalField("Quantidade", places=4, rounding=None,
                       validators=[DataRequired(), NumberRange(min=0.0001)])
    preco_unit = DecimalField("Preço unitário", places=2, rounding=None,
                              validators=[Opt(), NumberRange(min=0)])
    desconto = DecimalField("Desconto (R$)", places=2, rounding=None,
                            validators=[Opt(), NumberRange(min=0)], default=Decimal("0.00"))
    submit = SubmitField("Adicionar")


class SalePaymentForm(FlaskForm):
    pagamento = SelectField(
        "Forma de pagamento",
        choices=[("dinheiro", "Dinheiro"), ("cartao", "Cartão"), ("pix", "PIX"), ("misto", "Misto")],
        validators=[DataRequired()],
    )
    valor_recebido = DecimalField("Valor recebido (R$)", places=2, rounding=None,
                                  validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Concluir venda")


class SaleCancelForm(FlaskForm):
    motivo = StringField("Motivo", validators=[Opt(), Length(max=200)])
    confirmar = BooleanField("Confirmo o cancelamento", validators=[DataRequired()])
    submit = SubmitField("Cancelar venda")


# ========================
# Utilidades de admin
# ========================

class CsvImportForm(FlaskForm):
    if _HAS_FILE:
        file = FileField("Arquivo CSV", validators=[DataRequired(), FileAllowed(["csv"], "Apenas CSV")])
    submit = SubmitField("Importar")
