"""
Gera os entregáveis semanais a partir das views gold do Postgres:
  - abcs_weekly_onepage_v2.html / .pdf  — relatório completo (1 página A4)
  - resumo_semana.txt                   — texto pronto para WhatsApp

- Semana de referência = última segunda→domingo completa (ou --fim <domingo>).
- Compara com a semana anterior.
- Foco em usuários e médias: WAU (usuários únicos seg–dom), DAU médio, MAU
  (28 dias móveis), sessões por dia, visitas por usuário e tempo por sessão.
  Tráfego robótico já vem descontado nas views gold e não aparece no relatório.
- Recusa gerar se a semana ainda não está completa na base (ver
  verificar_completude); --forcar ignora a checagem.

Uso:
    python report/gerar_relatorio.py                 # última semana fechada
    python report/gerar_relatorio.py --fim 2026-08-31
    python report/gerar_relatorio.py --no-pdf --no-resumo
"""

import argparse
import base64
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
from db import get_connection  # noqa: E402

REPORT_DIR = _ROOT / "report"
TEMPLATE = REPORT_DIR / "template_weekly.html"
SAIDA_PADRAO = REPORT_DIR / "abcs_weekly_onepage_v2.html"
RESUMO_TXT_PADRAO = REPORT_DIR / "resumo_semana.txt"
LOGO = REPORT_DIR / "logo_abcs_png" / "ABCS-Horizontal-1.png"

# A GA4 só fecha o dia D por volta do meio-dia de D+1 (testes/ACHADOS.md, teste 6):
# o domingo só conta como completo se foi extraído depois disso.
HORA_DIA_FECHADO = time(12, 0)

MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS_SEM = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

PAISES_PT = {
    "Brazil": "Brasil", "United States": "Estados Unidos", "China": "China",
    "Japan": "Japão", "Colombia": "Colômbia", "United Kingdom": "Reino Unido",
    "Netherlands": "Holanda", "Argentina": "Argentina", "Portugal": "Portugal",
    "Germany": "Alemanha", "Spain": "Espanha", "France": "França", "Mexico": "México",
    "Chile": "Chile", "Canada": "Canadá", "Italy": "Itália", "Bolivia": "Bolívia",
    "Paraguay": "Paraguai", "Peru": "Peru", "Uruguay": "Uruguai", "Ireland": "Irlanda",
    "Vietnam": "Vietnã", "India": "Índia", "Australia": "Austrália", "Belgium": "Bélgica",
    "Switzerland": "Suíça", "Sweden": "Suécia", "Denmark": "Dinamarca", "Austria": "Áustria",
    "(not set)": "Não identificado",
}
ESTADOS_PT = {
    "Sao Paulo": "São Paulo", "Federal District": "Distrito Federal", "Parana": "Paraná",
    "Goias": "Goiás", "Ceara": "Ceará", "Espirito Santo": "Espírito Santo",
    "Maranhao": "Maranhão", "Piaui": "Piauí", "Amapa": "Amapá", "Para": "Pará",
    "Rondonia": "Rondônia", "Amazonas": "Amazonas",
}
DEVICE_PT = {"desktop": "Computador", "mobile": "Celular", "tablet": "Tablet",
             "smart tv": "Smart TV", "(not set)": "Outro"}


# ---------- helpers de formatação ----------

def n(v):
    return f"{int(round(v or 0)):,}".replace(",", ".")


def dec(v, casas=1):
    return f"{v or 0:.{casas}f}".replace(".", ",")


def pct(num, den, casas=0):
    if not den:
        return "—"
    return f"{100 * num / den:.{casas}f}%".replace(".", ",")


