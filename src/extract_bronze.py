"""Carga histórica da bronze — roda uma vez.

Report A (site): mês a mês de DATA_INICIO_HISTORICO até ontem.
Report B (painéis): mês a mês de DATA_INICIO_PAINEIS até ontem.
Report C (usuários): mês a mês de DATA_INICIO_HISTORICO até ontem.
Report D (páginas de painel): mês a mês de DATA_INICIO_PAGINAS até ontem.
Cada chamada ao runReport fica limitada a ~1 mês, abaixo do teto de linhas da API.

`--relatorios usuarios` carrega só um relatório (ex.: ao incluir o Report C num
banco que já tem site e painel).
"""

import argparse
from datetime import date, timedelta

from config import DATA_INICIO_HISTORICO, DATA_INICIO_PAGINAS, DATA_INICIO_PAINEIS
from db import get_connection
from ga4_client import extrair_paginas, extrair_paineis, extrair_site, extrair_usuarios
from load_bronze import gravar_snapshot_diario
from load_silver import executar_transformacao_silver


def _primeiro_dia_proximo_mes(d):
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def iterar_meses(inicio, fim):
    cursor = inicio.replace(day=1)
    while cursor <= fim:
        ini = max(cursor, inicio)
        fim_mes = _primeiro_dia_proximo_mes(cursor) - timedelta(days=1)
        yield ini, min(fim_mes, fim)
        cursor = _primeiro_dia_proximo_mes(cursor)


def registrar_execucao(conn, relatorio, inicio, fim, qtd_dias, qtd_linhas):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.controle_execucao
                (relatorio, tipo_carga, data_inicio_janela, data_fim_janela, qtd_dias, qtd_linhas)
            VALUES (%s, 'historico', %s, %s, %s, %s);
            """,
            (relatorio, inicio, fim, qtd_dias, qtd_linhas),
        )
    conn.commit()


def _carregar(relatorio, extrator, inicio, fim):
    print(f"\n=== Report '{relatorio}': {inicio} -> {fim} ===")
    total_dias = total_linhas = 0
    with get_connection() as conn:
        for ini_mes, fim_mes in iterar_meses(inicio, fim):
            registros = extrator(ini_mes, fim_mes)
            resultado = gravar_snapshot_diario(conn, relatorio, registros)
            dias, linhas = len(resultado), sum(resultado.values())
            total_dias += dias
            total_linhas += linhas
            print(f"  {ini_mes:%Y-%m}: {dias} dias, {linhas} linhas")
        registrar_execucao(conn, relatorio, inicio, fim, total_dias, total_linhas)
    print(f"  total: {total_dias} dias, {total_linhas} linhas")


RELATORIOS = ("site", "painel", "usuarios", "paginas")


def executar_carga_historica(inicio_site, inicio_painel, fim, relatorios=RELATORIOS):
    if "site" in relatorios:
        _carregar("site", extrair_site, inicio_site, fim)
    if "painel" in relatorios:
        _carregar("painel", extrair_paineis, inicio_painel, fim)
    if "usuarios" in relatorios:
        _carregar("usuarios", extrair_usuarios, inicio_site, fim)
    if "paginas" in relatorios:
        _carregar("paginas", extrair_paginas, max(inicio_painel, DATA_INICIO_PAGINAS), fim)
    print("\nTransformando silver...")
    executar_transformacao_silver()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga histórica da bronze")
    parser.add_argument("--inicio-site", type=date.fromisoformat, default=DATA_INICIO_HISTORICO)
    parser.add_argument("--inicio-painel", type=date.fromisoformat, default=DATA_INICIO_PAINEIS)
    parser.add_argument("--fim", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--relatorios", default=",".join(RELATORIOS),
                        help="lista separada por vírgula: site,painel,usuarios,paginas")
    args = parser.parse_args()
    relatorios = tuple(r.strip() for r in args.relatorios.split(","))
    invalidos = set(relatorios) - set(RELATORIOS)
    if invalidos:
        parser.error(f"relatório desconhecido: {', '.join(sorted(invalidos))}")
    executar_carga_historica(args.inicio_site, args.inicio_painel, args.fim, relatorios)
