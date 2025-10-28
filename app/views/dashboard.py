# app/views/dashboard.py
from __future__ import annotations

from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.core.services import relatorio_vendas_por_dia, listar_fluxo_caixa

bp = Blueprint("dashboard", __name__, template_folder="../templates")

@bp.get("/")
@login_required
def index():
    # Período: últimos 7 dias
    hoje = datetime.utcnow().date()
    data_ini = datetime(hoje.year, hoje.month, hoje.day) - timedelta(days=6)
    data_fim = datetime(hoje.year, hoje.month, hoje.day) + timedelta(days=1)

    vendas = relatorio_vendas_por_dia(current_user.store_id, data_ini, data_fim)
    caixa = listar_fluxo_caixa(current_user.store_id, data_ini, data_fim)

    return render_template("dashboard.html", vendas=vendas, caixa=caixa)