def tempo(segundos):
    if not segundos:
        return "—"
    m, s = divmod(int(round(segundos)), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def pais_pt(x):
    return PAISES_PT.get(x, x)


def estado_pt(x):
    x = (x or "").removeprefix("State of ").strip()
    return ESTADOS_PT.get(x, x or "Não identificado")


def variacao(atual, anterior):
    if not anterior:
        return None
    return (atual - anterior) / anterior


def frase_delta(var):
    if var is None:
        return "sem semana anterior para comparar"
    if abs(var) < 0.03:
        return "estável vs. semana anterior"
    return f"{'cresceu' if var > 0 else 'caiu'} {abs(var) * 100:.0f}% vs. semana anterior"


def delta_html(var):
    if var is None:
        return '<div class="delta new">sem base de comparação</div>'
    if abs(var) < 0.005:
        return '<div class="delta flat">estável vs semana ant.</div>'
    cls, seta = ("up", "↑") if var > 0 else ("dn", "↓")
    return f'<div class="delta {cls}">{seta} {abs(var) * 100:.0f}% vs semana ant.</div>'


def construir_tldr(di_var, inst_var, negrito):
    partes = []
    if di_var is not None and abs(di_var) >= 0.10:
        partes.append(f"o Data Insights {'ganhou' if di_var > 0 else 'perdeu'} "
                      f"{negrito(f'{abs(di_var) * 100:.0f}%')} de usuários")
    if inst_var is not None and abs(inst_var) >= 0.10:
        partes.append(f"o Institucional {'ganhou' if inst_var > 0 else 'perdeu'} "
                      f"{negrito(f'{abs(inst_var) * 100:.0f}%')} de usuários")
    if partes:
        return "Esta semana, " + " e ".join(partes) + " frente à semana anterior."
    return "Semana estável nos dois portais — sem grandes variações de público frente à anterior."


# ---------- consultas ----------

def verificar_completude(cur, dom):
    """Lista o que falta para a semana terminada em `dom` estar completa na base."""
    limite = datetime.combine(dom + timedelta(days=1), HORA_DIA_FECHADO)
    problemas = []
    for rotulo, tabela in (("uso do site", "silver.ga4_eventos"),
                           ("usuários ativos", "silver.ga4_usuarios")):
        cur.execute(f"SELECT max(event_date) FROM {tabela};")
        ultima = cur.fetchone()[0]
        if ultima is None or ultima < dom:
            problemas.append(f"{rotulo}: dados só até {ultima or '—'} (precisa de {dom})")
            continue
        cur.execute(f"SELECT max(data_extracao) FROM {tabela} WHERE event_date = %s;", (dom,))
        extraido = cur.fetchone()[0]
        if extraido is None or extraido < limite:
            problemas.append(f"{rotulo}: {dom} extraído em {extraido:%d/%m %H:%M}, antes de "
                             f"{limite:%d/%m %H:%M} — dia possivelmente incompleto na GA4")
    return problemas


def kpis_portal(cur, site, ini, fim):
    # Tudo de gold.vw_usuarios_ativos, no mesmo recorte de bot: sessões/tempo da
    # semana vêm das colunas *_7d do domingo, que usam a mesma regra do wau.
    cur.execute(
        """
        SELECT event_date, COALESCE(SUM(dau),0), COALESCE(SUM(wau),0), COALESCE(SUM(mau),0),
               COALESCE(SUM(sessoes_7d),0), COALESCE(SUM(sessoes_engajadas_7d),0),
               COALESCE(SUM(tempo_engajamento_7d_s),0)
        FROM gold.vw_usuarios_ativos
        WHERE site = %s AND event_date BETWEEN %s AND %s
        GROUP BY 1;
        """,
        (site, ini, fim),
    )
    por_dia = {r[0]: [float(x) for x in r[1:]] for r in cur.fetchall()}
    dias = (fim - ini).days + 1
    _, wau, mau, ses, eng, tempo_total = por_dia.get(fim, [0] * 6)  # janelas móveis: vale o último dia
    dau_dia = [por_dia.get(ini + timedelta(days=i), [0] * 6)[0] for i in range(dias)]
    return {
        "sessoes": ses, "engajadas": eng,
        "sessoes_dia": ses / dias,
        "tempo_sessao": (tempo_total / ses) if ses else 0,
        "wau": wau, "mau": mau,
        "dau_dia": dau_dia,
        "dau_medio": sum(dau_dia) / dias,
        "visitas_usuario": (ses / wau) if wau else 0,
    }


def top_paises(cur, dom, limite=5):
    cur.execute(
        """
        SELECT country, SUM(wau) FROM gold.vw_usuarios_ativos
        WHERE event_date = %s
        GROUP BY 1 HAVING COALESCE(SUM(wau),0) > 0
        ORDER BY 2 DESC LIMIT %s;
        """,
        (dom, limite),
    )
    return [(pais_pt(c), int(v)) for c, v in cur.fetchall()]


def top_estados(cur, ini, fim, limite=5):
    cur.execute(
        """
        SELECT region, COALESCE(SUM(sessoes),0) FROM gold.vw_site_overview
        WHERE country = 'Brazil' AND event_date BETWEEN %s AND %s
          AND region <> '(not set)'
        GROUP BY 1 HAVING COALESCE(SUM(sessoes),0) > 0
        ORDER BY 2 DESC LIMIT %s;
        """,
        (ini, fim, limite),
    )
    return [(estado_pt(c), int(v)) for c, v in cur.fetchall()]


def devices_data_insights(cur, dom):
    cur.execute(
        """
        SELECT device_category, SUM(wau) FROM gold.vw_usuarios_ativos
        WHERE site = 'Data Insights' AND event_date = %s
        GROUP BY 1 HAVING COALESCE(SUM(wau),0) > 0
        ORDER BY 2 DESC;
        """,
        (dom,),
    )
    return [(DEVICE_PT.get(d, d), int(v)) for d, v in cur.fetchall()]


def paineis_semana(cur, ini, fim):
    # Aberturas pela URL do painel (gold.vw_paineis_acessos), não pelo evento de
    # clique do GTM — que ficou quebrado de ~19/09 a 05/10 (testes/ACHADOS.md, teste 9).
    # acessos = pessoa × painel × dia (soma da semana); pessoas = únicas na semana
    # (pessoas_7d do domingo, mesma lógica do WAU).
    cur.execute(
        """
        SELECT painel, tema,
               COALESCE(SUM(acessos), 0),
               COALESCE(SUM(pessoas_7d) FILTER (WHERE event_date = %s), 0)
        FROM gold.vw_paineis_acessos
        WHERE event_date BETWEEN %s AND %s AND tipo = 'painel'
        GROUP BY 1, 2
        HAVING SUM(acessos) > 0
        ORDER BY 3 DESC, 4 DESC, 1 ASC;
        """,
        (fim, ini, fim),
    )
    return [
        {"painel": p, "tema": t, "acessos": int(a), "pessoas": int(pe)}
        for p, t, a, pe in cur.fetchall()
    ]


# ---------- montagem de fragmentos (relatório completo) ----------

def rank_rows(itens):
    if not itens:
        return '<li class="rank-item"><span class="rank-num"></span>'\
               '<span class="rank-name" style="color:#9aa39d">sem dados</span>'\
               '<span class="rank-val"></span></li>'
    topo = itens[0][1] or 1
    out = []
    for i, (nome, val) in enumerate(itens, 1):
        w = max(2, round(100 * val / topo))
        out.append(
            f'<li class="rank-item"><span class="rank-num">{i}</span>'
            f'<span class="rank-name">{nome}</span>'
            f'<span class="rank-val">{n(val)}</span></li>'
            f'<div class="bar-bg"><div class="bar-fill" style="width:{w}%"></div></div>'
        )
    return "".join(out)


def device_rows(itens):
    total = sum(v for _, v in itens) or 1
    cores = ["#09814a", "#53af33", "#a9d6bd"]
    out = []
    for i, (nome, val) in enumerate(itens[:3]):
        p = 100 * val / total
        cor = cores[i] if i < len(cores) else "#cccccc"
        out.append(
            f'<div class="dev-item"><span class="dev-name">'
            f'<span class="accent-dot" style="background:{cor}"></span>{nome}</span>'
            f'<div class="dev-bar-bg"><div class="dev-bar" style="width:{p:.0f}%;background:{cor}"></div></div>'
            f'<span class="dev-pct">{p:.0f}%</span></div>'
        )
    return "".join(out) or '<div style="font-size:10px;color:#9aa39d">sem dados</div>'


def dias_rows(dau_dia):
    topo = max(dau_dia) or 1
    out = []
    for nome, v in zip(DIAS_SEM, dau_dia):
        out.append(
            f'<div class="dev-item"><span class="dev-name">{nome}</span>'
            f'<div class="dev-bar-bg"><div class="dev-bar" style="width:{100 * v / topo:.0f}%;'
            f'background:var(--verde)"></div></div>'
            f'<span class="dev-pct">{n(v)}</span></div>'
        )
    return "".join(out)


def painel_rows(paineis, limite=6):
    if not paineis:
        return '<tr><td colspan="3" style="color:#9aa39d">sem acessos de painel na semana</td></tr>'
    return "".join(
        f'<tr><td>{p["painel"]}</td><td>{n(p["acessos"])}</td><td>{n(p["pessoas"])}</td></tr>'
        for p in paineis[:limite]
    )


def periodo_longo(seg_, dom):
    return (f"{DIAS_SEM[0].capitalize()}, {seg_.day} de {MESES[seg_.month]} a "
            f"domingo, {dom.day} de {MESES[dom.month]} de {dom.year}")


def logo_data_uri():
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()


# ---------- navegador headless (PDF) ----------

def _achar_navegador():
    for nome in ("chrome", "google-chrome", "chromium", "msedge"):
        p = shutil.which(nome)
        if p:
            return p
    candidatos = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/chromium-browser",
    ]
    return next((c for c in candidatos if os.path.exists(c)), None)


