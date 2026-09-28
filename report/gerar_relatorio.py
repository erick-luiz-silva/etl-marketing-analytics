"""
Gera os entregáveis semanais a partir das views gold do Postgres:
  - abcs_weekly_onepage_v2.html / .pdf  — relatório completo (1 página A4)
  - resumo_semana.txt                   — texto pronto para WhatsApp
  - resumo_semana.png                   — card/print para WhatsApp (1080x1350)

- Semana de referência = última segunda→domingo completa (ou --fim <domingo>).
- Compara com a semana anterior.
- Medidas espelham BI/info_medidas.csv (mesmas fórmulas, em SQL).

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
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
from db import get_connection  # noqa: E402

REPORT_DIR = _ROOT / "report"
TEMPLATE = REPORT_DIR / "template_weekly.html"
TEMPLATE_RESUMO = REPORT_DIR / "template_resumo.html"
SAIDA_PADRAO = REPORT_DIR / "abcs_weekly_onepage_v2.html"
RESUMO_TXT_PADRAO = REPORT_DIR / "resumo_semana.txt"
RESUMO_PNG_PADRAO = REPORT_DIR / "resumo_semana.png"
LOGO = REPORT_DIR / "logo_abcs_png" / "ABCS-Horizontal-1.png"

DATA_INICIO_PAINEIS = date(2026, 8, 27)  # eventos painel_acessado reais

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


def pct(num, den, casas=0):
    if not den:
        return "—"
    return f"{100 * num / den:.{casas}f}%".replace(".", ",")


def seg(v):
    return f"{v:.0f} s" if v else "—"


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


def delta_card_html(var):
    if var is None:
        return '<div class="stat-delta new">sem base de comparação</div>'
    if abs(var) < 0.03:
        return '<div class="stat-delta flat">estável vs. semana anterior</div>'
    cls, seta = ("up", "↑") if var > 0 else ("dn", "↓")
    return f'<div class="stat-delta {cls}">{seta} {abs(var) * 100:.0f}% vs. semana anterior</div>'


def construir_tldr(di_var, inst_var, negrito):
    partes = []
    if di_var is not None and abs(di_var) >= 0.10:
        partes.append(f"o Data Insights {'cresceu' if di_var > 0 else 'caiu'} "
                       f"{negrito(f'{abs(di_var) * 100:.0f}%')}")
    if inst_var is not None and abs(inst_var) >= 0.10:
        partes.append(f"o Institucional {'cresceu' if inst_var > 0 else 'caiu'} "
                       f"{negrito(f'{abs(inst_var) * 100:.0f}%')}")
    if partes:
        return "Esta semana, " + " e ".join(partes) + " frente à semana anterior."
    return "Semana estável nos dois portais — sem grandes variações frente à anterior."


# ---------- consultas ----------

def kpis_portal(cur, site, ini, fim):
    cur.execute(
        """
        SELECT COALESCE(SUM(sessoes),0), COALESCE(SUM(usuarios),0),
               COALESCE(SUM(sessoes_engajadas),0), COALESCE(SUM(tempo_engajamento_s),0)
        FROM gold.vw_site_overview
        WHERE site = %s AND event_date BETWEEN %s AND %s;
        """,
        (site, ini, fim),
    )
    ses, us, eng, tempo = cur.fetchone()
    return {
        "sessoes": ses, "usuarios": us, "engajadas": eng, "tempo_total": tempo,
        "tempo_medio": (tempo / ses) if ses else 0,
    }


def top_paises(cur, ini, fim, limite=5):
    cur.execute(
        """
        SELECT country, COALESCE(SUM(sessoes),0) FROM gold.vw_site_overview
        WHERE event_date BETWEEN %s AND %s
        GROUP BY 1 HAVING COALESCE(SUM(sessoes),0) > 0
        ORDER BY 2 DESC LIMIT %s;
        """,
        (ini, fim, limite),
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


def devices_data_insights(cur, ini, fim):
    cur.execute(
        """
        SELECT device_category, COALESCE(SUM(sessoes),0) FROM gold.vw_site_overview
        WHERE site = 'Data Insights' AND event_date BETWEEN %s AND %s
        GROUP BY 1 HAVING COALESCE(SUM(sessoes),0) > 0
        ORDER BY 2 DESC;
        """,
        (ini, fim),
    )
    return [(DEVICE_PT.get(d, d), int(v)) for d, v in cur.fetchall()]


def paineis_semana(cur, ini, fim):
    cur.execute(
        """
        SELECT painel, tema, SUM(acessos), SUM(sessoes_engajadas), SUM(sessoes)
        FROM gold.vw_paineis_ranking
        WHERE event_date BETWEEN %s AND %s
        GROUP BY 1, 2
        ORDER BY 3 DESC, SUM(sessoes_engajadas) DESC, 1 ASC;
        """,
        (ini, fim),
    )
    return [
        {"painel": p, "tema": t, "acessos": int(a),
         "engajadas": int(e), "sessoes": int(s)}
        for p, t, a, e, s in cur.fetchall()
    ]


def qualidade(cur, ini, fim):
    cur.execute(
        """
        SELECT COALESCE(SUM(sessoes_validas),0), COALESCE(SUM(sessoes_descartadas),0)
        FROM gold.vw_qualidade_trafego WHERE event_date BETWEEN %s AND %s;
        """,
        (ini, fim),
    )
    return cur.fetchone()


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


def painel_rows(paineis, limite=6):
    if not paineis:
        return '<tr><td colspan="3" style="color:#9aa39d">sem acessos de painel na semana</td></tr>'
    out = []
    for p in paineis[:limite]:
        taxa = (p["engajadas"] / p["sessoes"]) if p["sessoes"] else 0
        cor = "#1b5e20" if taxa >= 0.6 else ("#f57c00" if taxa >= 0.3 else "#c62828")
        out.append(
            f'<tr><td>{p["painel"]}</td><td>{p["acessos"]}</td>'
            f'<td><span class="pct-bar"><span class="pct-fill" '
            f'style="width:{taxa * 100:.0f}%;background:{cor}"></span></span>'
            f'{taxa * 100:.0f}%</td></tr>'
        )
    return "".join(out)


def notice_html(ini, fim):
    if ini <= DATA_INICIO_PAINEIS <= fim or fim < DATA_INICIO_PAINEIS + timedelta(days=21):
        return (
            '<div class="notice-bar"><div class="notice-icon">ℹ</div>'
            '<div class="notice-text"><strong>Dados de painel ainda em consolidação:</strong> '
            'o rastreamento por painel do ABCS Data Insights começou em 27/08/2026. '
            'Os números de painéis desta semana são preliminares e tendem a se '
            'estabilizar conforme o volume de acessos cresce.</div></div>'
        )
    return ""


def periodo_longo(seg_, dom):
    return (f"{DIAS_SEM[0].capitalize()}, {seg_.day} de {MESES[seg_.month]} a "
            f"domingo, {dom.day} de {MESES[dom.month]} de {dom.year}")


def logo_data_uri():
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()


# ---------- navegador headless (PDF + PNG) ----------

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


def gerar_png(html_path, png_path, largura, altura):
    navegador = _achar_navegador()
    if not navegador:
        print("  ! Chrome/Edge não encontrado — imagem do resumo não gerada.")
        return False
    cmd = [
        navegador, "--headless", "--disable-gpu", "--hide-scrollbars",
        f"--window-size={largura},{altura}",
        f"--screenshot={png_path}", _url_arquivo(html_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if png_path.exists() and png_path.stat().st_size > 2000:
        print(f"Gerado: {png_path}  ({png_path.stat().st_size // 1024} KB) — via {Path(navegador).name}")
        return True
    print(f"  ! Falha ao gerar imagem (rc={r.returncode}). {r.stderr[-300:]}")
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


def coletar_dados(fim_arg):
    seg_, dom = semana_referencia(fim_arg)
    seg_ant, dom_ant = seg_ - timedelta(days=7), dom - timedelta(days=7)
    print(f"Semana de referência : {seg_} a {dom}")
    print(f"Semana de comparação : {seg_ant} a {dom_ant}")

    with get_connection() as conn, conn.cursor() as cur:
        di = kpis_portal(cur, "Data Insights", seg_, dom)
        di_ant = kpis_portal(cur, "Data Insights", seg_ant, dom_ant)
        inst = kpis_portal(cur, "Institucional", seg_, dom)
        inst_ant = kpis_portal(cur, "Institucional", seg_ant, dom_ant)
        paises = top_paises(cur, seg_, dom)
        estados = top_estados(cur, seg_, dom)
        devices = devices_data_insights(cur, seg_, dom)
        paineis = paineis_semana(cur, seg_, dom)
        val, desc = qualidade(cur, seg_, dom)

    bruto = (val or 0) + (desc or 0)
    tema_tot = sum(p["acessos"] for p in paineis) or 1
    temas = {}
    for p in paineis:
        temas[p["tema"]] = temas.get(p["tema"], 0) + p["acessos"]
    tema_top, tema_top_ac = max(temas.items(), key=lambda x: x[1]) if temas else ("—", 0)

    return {
        "seg": seg_, "dom": dom, "seg_ant": seg_ant, "dom_ant": dom_ant,
        "di": di, "di_ant": di_ant, "inst": inst, "inst_ant": inst_ant,
        "di_var": variacao(di["sessoes"], di_ant["sessoes"]),
        "inst_var": variacao(inst["sessoes"], inst_ant["sessoes"]),
        "paises": paises, "estados": estados, "devices": devices,
        "paineis": paineis, "val": val, "desc": desc, "bruto": bruto,
        "tema_top": tema_top, "tema_top_ac": tema_top_ac, "tema_tot": tema_tot,
    }


# ---------- geração: relatório completo ----------

def gerar_html(d, saida):
    seg_, dom = d["seg"], d["dom"]
    di, inst = d["di"], d["inst"]
    paineis, desc, bruto = d["paineis"], d["desc"], d["bruto"]
    nomes_top = ", ".join(p["painel"] for p in paineis[:3])
    di_taxa = pct(di["engajadas"], di["sessoes"])

    subs = {
        "{{LOGO_DATA_URI}}": logo_data_uri(),
        "{{PERIODO_LONGO}}": periodo_longo(seg_, dom),
        "{{PROX_RELATORIO}}": f"{(dom + timedelta(days=7)):%d/%m/%Y}",
        "{{NOTICE}}": notice_html(seg_, dom),

        "{{DI_ACESSOS}}": n(di["sessoes"]),
        "{{DI_ENGAJ_PCT}}": di_taxa,
        "{{DI_USUARIOS}}": n(di["usuarios"]),
        "{{DI_TEMPO}}": seg(di["tempo_medio"]),
        "{{DI_DELTA}}": delta_html(d["di_var"]),

        "{{INST_ACESSOS}}": n(inst["sessoes"]),
        "{{INST_ENGAJ_PCT}}": pct(inst["engajadas"], inst["sessoes"]),
        "{{INST_USUARIOS}}": n(inst["usuarios"]),
        "{{INST_TEMPO}}": seg(inst["tempo_medio"]),
        "{{INST_DELTA}}": delta_html(d["inst_var"]),

        "{{PAISES_ROWS}}": rank_rows(d["paises"]),
        "{{ESTADOS_ROWS}}": rank_rows(d["estados"]),
        "{{DEVICE_ROWS}}": device_rows(d["devices"]),

        "{{QT_VALIDAS}}": n(d["val"]),
        "{{QT_BOTS}}": n(desc),
        "{{QT_BOT_PCT}}": pct(desc, bruto, 1),
        "{{QT_REAL_PCT}}": pct(d["val"], bruto, 1),
        "{{QT_REAL_PCT_W}}": f"{max(1, round(100 * (d['val'] or 0) / (bruto or 1)))}",

        "{{TEMA_TOP}}": d["tema_top"],
        "{{TEMA_PCT}}": pct(d["tema_top_ac"], d["tema_tot"]),
        "{{TEMA_DESC}}": (f"{nomes_top} foram os painéis mais consultados da semana."
                          if nomes_top else "Sem acessos de painel registrados na semana."),
        "{{PAINEIS_ROWS}}": painel_rows(paineis),

        "{{HIGHLIGHT_PCT}}": di_taxa,
        "{{HIGHLIGHT_SUB}}": (
            f"De {n(di['sessoes'])} sessões no ABCS Data Insights, "
            f"{n(di['engajadas'])} foram engajadas — o público que chega à "
            f"plataforma explora os dados do setor em vez de sair na hora."
        ),

        "{{FONTE_NOTA}}": (
            f"Período: {seg_:%d/%m} a {dom:%d/%m/%Y} · "
            f"Bots excluídos ({pct(desc, bruto, 1)} do tráfego bruto da semana) · "
            f"Fonte: GA4 via pipeline ABCS Analytics"
        ),
    }

    html = TEMPLATE.read_text(encoding="utf-8")
    for k, v in subs.items():
        html = html.replace(k, v)
    saida.write_text(html, encoding="utf-8")
    print(f"\nGerado: {saida}")
    print(f"  Data Insights : {n(di['sessoes'])} sessões ({di_taxa} engajadas)")
    print(f"  Institucional : {n(inst['sessoes'])} sessões")
    print(f"  Bots na semana: {pct(desc, bruto, 1)}")
    print(f"  Painéis       : {len(paineis)} com acesso, {d['tema_tot']} acessos totais")
    return saida


# ---------- geração: resumo para WhatsApp (texto) ----------

def gerar_texto_resumo(d, saida_txt):
    seg_, dom = d["seg"], d["dom"]
    di, inst, paineis = d["di"], d["inst"], d["paineis"]

    linhas = [
        f"📊 *Resumo Semanal — Portal ABCS*",
        f"{seg_:%d/%m} a {dom:%d/%m/%Y}",
        "",
        construir_tldr(d["di_var"], d["inst_var"], negrito=lambda s: f"*{s}*"),
        "",
        f"🔹 *ABCS Data Insights*: {n(di['sessoes'])} sessões reais "
        f"({frase_delta(d['di_var'])}), {pct(di['engajadas'], di['sessoes'])} engajadas.",
    ]
    if paineis:
        linhas.append("   Top 3 painéis da semana:")
        for i, p in enumerate(paineis[:3], 1):
            linhas.append(f"   {i}. *{p['painel']}* — {p['acessos']} acessos")
    else:
        linhas.append("   Sem acessos de painel registrados (rastreamento ainda recente).")

    linhas += [
        "",
        f"🔹 *Site Institucional*: {n(inst['sessoes'])} sessões reais "
        f"({frase_delta(d['inst_var'])}), {pct(inst['engajadas'], inst['sessoes'])} engajadas.",
        "",
        f"🤖 *{pct(d['desc'], d['bruto'], 1)}* do tráfego bruto da semana era robô e foi "
        f"removido automaticamente antes dessas contagens.",
        "",
        "📎 Relatório completo em PDF em anexo.",
    ]

    saida_txt.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Gerado: {saida_txt}")
    return saida_txt


# ---------- geração: resumo para WhatsApp (imagem) ----------

def paineis_top3_html(paineis):
    if not paineis:
        return ('<div class="panel-row"><span class="panel-name" style="color:#8a948e">'
                'Sem acessos de painel na semana</span></div>')
    out = []
    for i, p in enumerate(paineis[:3], 1):
        out.append(
            f'<div class="panel-row"><span class="panel-num">{i}</span>'
            f'<span class="panel-name">{p["painel"]}</span>'
            f'<span class="panel-val">{n(p["acessos"])}</span></div>'
        )
    return "".join(out)


def gerar_imagem_resumo(d, saida_png, largura=1080, altura=1040):
    di, inst = d["di"], d["inst"]

    subs = {
        "{{LOGO_DATA_URI}}": logo_data_uri(),
        "{{PERIODO_LONGO}}": periodo_longo(d["seg"], d["dom"]),
        "{{TLDR}}": construir_tldr(d["di_var"], d["inst_var"], negrito=lambda s: f"<b>{s}</b>"),

        "{{DI_ACESSOS}}": n(di["sessoes"]),
        "{{DI_ENGAJ_PCT}}": pct(di["engajadas"], di["sessoes"]),
        "{{DI_DELTA}}": delta_card_html(d["di_var"]),

        "{{INST_ACESSOS}}": n(inst["sessoes"]),
        "{{INST_ENGAJ_PCT}}": pct(inst["engajadas"], inst["sessoes"]),
        "{{INST_DELTA}}": delta_card_html(d["inst_var"]),

        "{{PAINEIS_TOP3}}": paineis_top3_html(d["paineis"]),
        "{{BOT_PCT}}": pct(d["desc"], d["bruto"], 1),
    }

    html = TEMPLATE_RESUMO.read_text(encoding="utf-8")
    for k, v in subs.items():
        html = html.replace(k, v)

    html_tmp = saida_png.with_suffix(".tmp.html")
    html_tmp.write_text(html, encoding="utf-8")
    try:
        ok = gerar_png(html_tmp, saida_png, largura, altura)
    finally:
        html_tmp.unlink(missing_ok=True)
    return saida_png if ok else None


# ---------- main ----------

def gerar(fim_arg, saida):
    """Compatibilidade: coleta os dados e gera só o HTML do relatório completo."""
    d = coletar_dados(fim_arg)
    return gerar_html(d, saida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Entregáveis semanais ABCS (relatório + resumo WhatsApp)")
    ap.add_argument("--fim", type=date.fromisoformat, default=None,
                    help="domingo de referência (ISO). Padrão: último domingo fechado")
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO, help="HTML do relatório completo")
    ap.add_argument("--resumo-txt", type=Path, default=RESUMO_TXT_PADRAO)
    ap.add_argument("--resumo-png", type=Path, default=RESUMO_PNG_PADRAO)
    ap.add_argument("--no-pdf", action="store_true", help="não gerar o PDF do relatório")
    ap.add_argument("--no-resumo", action="store_true", help="não gerar o resumo (txt + png) para WhatsApp")
    args = ap.parse_args()

    dados = coletar_dados(args.fim)

    html_path = gerar_html(dados, args.saida)
    if not args.no_pdf:
        gerar_pdf(html_path, html_path.with_suffix(".pdf"))

    if not args.no_resumo:
        gerar_texto_resumo(dados, args.resumo_txt)
        gerar_imagem_resumo(dados, args.resumo_png)
