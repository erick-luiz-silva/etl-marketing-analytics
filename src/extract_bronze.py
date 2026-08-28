"""Carga histórica da bronze — roda uma vez.

Extrai mês a mês (cada chamada ao runReport fica limitada a ~1 mês de dados,
bem abaixo do teto de linhas da API) de DATA_INICIO_HISTORICO até ontem.
"""

import argparse
from datetime import date, timedelta

from config import DATA_INICIO_HISTORICO
from db import get_connection
from load_bronze import carregar_periodo_bronze
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


def registrar_execucao(conn, inicio, fim, qtd_dias, qtd_linhas):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.controle_execucao
                (tipo_carga, data_inicio_janela, data_fim_janela, qtd_dias, qtd_linhas)
            VALUES ('historico', %s, %s, %s, %s);
            """,
            (inicio, fim, qtd_dias, qtd_linhas),
        )
    conn.commit()


def executar_carga_historica(inicio, fim):
    print(f"Carga histórica bronze: {inicio} -> {fim}")
    total_dias = total_linhas = 0

    with get_connection() as conn:
        for ini_mes, fim_mes in iterar_meses(inicio, fim):
            resultado = carregar_periodo_bronze(conn, ini_mes, fim_mes)
            dias = len(resultado)
            linhas = sum(resultado.values())
            total_dias += dias
            total_linhas += linhas
            print(f"  {ini_mes:%Y-%m}: {dias} dias, {linhas} linhas")

        registrar_execucao(conn, inicio, fim, total_dias, total_linhas)

    print(f"\nBronze: {total_dias} dias, {total_linhas} linhas.")
    print("Transformando silver...")
    executar_transformacao_silver()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga histórica da bronze")
    parser.add_argument("--inicio", type=date.fromisoformat, default=DATA_INICIO_HISTORICO)
    parser.add_argument("--fim", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    args = parser.parse_args()
    executar_carga_historica(args.inicio, args.fim)