def _url_arquivo(caminho):
    return "file:///" + str(caminho.resolve()).replace("\\", "/")


def gerar_pdf(html_path, pdf_path):
    navegador = _achar_navegador()
    if not navegador:
        print("  ! Chrome/Edge não encontrado — PDF não gerado. Abra o HTML e "
              "'Imprimir > Salvar como PDF' (A4 retrato).")
        return False
    cmd = [
        navegador, "--headless", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}", _url_arquivo(html_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if pdf_path.exists() and pdf_path.stat().st_size > 2000:
        print(f"Gerado: {pdf_path}  ({pdf_path.stat().st_size // 1024} KB) — via {Path(navegador).name}")
        return True
    print(f"  ! Falha ao gerar PDF (rc={r.returncode}). {r.stderr[-300:]}")
    return False


# ---------- coleta de dados ----------

def semana_referencia(fim_arg):
    if fim_arg:
        dom = fim_arg
    else:
        hoje = date.today()
        dom = hoje - timedelta(days=hoje.weekday() + 1)  # domingo anterior
    seg_ = dom - timedelta(days=6)
    return seg_, dom


def coletar_dados(fim_arg, forcar=False):
    seg_, dom = semana_referencia(fim_arg)
    seg_ant, dom_ant = seg_ - timedelta(days=7), dom - timedelta(days=7)
    print(f"Semana de referência : {seg_} a {dom}")
    print(f"Semana de comparação : {seg_ant} a {dom_ant}")

    with get_connection() as conn, conn.cursor() as cur:
        problemas = verificar_completude(cur, dom)
        if problemas:
            print("\n! Semana incompleta na base:")
            for p in problemas:
                print(f"  - {p}")
            if not forcar:
                sys.exit("Rode o pipeline (src/pipeline.py) e tente de novo, "
                         "ou use --forcar para gerar mesmo assim.")
            print("  --forcar: gerando mesmo assim.\n")
        di = kpis_portal(cur, "Data Insights", seg_, dom)
        di_ant = kpis_portal(cur, "Data Insights", seg_ant, dom_ant)
        inst = kpis_portal(cur, "Institucional", seg_, dom)
        inst_ant = kpis_portal(cur, "Institucional", seg_ant, dom_ant)
        paises = top_paises(cur, dom)
        estados = top_estados(cur, seg_, dom)
        devices = devices_data_insights(cur, dom)
        paineis = paineis_semana(cur, seg_, dom)

    tema_tot = sum(p["acessos"] for p in paineis) or 1
    temas = {}
    for p in paineis:
        temas[p["tema"]] = temas.get(p["tema"], 0) + p["acessos"]
    tema_top, tema_top_ac = max(temas.items(), key=lambda x: x[1]) if temas else ("—", 0)

    return {
        "seg": seg_, "dom": dom, "seg_ant": seg_ant, "dom_ant": dom_ant,
        "di": di, "di_ant": di_ant, "inst": inst, "inst_ant": inst_ant,
        "di_var": variacao(di["wau"], di_ant["wau"]),
        "inst_var": variacao(inst["wau"], inst_ant["wau"]),
        "paises": paises, "estados": estados, "devices": devices,
        "paineis": paineis,
        "tema_top": tema_top, "tema_top_ac": tema_top_ac, "tema_tot": tema_tot,
    }


