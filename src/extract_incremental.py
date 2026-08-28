"""Carga incremental diária: bronze -> silver.

Janela = [min(hoje - N, último data_fim - N), hoje - 1], onde N = JANELA_SEGURANCA_DIAS.
Se rodou ontem, é D-N fixo. Se ficou dias sem rodar, a janela se alarga
sozinha para cobrir o período perdido.
"""

from datetime import date, timedelta

from config import JANELA_SEGURANCA_DIAS
from db import get_connection
from load_bronze import carregar_periodo_bronze
from load_silver import executar_transformacao_silver


def calcular_janela(conn):
    hoje = date.today()
    limite_padrao = hoje - timedelta(days=JANELA_SEGURANCA_DIAS)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT max(data_fim_janela) FROM bronze.controle_execucao
            WHERE tipo_carga IN ('incremental', 'historico');
            """
        )
        ultima_fim = cur.fetchone()[0]

    if ultima_fim is None:
        data_inicio = limite_padrao
    else:
        data_inicio = min(limite_padrao, ultima_fim - timedelta(days=JANELA_SEGURANCA_DIAS))

    return data_inicio, hoje - timedelta(days=1)


def registrar_execucao(conn, inicio, fim, qtd_dias, qtd_linhas):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.controle_execucao
                (tipo_carga, data_inicio_janela, data_fim_janela, qtd_dias, qtd_linhas)
            VALUES ('incremental', %s, %s, %s, %s);
            """,
            (inicio, fim, qtd_dias, qtd_linhas),
        )
    conn.commit()


def executar_carga_incremental():
    with get_connection() as conn:
        data_inicio, data_fim = calcular_janela(conn)
        if data_inicio > data_fim:
            print(f"Nada a extrair (janela {data_inicio}..{data_fim}).")
            return
        print(f"Janela incremental: {data_inicio} -> {data_fim}")

        resultado = carregar_periodo_bronze(conn, data_inicio, data_fim)
        qtd_dias = len(resultado)
        qtd_linhas = sum(resultado.values())
        for d, n in sorted(resultado.items()):
            print(f"  {d}: {n} linhas")

        registrar_execucao(conn, data_inicio, data_fim, qtd_dias, qtd_linhas)

    print("Transformando silver...")
    executar_transformacao_silver()


if __name__ == "__main__":
    executar_carga_incremental()
