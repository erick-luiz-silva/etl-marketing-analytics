"""Carga incremental diária: bronze (site + painel) -> silver.

Janela = [min(hoje - N, último data_fim - N), hoje - 1], N = JANELA_SEGURANCA_DIAS.
Se rodou ontem, é D-N fixo. Se ficou dias sem rodar, a janela se alarga sozinha.
Cada relatório tem seu próprio controle de janela.
"""

from datetime import date, timedelta

from config import DATA_INICIO_PAINEIS, JANELA_SEGURANCA_DIAS
from db import get_connection
from ga4_client import extrair_paineis, extrair_site
from load_bronze import gravar_snapshot_diario
from load_silver import executar_transformacao_silver


def calcular_janela(conn, relatorio, piso):
    hoje = date.today()
    limite_padrao = hoje - timedelta(days=JANELA_SEGURANCA_DIAS)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT max(data_fim_janela) FROM bronze.controle_execucao WHERE relatorio = %s;",
            (relatorio,),
        )
        ultima_fim = cur.fetchone()[0]

    if ultima_fim is None:
        data_inicio = max(piso, limite_padrao)
    else:
        data_inicio = min(limite_padrao, ultima_fim - timedelta(days=JANELA_SEGURANCA_DIAS))
    return data_inicio, hoje - timedelta(days=1)


def registrar_execucao(conn, relatorio, inicio, fim, qtd_dias, qtd_linhas):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.controle_execucao
                (relatorio, tipo_carga, data_inicio_janela, data_fim_janela, qtd_dias, qtd_linhas)
            VALUES (%s, 'incremental', %s, %s, %s, %s);
            """,
            (relatorio, inicio, fim, qtd_dias, qtd_linhas),
        )
    conn.commit()


def _incremental(relatorio, extrator, piso):
    with get_connection() as conn:
        data_inicio, data_fim = calcular_janela(conn, relatorio, piso)
        if data_inicio > data_fim:
            print(f"Report '{relatorio}': nada a extrair ({data_inicio}..{data_fim}).")
            return
        print(f"Report '{relatorio}': {data_inicio} -> {data_fim}")
        registros = extrator(data_inicio, data_fim)
        resultado = gravar_snapshot_diario(conn, relatorio, registros)
        for d, n in sorted(resultado.items()):
            print(f"  {d}: {n} linhas")
        registrar_execucao(
            conn, relatorio, data_inicio, data_fim, len(resultado), sum(resultado.values())
        )


def executar_carga_incremental():
    # piso do site: 3 anos atrás basta como fallback quando a tabela está vazia
    _incremental("site", extrair_site, date.today() - timedelta(days=1095))
    _incremental("painel", extrair_paineis, DATA_INICIO_PAINEIS)
    print("\nTransformando silver...")
    executar_transformacao_silver()


if __name__ == "__main__":
    executar_carga_incremental()