# ---------- geração: relatório completo ----------

def _kpis_html(prefixo, k, var):
    return {
        f"{{{{{prefixo}_WAU}}}}": n(k["wau"]),
        f"{{{{{prefixo}_DELTA}}}}": delta_html(var),
        f"{{{{{prefixo}_DAU}}}}": n(k["dau_medio"]),
        f"{{{{{prefixo}_MAU}}}}": n(k["mau"]),
        f"{{{{{prefixo}_SES_DIA}}}}": n(k["sessoes_dia"]),
        f"{{{{{prefixo}_VISITAS_USU}}}}": dec(k["visitas_usuario"]),
        f"{{{{{prefixo}_TEMPO}}}}": tempo(k["tempo_sessao"]),
        f"{{{{{prefixo}_ENGAJ_PCT}}}}": pct(k["engajadas"], k["sessoes"]),
    }


def gerar_html(d, saida):
    seg_, dom = d["seg"], d["dom"]
    di, inst, paineis = d["di"], d["inst"], d["paineis"]
    nomes_top = ", ".join(p["painel"] for p in paineis[:3])
    frequencia = pct(di["dau_medio"], di["wau"])

    subs = {
        "{{LOGO_DATA_URI}}": logo_data_uri(),
        "{{PERIODO_LONGO}}": periodo_longo(seg_, dom),
        "{{PROX_RELATORIO}}": f"{(dom + timedelta(days=8)):%d/%m/%Y}",
        **_kpis_html("DI", di, d["di_var"]),
        **_kpis_html("INST", inst, d["inst_var"]),

        "{{PAISES_ROWS}}": rank_rows(d["paises"]),
        "{{ESTADOS_ROWS}}": rank_rows(d["estados"]),
        "{{DEVICE_ROWS}}": device_rows(d["devices"]),
        "{{DIAS_ROWS}}": dias_rows(di["dau_dia"]),

        "{{TEMA_TOP}}": d["tema_top"],
        "{{TEMA_PCT}}": pct(d["tema_top_ac"], d["tema_tot"]),
        "{{TEMA_DESC}}": (f"{nomes_top} foram os painéis mais consultados da semana."
                          if nomes_top else "Sem acessos de painel registrados na semana."),
        "{{PAINEIS_ROWS}}": painel_rows(paineis),

        "{{HIGHLIGHT_VAL}}": dec(di["visitas_usuario"]),
        "{{HIGHLIGHT_SUB}}": (
            f"Os {n(di['wau'])} usuários do ABCS Data Insights fizeram {n(di['sessoes'])} "
            f"visitas na semana. Em média, {n(di['dau_medio'])} pessoas acessaram por dia "
            f"({frequencia} do público da semana)."
        ),

        "{{FONTE_NOTA}}": (
            f"Período: {seg_:%d/%m} a {dom:%d/%m/%Y} · Usuários no mês = últimos 28 dias até "
            f"{dom:%d/%m} · Fonte: GA4 via pipeline ABCS Analytics"
        ),
    }

    html = TEMPLATE.read_text(encoding="utf-8")
    for k, v in subs.items():
        html = html.replace(k, v)
    saida.write_text(html, encoding="utf-8")
    print(f"\nGerado: {saida}")
    for nome, k in (("Data Insights", di), ("Institucional", inst)):
        print(f"  {nome:14}: {n(k['wau'])} usuários na semana, {n(k['dau_medio'])}/dia, "
              f"{n(k['mau'])} em 28 dias, {n(k['sessoes'])} sessões")
    print(f"  Painéis       : {len(paineis)} com acesso, {n(d['tema_tot'])} acessos totais")
    return saida


# ---------- geração: resumo para WhatsApp (texto) ----------

def _bloco_portal(nome, k, var):
    return [
        f"🔹 *{nome}*",
        f"   • *{n(k['wau'])}* usuários na semana ({frase_delta(var)})",
        f"   • *{n(k['dau_medio'])}* usuários por dia, em média",
        f"   • *{n(k['mau'])}* usuários nos últimos 28 dias",
        f"   • {n(k['sessoes_dia'])} visitas por dia · {dec(k['visitas_usuario'])} visitas "
        f"por usuário · {tempo(k['tempo_sessao'])} por visita",
    ]


def gerar_texto_resumo(d, saida_txt):
    seg_, dom = d["seg"], d["dom"]
    paineis = d["paineis"]

    linhas = [
        "📊 *Resumo Semanal — Portal ABCS*",
        f"{seg_:%d/%m} a {dom:%d/%m/%Y}",
        "",
        construir_tldr(d["di_var"], d["inst_var"], negrito=lambda s: f"*{s}*"),
        "",
        *_bloco_portal("ABCS Data Insights", d["di"], d["di_var"]),
    ]
    if paineis:
        linhas.append("   Top 3 painéis da semana:")
        for i, p in enumerate(paineis[:3], 1):
            linhas.append(f"   {i}. *{p['painel']}* — {p['acessos']} acessos "
                          f"({p['pessoas']} pessoas)")
    else:
        linhas.append("   Sem acessos de painel registrados na semana.")

    linhas += [
        "",
        *_bloco_portal("Site Institucional", d["inst"], d["inst_var"]),
        "",
        "📎 Relatório completo em PDF em anexo.",
    ]

    saida_txt.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Gerado: {saida_txt}")
    return saida_txt


# ---------- main ----------

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Entregáveis semanais ABCS (relatório + resumo WhatsApp)")
    ap.add_argument("--fim", type=date.fromisoformat, default=None,
                    help="domingo de referência (ISO). Padrão: último domingo fechado")
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO, help="HTML do relatório completo")
    ap.add_argument("--resumo-txt", type=Path, default=RESUMO_TXT_PADRAO)
    ap.add_argument("--no-pdf", action="store_true", help="não gerar o PDF do relatório")
    ap.add_argument("--no-resumo", action="store_true", help="não gerar o texto para WhatsApp")
    ap.add_argument("--forcar", action="store_true",
                    help="gera mesmo com a semana incompleta na base")
    args = ap.parse_args()

    dados = coletar_dados(args.fim, args.forcar)

    html_path = gerar_html(dados, args.saida)
    if not args.no_pdf:
        gerar_pdf(html_path, html_path.with_suffix(".pdf"))

    if not args.no_resumo:
        gerar_texto_resumo(dados, args.resumo_txt)
