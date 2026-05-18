from __future__ import annotations

import base64
import html
import json
import re
from urllib.parse import quote
from pathlib import Path

import plotly

from religiao_politica.config import FIGURES_DIR, PRESENTATION_DIR, PROJECT_ROOT


THEME = {
    "cosmos": "#3c3c47",
    "rose": "#f04e63",
    "sand": "#e6d2c9",
    "paper": "#fbf7f4",
    "line": "#d9c4bd",
}

LOGO_PATH = Path(r"c:\Users\wagbr\OneDrive\Documentos\APCE\Verta\logo 1.jpeg")
ASSETS_DIR = FIGURES_DIR / "presentation_assets"
DATA_ASSETS_DIR = PROJECT_ROOT / "outputs" / "presentation_assets"


def plotly_bundle() -> str:
    package_dir = Path(plotly.__file__).parent
    candidates = [
        package_dir / "package_data" / "plotly.min.js",
        package_dir / "package_data" / "plotly.js",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    for candidate in package_dir.rglob("plotly.min.js"):
        return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError("Bundle local do Plotly não encontrado no ambiente Python.")


def read_text_asset(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo visual não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def iframe_srcdoc(path: Path, title: str) -> str:
    content = read_text_asset(path)
    escaped = html.escape(content, quote=True)
    return f'<iframe class="visual-frame" title="{html.escape(title)}" srcdoc="{escaped}"></iframe>'


def read_json_asset(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


COMPARISON_LABELS = {
    "cristaos_vs_nao_cristaos": "Cristãos x não cristãos",
    "cristaos_eleitos_vs_derrotados": "Cristãos eleitos x cristãos derrotados",
    "cristaos_direita_vs_esquerda": "Cristãos de direita x cristãos de esquerda",
}

COMPARISON_GROUPS = {
    "cristaos_vs_nao_cristaos": ["Cristãos", "Não cristãos"],
    "cristaos_eleitos_vs_derrotados": ["Cristãos eleitos", "Cristãos derrotados"],
    "cristaos_direita_vs_esquerda": ["Cristãos de direita", "Cristãos de esquerda"],
}

PARTY_GROUPS = {
    "esquerda": ["PC DO B", "PCB", "PCO", "PDT", "PSB", "PSOL", "PSTU", "PT", "PV", "REDE", "SOLIDARIEDADE", "UP"],
    "centro": ["AGIR", "AVANTE", "CIDADANIA", "DC", "MDB", "MOBILIZA", "PHS", "PMDB", "PMN", "PPL", "PPS", "PROS", "PRP", "PSDC", "PT DO B", "PTC", "PTN", "SD"],
    "direita": ["DEM", "NOVO", "PATRIOTA", "PL", "PMB", "PODE", "PP", "PR", "PRB", "PRD", "PRTB", "PSC", "PSD", "PSDB", "PSL", "PTB", "REPUBLICANOS", "UNIAO"],
}

PARTY_GROUP_LABELS = {
    "esquerda": "Esquerda",
    "centro": "Centro / indefinido",
    "direita": "Direita",
}


JURISPRUDENCE_CASES = [
    {
        "tribunal": "TRE-PR",
        "classe": "Recurso Eleitoral",
        "processo": "REl 6002633720246160147",
        "local": "Foz do Iguaçu - PR",
        "data": "18/09/2024",
        "resultado": "Recurso desprovido; multa mantida em R$ 4.000,00",
        "tags": ["Templo religioso", "Distribuição interna", "Multa"],
        "texto": (
            'Propaganda eleitoral irregular por distribuição de "santinhos" em templo religioso. '
            "A prova material e testemunhal demonstrou distribuição no interior do templo, com presença da candidata no local. "
            "Tese: a distribuição de propaganda eleitoral em bem de uso comum, como templo religioso, configura ilícito eleitoral, "
            "sujeitando o responsável à multa do art. 37, § 1º, da Lei nº 9.504/97, independentemente de dolo específico."
        ),
    },
    {
        "tribunal": "TRE-SC",
        "classe": "Recurso contra decisão de juiz eleitoral",
        "processo": "RDJE 46466",
        "local": "Santa Catarina",
        "data": "01/03/2013",
        "resultado": "Recurso desprovido",
        "tags": ["Pastor", "Prévio conhecimento", "Templo"],
        "texto": (
            "Eleições 2012. Propaganda eleitoral com santinhos e adesivos em templo religioso. "
            "Infração ao art. 37, §§ 1º e 4º, da Lei nº 9.504/1997. "
            "Prévio conhecimento evidenciado pelas circunstâncias do caso: pastor e líder religioso local."
        ),
    },
    {
        "tribunal": "TRE-RJ",
        "classe": "Recurso Eleitoral",
        "processo": "REl 6000666120246190127",
        "local": "Duque de Caxias - RJ",
        "data": "28/10/2025",
        "resultado": "Majoritário provido; proporcional parcialmente provido, com multa reduzida",
        "tags": ["Templo", "Poste", "Prévio conhecimento"],
        "texto": (
            "Material gráfico guardado em sacola dentro de templo vazio não comprovou veiculação ou distribuição de propaganda no interior do templo. "
            "A fiscalização apreendeu bandeira, adesivos, revistas e 453 santinhos. "
            "Afixação de adesivos em poste de iluminação pública configurou propaganda irregular em bem de uso comum. "
            "O prévio conhecimento do candidato proporcional foi inferido das circunstâncias."
        ),
    },
    {
        "tribunal": "TRE-SP",
        "classe": "Recurso Eleitoral",
        "processo": "RE 37335",
        "local": "Campos do Jordão - SP",
        "data": "13/12/2016",
        "resultado": "Recurso desprovido; sentença mantida",
        "tags": ["Pedido de voto", "Templo", "Material impresso"],
        "texto": (
            "Eleições 2016. Propaganda eleitoral irregular. Distribuição de santinhos e carta com pedido expresso de votos "
            "dentro de templo religioso. Não observância do art. 37, caput, da Lei das Eleições. "
            "Imposição de multa de acordo com a dimensão da propaganda."
        ),
    },
    {
        "tribunal": "TRE-RJ",
        "classe": "Ação de Investigação Judicial Eleitoral",
        "processo": "AIJE 801011",
        "local": "Duque de Caxias - RJ",
        "data": "21/01/2015",
        "resultado": "Improcedência por ausência de prova de abuso/captação",
        "tags": ["Material no templo", "Prova insuficiente", "Abuso econômico"],
        "texto": (
            "Material de propaganda eleitoral foi encontrado dentro de templo religioso: placas, banners e santinhos. "
            "O tribunal registrou que não haveria ilegalidade no apoio religioso se não houvesse utilização do templo. "
            "Apesar da apreensão, a alegação de captação de votos em eventos religiosos não foi provada nos autos, levando à improcedência."
        ),
    },
    {
        "tribunal": "TRE-GO",
        "classe": "Recurso Eleitoral",
        "processo": "REC 6034827720226090000",
        "local": "Rubiataba - GO",
        "data": "13/12/2022",
        "resultado": "Recurso desprovido; multa acima do mínimo legal",
        "tags": ["Porta de igreja", "Ato instantâneo", "Multa majorada"],
        "texto": (
            "Distribuição de santinhos em porta de igreja após ato ecumênico. "
            "A proteção do art. 37 alcança interior, entrada e saída dos templos, pela facilidade de abordagem dos frequentadores. "
            "Ato instantâneo de propaganda dispensa prévia notificação. Circunstâncias relevantes autorizaram multa acima do mínimo legal."
        ),
    },
    {
        "tribunal": "TRE-MA",
        "classe": "Recurso Eleitoral",
        "processo": "REl 6002829620246100054",
        "local": "Presidente Dutra - MA",
        "data": "17/12/2024",
        "resultado": "Recurso desprovido; multa de R$ 5.000,00 mantida",
        "tags": ["Culto religioso", "Discurso", "Redes sociais"],
        "texto": (
            "Distribuição de santinhos e discurso durante culto religioso, com posterior divulgação em redes sociais. "
            "A conduta foi enquadrada na vedação do art. 37, § 4º, da Lei nº 9.504/97. "
            "A posterior remoção de publicações não afastou a infração consumada."
        ),
    },
]


def highlight_santinhos(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"(?i)santinhos?", lambda match: f"<mark>{match.group(0)}</mark>", escaped)


def jurisprudence_carousel() -> str:
    cards = []
    for index, case in enumerate(JURISPRUDENCE_CASES):
        tags = "".join(f"<span>{html.escape(tag)}</span>" for tag in case["tags"])
        cards.append(
            f"""
          <article class="case-card{' active' if index == 0 else ''}" data-case="{index}">
            <div class="case-meta">
              <strong>{html.escape(case["tribunal"])}</strong>
              <div class="case-meta-right">
                <span class="case-date">{html.escape(case["data"])}</span>
                <div class="case-inline-nav" aria-label="Navegação dos julgados">
                  <button type="button" class="case-prev" aria-label="Julgado anterior">‹</button>
                  <span class="case-counter">1 / {len(JURISPRUDENCE_CASES)}</span>
                  <button type="button" class="case-next" aria-label="Próximo julgado">›</button>
                </div>
              </div>
            </div>
            <h3>{html.escape(case["classe"])}</h3>
            <div class="case-process">{html.escape(case["processo"])} · {html.escape(case["local"])}</div>
            <div class="case-tags">{tags}</div>
            <p>{highlight_santinhos(case["texto"])}</p>
            <div class="case-result">{html.escape(case["resultado"])}</div>
          </article>"""
        )
    return f"""
        <div class="case-carousel" id="case-carousel">
          <div class="case-stage">
            {"".join(cards)}
          </div>
        </div>"""


def keyword_cloud(terms: list[str]) -> str:
    return "".join(f"<span>{html.escape(term)}</span>" for term in terms)


def party_grid() -> str:
    columns = []
    for group, parties in PARTY_GROUPS.items():
        party_items = []
        for party in parties:
            party_items.append(
                f"""
                <div class="party-chip">
                  <span class="party-logo party-logo-{group}">{html.escape(party[:3])}</span>
                  <span>{html.escape(party)}</span>
                </div>"""
            )
        columns.append(
            f"""
            <div class="party-column party-column-{group}">
              <h3>{html.escape(PARTY_GROUP_LABELS[group])}</h3>
              <div class="party-list">{"".join(party_items)}</div>
            </div>"""
        )
    return f'<div class="party-grid">{"".join(columns)}</div>'


def radios(name: str, values: list[str], chart_id: str) -> str:
    labels = []
    for index, value in enumerate(values):
        checked = " checked" if index == 0 else ""
        display = COMPARISON_LABELS.get(value, value)
        labels.append(
            f'<label><input type="radio" name="{chart_id}-{name}" value="{html.escape(value)}"{checked}> '
            f'{html.escape(display)}</label>'
        )
    return "\n".join(labels)


def chart_component(
    chart_id: str,
    records: list[dict[str, object]],
    title: str,
    subtitle: str,
    mode: str,
    fixed_metric: str | None = None,
) -> str:
    years = sorted({str(record["year"]) for record in records}, key=lambda value: (value != "Total", value))
    spheres = ["Total", "municipal", "estadual", "federal"]
    data = html.escape(json.dumps(records, ensure_ascii=False), quote=True)
    fixed = "" if fixed_metric is None else f' data-fixed-metric="{fixed_metric}"'
    return f"""
<div class="chart-dashboard" id="{chart_id}" data-mode="{mode}"{fixed} data-records="{data}">
  <div class="chart-controls">
    <h3>{html.escape(title)}</h3>
    <p>{html.escape(subtitle)}</p>
    <fieldset>
      <legend>Comparação</legend>
      {radios("comparison", list(COMPARISON_LABELS.keys()), chart_id)}
    </fieldset>
    <fieldset>
      <legend>Ano</legend>
      {radios("year", years, chart_id)}
    </fieldset>
    <fieldset>
      <legend>Esfera</legend>
      {radios("sphere", spheres, chart_id)}
    </fieldset>
  </div>
  <div class="chart-panel" id="{chart_id}-plot"></div>
</div>"""


def logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        raise FileNotFoundError(f"Logo não encontrada: {LOGO_PATH}")
    data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def justice_image_data_uri() -> str:
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 680" role="img" aria-label="Balança da Justiça">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="{THEME["sand"]}"/>
      <stop offset="1" stop-color="#fffdfb"/>
    </linearGradient>
    <linearGradient id="rose" x1="0" x2="1">
      <stop offset="0" stop-color="{THEME["rose"]}"/>
      <stop offset="1" stop-color="#c43f55"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="16" stdDeviation="18" flood-color="{THEME["cosmos"]}" flood-opacity=".18"/>
    </filter>
  </defs>
  <rect width="900" height="680" rx="34" fill="url(#bg)"/>
  <g filter="url(#shadow)" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M450 122v422" stroke="{THEME["cosmos"]}" stroke-width="26"/>
    <path d="M316 558h268" stroke="{THEME["cosmos"]}" stroke-width="30"/>
    <path d="M382 508h136" stroke="{THEME["cosmos"]}" stroke-width="24"/>
    <path d="M216 214h468" stroke="{THEME["cosmos"]}" stroke-width="22"/>
    <circle cx="450" cy="214" r="34" fill="url(#rose)" stroke="{THEME["cosmos"]}" stroke-width="12"/>
    <path d="M274 214l-94 178h188L274 214z" stroke="url(#rose)" stroke-width="18"/>
    <path d="M626 214l-94 178h188L626 214z" stroke="url(#rose)" stroke-width="18"/>
    <path d="M180 392c20 54 168 54 188 0" stroke="{THEME["cosmos"]}" stroke-width="18"/>
    <path d="M532 392c20 54 168 54 188 0" stroke="{THEME["cosmos"]}" stroke-width="18"/>
    <path d="M274 214v178M626 214v178" stroke="{THEME["cosmos"]}" stroke-width="12" opacity=".55"/>
  </g>
  <g opacity=".14" fill="{THEME["rose"]}">
    <circle cx="118" cy="110" r="18"/>
    <circle cx="782" cy="560" r="24"/>
    <circle cx="750" cy="122" r="10"/>
  </g>
</svg>"""
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def build_html() -> str:
    logo = logo_data_uri()
    justice_image = justice_image_data_uri()
    plotly_js = plotly_bundle()
    cases = jurisprudence_carousel()
    total_records = read_json_asset(DATA_ASSETS_DIR / "barras_totais_medios.json")
    expense_structure_records = read_json_asset(DATA_ASSETS_DIR / "barras_estrutura_despesas.json")
    receipt_structure_records = read_json_asset(DATA_ASSETS_DIR / "barras_estrutura_receitas.json")
    strong_keywords = keyword_cloud(["pastor(a)", "pr./pra.", "bispo(a)", "apóstolo(a)", "missionário(a)", "obreiro(a)", "presbítero", "pb.", "diácono(a)", "padre", "pe.", "frei/freira", "monsenhor", "irmão/irmã"])
    identity_keywords = keyword_cloud(["cristão/cristã", "evangélico(a)", "gospel", "católico(a)", "paróquia", "Assembleia de Deus", "igreja", "Jesus", "Deus"])
    party_grid_html = party_grid()
    map_iframe = iframe_srcdoc(
        ASSETS_DIR / "mapas_municipais" / "mapa_municipal_votos_cristaos_vs_nao_cristaos_municipal.html",
        "Mapa municipal de votos cristãos versus não cristãos",
    )
    expense_totals_chart = chart_component(
        "chart-expense-totals",
        total_records,
        "Despesas totais médias",
        "Média por candidatura no recorte selecionado.",
        "totals",
        fixed_metric="despesa_contratada",
    )
    receipt_totals_chart = chart_component(
        "chart-receipt-totals",
        total_records,
        "Receitas totais médias",
        "Média por candidatura no recorte selecionado.",
        "totals",
        fixed_metric="receita_total",
    )
    expense_structure_chart = chart_component(
        "chart-expense-structure",
        expense_structure_records,
        "Estrutura média de despesas",
        "Top 5 rubricas por volume no recorte selecionado.",
        "structure",
    )
    receipt_structure_chart = chart_component(
        "chart-receipt-structure",
        receipt_structure_records,
        "Estrutura média de arrecadação",
        "Top 5 rubricas por volume no recorte selecionado.",
        "structure",
    )

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Religião e política no Brasil</title>
  <script>
{plotly_js}
  </script>
  <style>
    :root {{
      color-scheme: light;
      --cosmos: {THEME["cosmos"]};
      --rose: {THEME["rose"]};
      --sand: {THEME["sand"]};
      --paper: {THEME["paper"]};
      --line: {THEME["line"]};
      --white: #fffdfb;
      --muted: #706875;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--cosmos);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }}
    .deck {{
      height: 100vh;
      display: grid;
      grid-template-rows: 6px 1fr 64px;
      background:
        linear-gradient(90deg, rgba(240,78,99,.05), transparent 34%, rgba(60,60,71,.05)),
      var(--paper);
    }}
    .deck.nav-hidden {{
      grid-template-rows: 6px 1fr 0px;
    }}
    .progress-track {{ background: rgba(60,60,71,.16); }}
    .progress-bar {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--rose), var(--cosmos));
      transition: width 260ms ease;
    }}
    .slides {{
      position: relative;
      overflow: hidden;
      min-height: 0;
    }}
    .slide {{
      position: absolute;
      inset: 0;
      padding: clamp(28px, 4vw, 64px);
      display: grid;
      align-content: center;
      gap: 24px;
      opacity: 0;
      visibility: hidden;
      z-index: 0;
      transform: translateX(28px);
      pointer-events: none;
      transition: opacity 260ms ease, transform 260ms ease;
      min-height: 0;
    }}
    .slide.active {{
      opacity: 1;
      visibility: visible;
      z-index: 1;
      transform: translateX(0);
      pointer-events: auto;
    }}
    .slide-law {{
      padding: 86px 64px 72px;
      align-content: start;
    }}
    .slide-cases {{
      padding: 80px 64px 72px;
      align-content: start;
    }}
    .brand-row {{
      position: absolute;
      top: 30px;
      right: clamp(28px, 4vw, 64px);
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    .brand-row img {{
      width: 48px;
      height: 48px;
      border-radius: 50%;
      object-fit: cover;
      border: 1px solid rgba(60,60,71,.18);
    }}
    .cover {{
      align-content: stretch;
      padding: clamp(44px, 6vw, 96px) clamp(46px, 6vw, 92px);
      grid-template-columns: minmax(520px, .95fr) minmax(280px, .55fr);
      align-items: center;
      column-gap: clamp(24px, 4vw, 70px);
      overflow: hidden;
      background:
        radial-gradient(circle at 62% 22%, rgba(230,210,201,.58), transparent 24%),
        radial-gradient(circle at 28% 78%, rgba(240,78,99,.08), transparent 24%),
        #fffaf7;
    }}
    .cover::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1200' height='760' viewBox='0 0 1200 760'%3E%3Cg fill='none' stroke='%23e6d2c9' stroke-opacity='.45'%3E%3Cellipse cx='690' cy='260' rx='315' ry='75' transform='rotate(-18 690 260)'/%3E%3Cellipse cx='690' cy='260' rx='260' ry='58' transform='rotate(42 690 260)'/%3E%3Cellipse cx='690' cy='260' rx='220' ry='48' transform='rotate(88 690 260)'/%3E%3Cpath d='M508 642c150-170 346-294 608-378' stroke-width='1'/%3E%3Cpath d='M560 690c142-176 334-316 594-420' stroke-width='1'/%3E%3C/g%3E%3Cg fill='%23e6d2c9' fill-opacity='.75'%3E%3Ccircle cx='586' cy='215' r='7'/%3E%3Ccircle cx='825' cy='258' r='10'/%3E%3Ccircle cx='702' cy='91' r='14'/%3E%3Ccircle cx='760' cy='381' r='5'/%3E%3C/g%3E%3C/svg%3E") center / cover no-repeat;
      pointer-events: none;
      opacity: .78;
    }}
    .cover-copy {{
      position: relative;
      z-index: 3;
      max-width: 760px;
    }}
    .cover-kicker {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 12px 24px;
      margin-bottom: 34px;
      background: linear-gradient(90deg, var(--rose), #d84658);
      color: white;
      text-transform: uppercase;
      letter-spacing: .1em;
      font-weight: 900;
      font-size: 14px;
      box-shadow: 0 12px 34px rgba(240,78,99,.22);
    }}
    .cover h1 {{
      max-width: 760px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(74px, 8vw, 132px);
      line-height: .86;
      letter-spacing: -0.01em;
      color: #171e2f;
      text-shadow: 0 8px 28px rgba(60,60,71,.12);
    }}
    .cover-rule {{
      width: 76px;
      height: 5px;
      border-radius: 999px;
      margin: 34px 0 24px;
      background: var(--rose);
    }}
    .cover-subtitle {{
      max-width: 610px;
      color: #686273;
      font-size: clamp(20px, 1.6vw, 28px);
      line-height: 1.35;
    }}
    .presenter-card {{
      display: flex;
      align-items: center;
      gap: 18px;
      margin-top: 34px;
      color: #171e2f;
    }}
    .presenter-icon {{
      width: 66px;
      height: 66px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: white;
      background: linear-gradient(135deg, var(--rose), #cc3e53);
      box-shadow: 0 14px 32px rgba(240,78,99,.24);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 34px;
      font-weight: 900;
    }}
    .presenter-name {{
      font-size: 22px;
      font-weight: 900;
    }}
    .presenter-org {{
      margin-top: 4px;
      color: #686273;
      font-size: 18px;
    }}
    .cover-medallion {{
      position: relative;
      z-index: 3;
      justify-self: center;
      align-self: start;
      margin-top: clamp(54px, 9vh, 110px);
      width: min(360px, 30vw);
      aspect-ratio: 1;
      border-radius: 50%;
      padding: 18px;
      background: rgba(255,253,251,.72);
      border: 1px solid rgba(230,210,201,.88);
      box-shadow: 0 28px 90px rgba(60,60,71,.18);
    }}
    .cover-logo {{
      width: 100%;
      height: 100%;
      border-radius: 50%;
      object-fit: cover;
      display: block;
    }}
    .cover-congress {{
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      z-index: 2;
      width: clamp(300px, 27vw, 450px);
      display: grid;
      align-content: end;
      justify-items: center;
      padding: 0 42px 94px 72px;
      color: white;
      background:
        radial-gradient(circle at 70% 24%, rgba(255,255,255,.18), transparent 2px),
        radial-gradient(circle at 50% 56%, rgba(255,255,255,.14), transparent 2px),
        linear-gradient(165deg, #151b2b, #111624 66%);
      border-top-left-radius: 58% 100%;
      border-bottom-left-radius: 38% 82%;
      box-shadow: -34px 0 0 var(--rose);
    }}
    .cover-congress::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='520' height='760' viewBox='0 0 520 760'%3E%3Cg fill='none' stroke='white' stroke-opacity='.12'%3E%3Cpath d='M45 120 C 180 38, 318 186, 470 94'/%3E%3Cpath d='M32 505 C 188 418, 302 612, 486 492'/%3E%3Cpath d='M86 270 C 190 196, 302 348, 438 268'/%3E%3C/g%3E%3Cg fill='white' fill-opacity='.32'%3E%3Ccircle cx='94' cy='258' r='5'/%3E%3Ccircle cx='302' cy='348' r='4'/%3E%3Ccircle cx='438' cy='268' r='6'/%3E%3Ccircle cx='188' cy='418' r='4'/%3E%3Ccircle cx='486' cy='492' r='5'/%3E%3C/g%3E%3C/svg%3E") center / cover no-repeat;
      pointer-events: none;
    }}
    .congress-copy {{
      position: relative;
      z-index: 1;
      text-align: center;
      font-family: Georgia, "Times New Roman", serif;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    .congress-line {{
      width: 74px;
      height: 2px;
      margin: 0 auto 22px;
      background: var(--rose);
    }}
    .congress-small {{ font-size: 18px; opacity: .9; }}
    .congress-main {{ font-size: clamp(34px, 3.2vw, 52px); margin-top: 12px; }}
    .congress-red {{ color: var(--rose); font-size: clamp(22px, 2vw, 32px); margin-top: 10px; }}
    .congress-sub {{ font-size: clamp(20px, 1.6vw, 27px); margin-top: 12px; }}
    .congress-year {{ color: var(--rose); font-size: clamp(28px, 2.5vw, 40px); margin-top: 20px; }}
    .kicker {{
      color: var(--rose);
      text-transform: uppercase;
      font-weight: 850;
      letter-spacing: .09em;
      font-size: 13px;
      margin-bottom: 12px;
    }}
    h1, h2 {{
      margin: 0;
      letter-spacing: 0;
      line-height: .98;
      color: var(--cosmos);
    }}
    h1 {{ font-size: clamp(52px, 8vw, 112px); max-width: 980px; }}
    h2 {{ font-size: clamp(38px, 5.4vw, 76px); max-width: 1040px; }}
    p {{
      margin: 0;
      color: var(--muted);
      font-size: clamp(18px, 2.1vw, 25px);
      line-height: 1.45;
      max-width: 980px;
    }}
    .content-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      max-width: 1180px;
    }}
    .note {{
      background: rgba(255,255,255,.72);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
      min-height: 170px;
    }}
    .note strong {{
      display: block;
      color: var(--cosmos);
      font-size: 20px;
      margin-bottom: 10px;
    }}
    .note span {{
      display: block;
      color: var(--muted);
      line-height: 1.42;
      font-size: 16px;
    }}
    .methodology-grid {{
      display: grid;
      grid-template-columns: minmax(320px, .9fr) minmax(420px, 1.1fr);
      gap: 22px;
      align-items: start;
      max-width: 1280px;
    }}
    .methodology-panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,.72);
      padding: 24px;
      display: grid;
      gap: 16px;
    }}
    .methodology-panel h3 {{
      margin: 0;
      color: var(--cosmos);
      font-size: 24px;
    }}
    .methodology-panel ul {{
      margin: 0;
      padding-left: 20px;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.45;
    }}
    .keyword-block {{
      display: grid;
      gap: 10px;
    }}
    .keyword-block strong {{
      color: var(--cosmos);
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    .keyword-cloud {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .keyword-cloud span {{
      border: 1px solid rgba(240,78,99,.34);
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(230,210,201,.32);
      color: var(--cosmos);
      font-size: 14px;
      font-weight: 760;
    }}
    .party-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      width: min(1320px, 100%);
    }}
    .party-column {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,.74);
      padding: 18px;
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .party-column h3 {{
      margin: 0;
      color: var(--cosmos);
      font-size: 26px;
      line-height: 1;
    }}
    .party-list {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }}
    .party-chip {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      padding: 7px 8px;
      border-radius: 8px;
      background: rgba(251,247,244,.88);
      border: 1px solid rgba(60,60,71,.11);
      color: var(--cosmos);
      font-size: 13px;
      font-weight: 820;
    }}
    .party-logo {{
      width: 34px;
      height: 34px;
      flex: 0 0 34px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      color: white;
      font-size: 10px;
      font-weight: 900;
      letter-spacing: .02em;
      box-shadow: 0 6px 16px rgba(60,60,71,.12);
    }}
    .party-logo-esquerda {{ background: #f04e63; }}
    .party-logo-centro {{ background: #8b817d; }}
    .party-logo-direita {{ background: #3c3c47; }}
    .slide-party-method {{
      align-content: start;
      gap: 14px;
      padding-top: 46px;
      padding-bottom: 24px;
    }}
    .slide-party-method h2 {{
      font-size: clamp(34px, 4.4vw, 58px);
      max-width: 1240px;
    }}
    .slide-party-method p {{
      font-size: 18px;
      max-width: 1240px;
    }}
    .slide-party-method .party-column {{
      padding: 14px;
      gap: 10px;
    }}
    .slide-party-method .party-column h3 {{
      font-size: 23px;
    }}
    .slide-party-method .party-list {{
      gap: 6px;
    }}
    .slide-party-method .party-chip {{
      padding: 5px 7px;
      font-size: 12px;
    }}
    .slide-party-method .party-logo {{
      width: 28px;
      height: 28px;
      flex-basis: 28px;
      font-size: 9px;
    }}
    .presenter {{
      margin-top: 22px;
      font-size: clamp(18px, 2vw, 24px);
      color: var(--cosmos);
      font-weight: 800;
    }}
    .visual-layout {{
      display: grid;
      grid-template-columns: minmax(260px, .72fr) minmax(520px, 1.5fr);
      gap: 18px;
      align-items: stretch;
      height: 800px;
      min-height: 800px;
    }}
    .visual-stack {{
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .visual-frame {{
      width: 100%;
      height: 800px;
      min-height: 800px;
      pointer-events: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
    }}
    .chart-dashboard {{
      width: 100%;
      height: 800px;
      min-height: 800px;
      display: grid;
      grid-template-columns: minmax(220px, 310px) minmax(0, 1fr);
      gap: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--white);
      padding: 18px;
      overflow: hidden;
    }}
    .chart-controls {{
      min-width: 0;
      overflow: auto;
      padding-right: 4px;
    }}
    .chart-controls h3 {{
      margin: 0 0 6px;
      color: var(--cosmos);
      font-size: 22px;
    }}
    .chart-controls p {{
      margin: 0 0 16px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.35;
    }}
    .chart-controls fieldset {{
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 0 0 12px;
      padding: 10px 12px;
    }}
    .chart-controls legend {{
      font-weight: 800;
      padding: 0 4px;
    }}
    .chart-controls label {{
      display: flex;
      align-items: center;
      gap: 7px;
      margin: 8px 0;
      line-height: 1.22;
      font-size: 14px;
    }}
    .chart-controls input {{ accent-color: var(--rose); }}
    .chart-panel {{
      min-width: 0;
      height: 100%;
    }}
    .split-visuals {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      height: 800px;
      min-height: 800px;
    }}
    .split-visuals .visual-frame {{
      height: 800px;
      min-height: 800px;
    }}
    .law-box {{
      max-width: 1500px;
      display: grid;
      grid-template-columns: minmax(620px, 1.45fr) minmax(280px, .55fr);
      gap: 28px;
      align-items: stretch;
    }}
    blockquote {{
      margin: 0;
      padding: 34px 38px;
      border-left: 7px solid var(--rose);
      background: var(--white);
      border-radius: 8px;
      color: var(--cosmos);
      font-size: clamp(18px, 1.45vw, 25px);
      line-height: 1.42;
      min-height: 560px;
      display: grid;
      align-content: center;
      gap: 22px;
    }}
    blockquote p {{
      margin: 0;
      max-width: none;
      color: var(--cosmos);
      font-size: inherit;
      line-height: inherit;
    }}
    .justice-visual {{
      min-height: 560px;
      display: grid;
      align-items: center;
    }}
    .justice-visual img {{
      width: 100%;
      max-height: 620px;
      object-fit: contain;
      border-radius: 18px;
      box-shadow: 0 24px 80px rgba(60,60,71,.13);
    }}
    .slide-law .law-box {{
      min-height: 0;
    }}
    .slide-law blockquote,
    .slide-law .justice-visual {{
      min-height: 500px;
    }}
    .placeholder {{
      max-width: 960px;
      border: 1px dashed rgba(60,60,71,.38);
      border-radius: 8px;
      padding: 28px;
      background: rgba(255,255,255,.55);
    }}
    .case-carousel {{
      width: min(1320px, 100%);
      height: auto;
      display: grid;
      grid-template-rows: auto;
      gap: 16px;
    }}
    .case-stage {{
      position: relative;
      min-height: 0;
    }}
    .case-card {{
      position: static;
      inset: 0;
      display: none;
      align-content: start;
      gap: 16px;
      padding: 34px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(240,78,99,.08), transparent 42%),
        var(--white);
      opacity: 0;
      transform: translateX(20px);
      pointer-events: none;
      transition: opacity 220ms ease, transform 220ms ease;
      overflow: auto;
    }}
    .case-card.active {{
      opacity: 1;
      transform: translateX(0);
      pointer-events: auto;
      display: grid;
    }}
    .case-meta {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      color: var(--rose);
      text-transform: uppercase;
      letter-spacing: .08em;
      font-size: 14px;
      font-weight: 850;
    }}
    .case-meta-right {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 14px;
      margin-left: auto;
    }}
    .case-date {{
      white-space: nowrap;
    }}
    .case-inline-nav {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      text-transform: none;
      letter-spacing: 0;
    }}
    .case-inline-nav button {{
      width: 34px;
      height: 34px;
      border-radius: 999px;
      border: 1px solid rgba(60,60,71,.24);
      background: rgba(255,253,251,.88);
      color: var(--cosmos);
      font-size: 22px;
      font-weight: 850;
      line-height: 1;
      cursor: pointer;
    }}
    .case-inline-nav button:hover:not(:disabled) {{
      border-color: var(--rose);
      color: var(--rose);
    }}
    .case-inline-nav button:disabled {{
      opacity: .36;
      cursor: default;
    }}
    .case-counter {{
      min-width: 48px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 850;
      text-align: center;
      white-space: nowrap;
    }}
    .case-card h3 {{
      margin: 0;
      color: var(--cosmos);
      font-size: clamp(28px, 3vw, 46px);
      line-height: 1.04;
    }}
    .case-process {{
      color: var(--muted);
      font-size: 18px;
      font-weight: 760;
    }}
    .case-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .case-tags span {{
      border: 1px solid rgba(240,78,99,.34);
      border-radius: 999px;
      padding: 7px 11px;
      color: var(--cosmos);
      background: rgba(230,210,201,.35);
      font-size: 13px;
      font-weight: 760;
    }}
    .case-card p {{
      max-width: none;
      color: var(--cosmos);
      font-size: clamp(19px, 1.6vw, 27px);
      line-height: 1.42;
    }}
    .case-card mark {{
      background: rgba(240,78,99,.18);
      color: var(--cosmos);
      border: 1px solid rgba(240,78,99,.36);
      border-radius: 5px;
      padding: 0 .18em;
      font-weight: 850;
    }}
    .case-result {{
      margin-top: 4px;
      border-left: 5px solid var(--rose);
      padding: 14px 16px;
      background: rgba(230,210,201,.32);
      color: var(--cosmos);
      font-size: 17px;
      font-weight: 760;
    }}
    .case-nav {{
      display: grid;
      grid-template-columns: 170px 1fr 170px;
      gap: 12px;
      align-items: center;
    }}
    .case-nav span {{
      text-align: center;
      color: var(--muted);
      font-weight: 850;
    }}
    .slide-cases .case-carousel {{
      width: 100%;
    }}
    .nav {{
      display: grid;
      grid-template-columns: 120px 1fr 120px;
      align-items: center;
      gap: 16px;
      padding: 0 clamp(20px, 4vw, 56px);
      border-top: 1px solid var(--line);
      background: rgba(251,247,244,.9);
      backdrop-filter: blur(10px);
      transition: transform 220ms ease, opacity 220ms ease;
    }}
    .deck.nav-hidden .nav {{
      transform: translateY(100%);
      opacity: 0;
      pointer-events: none;
    }}
    button {{
      appearance: none;
      border: 1px solid var(--line);
      background: var(--white);
      color: var(--cosmos);
      border-radius: 8px;
      padding: 10px 14px;
      font-weight: 800;
      cursor: pointer;
    }}
    button:hover {{ border-color: var(--rose); color: var(--rose); }}
    .status {{
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-weight: 700;
    }}
    .dots {{ display: flex; gap: 8px; }}
    .dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: rgba(60,60,71,.24);
    }}
    .dot.active {{ background: var(--rose); }}
    .nav-toggle {{
      position: fixed;
      right: 18px;
      bottom: 76px;
      z-index: 50;
      border-color: rgba(240,78,99,.45);
      box-shadow: 0 10px 30px rgba(60,60,71,.12);
    }}
    .deck.nav-hidden .nav-toggle {{
      bottom: 18px;
    }}
    @media (max-width: 980px) {{
      body {{ overflow: auto; }}
      .deck {{ min-height: 100vh; height: auto; }}
      .slides {{ min-height: calc(100vh - 70px); }}
      .slide {{ min-height: calc(100vh - 70px); position: relative; display: none; }}
      .slide.active {{ display: grid; }}
      .cover, .visual-layout, .split-visuals, .law-box {{ grid-template-columns: 1fr; }}
      .cover {{ padding: 34px 22px; }}
      .cover h1 {{ font-size: clamp(54px, 16vw, 88px); }}
      .cover-medallion {{ width: min(260px, 72vw); }}
      .cover-congress {{ position: relative; width: 100%; min-height: 280px; border-radius: 34px; box-shadow: inset 8px 0 0 var(--rose); padding: 42px 24px; }}
      .brand-row {{ position: static; justify-self: start; }}
      .visual-layout, .split-visuals {{ height: auto; max-height: none; }}
      .visual-frame, .split-visuals .visual-frame {{ height: 58vh; max-height: 58vh; min-height: 360px; }}
      .chart-dashboard {{ grid-template-columns: 1fr; height: auto; min-height: 720px; overflow: visible; }}
      .chart-panel {{ height: 460px; }}
      blockquote, .justice-visual {{ min-height: auto; }}
      .case-carousel {{ height: 720px; }}
      .case-meta, .case-meta-right {{ align-items: flex-start; flex-direction: column; }}
      .case-meta-right {{ gap: 8px; }}
      .methodology-grid, .party-grid, .party-list {{ grid-template-columns: 1fr; }}
      .content-grid {{ grid-template-columns: 1fr; }}
      .nav {{ position: sticky; bottom: 0; grid-template-columns: 90px 1fr 90px; }}
    }}
  </style>
</head>
<body>
  <main class="deck">
    <div class="progress-track"><div class="progress-bar" id="progress"></div></div>
    <div class="slides" id="slides">
      <section class="slide cover active">
        <div class="cover-copy">
          <div class="cover-kicker">APCE · estudo exploratório</div>
          <h1>Religião e política no Brasil</h1>
          <div class="cover-rule"></div>
          <p class="cover-subtitle">Candidaturas cristãs, financiamento de campanha, voto territorial e riscos jurídicos nas eleições legislativas de 2012 a 2024.</p>
          <div class="presenter-card">
            <div class="presenter-icon">§</div>
            <div>
              <div class="presenter-name">Wagner Brignol Menke</div>
              <div class="presenter-org">APCE – Associação Ateísta do Planalto Central</div>
            </div>
          </div>
        </div>
        <div class="cover-medallion">
          <img class="cover-logo" src="{logo}" alt="Logo da APCE">
        </div>
        <aside class="cover-congress" aria-label="Congresso Ateísmo no Século XXI">
          <div class="congress-copy">
            <div class="congress-line"></div>
            <div class="congress-small">Congresso</div>
            <div class="congress-main">Ateísmo</div>
            <div class="congress-red">no século XXI:</div>
            <div class="congress-sub">Filosofia e Ciência</div>
            <div class="congress-year">2026</div>
          </div>
        </aside>
      </section>

      <section class="slide">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div>
          <div class="kicker">Introdução · Objetivos</div>
          <h2>Medir presença, estrutura e risco institucional.</h2>
        </div>
        <div class="content-grid">
          <div class="note"><strong>Presença eleitoral</strong><span>Identificar a evolução de candidaturas legislativas com sinais cristãos explícitos em nome, urna, nome social ou ocupação.</span></div>
          <div class="note"><strong>Competitividade</strong><span>Comparar desempenho, despesas, receitas e estrutura de campanha entre cristãos, não cristãos, vencedores, derrotados e blocos ideológicos.</span></div>
          <div class="note"><strong>Risco jurídico</strong><span>Conectar padrões empíricos de campanha territorial, impressos e redes comunitárias a hipóteses de propaganda irregular e uso de bens de acesso público.</span></div>
        </div>
      </section>

      <section class="slide">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div>
          <div class="kicker">Metodologia · Identificação cristã</div>
          <h2>Como separamos candidatos cristãos dos demais.</h2>
        </div>
        <div class="methodology-grid">
          <div class="methodology-panel">
            <h3>Regra de classificação</h3>
            <ul>
              <li>O texto foi normalizado para reduzir diferenças de acento, caixa e grafia.</li>
              <li>A candidatura entrou como cristã quando ao menos um padrão apareceu nos campos analisados.</li>
              <li>O método registra termo encontrado, campo de origem e força do sinal: ampla, média ou forte.</li>
              <li>A leitura mede sinal público de identidade religiosa, não filiação formal a igrejas.</li>
            </ul>
          </div>
          <div class="methodology-panel">
            <h3>Campos e palavras-chave</h3>
            <div class="keyword-block">
              <strong>Campos do TSE</strong>
              <div class="keyword-cloud">
                <span>NM_CANDIDATO</span><span>NM_URNA_CANDIDATO</span><span>NM_SOCIAL_CANDIDATO</span><span>DS_OCUPACAO</span>
              </div>
            </div>
            <div class="keyword-block">
              <strong>Sinais fortes de liderança</strong>
              <div class="keyword-cloud">{strong_keywords}</div>
            </div>
            <div class="keyword-block">
              <strong>Sinais de identidade cristã</strong>
              <div class="keyword-cloud">{identity_keywords}</div>
            </div>
          </div>
        </div>
      </section>

      <section class="slide slide-party-method">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div>
          <div class="kicker">Metodologia · Blocos partidários</div>
          <h2>Como agrupamos esquerda, centro e direita.</h2>
        </div>
        <p>Os partidos dos candidatos foram classificados por uma regra heurística: siglas nos conjuntos de esquerda e direita entraram nesses polos; as demais ficaram como centro ou indefinido.</p>
        {party_grid_html}
      </section>

      <section class="slide">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div class="visual-layout">
          <div class="visual-stack">
            <div>
              <div class="kicker">Dados descritivos · Território</div>
              <h2>O voto cristão se espalha de modo desigual pelo território.</h2>
            </div>
            <p>O mapa municipal permite trocar o ano no controle de camadas. Municípios sem dados no recorte aparecem em branco, mas agora preservam identificação no tooltip.</p>
          </div>
          {map_iframe}
        </div>
      </section>

      <section class="slide">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div class="visual-layout">
          <div class="visual-stack">
            <div>
              <div class="kicker">Dados descritivos · Despesas</div>
              <h2>As despesas médias mudam conforme grupo, ano e esfera.</h2>
            </div>
            <p>Use os controles laterais para alternar comparação, ano e esfera. Os totais incluem todas as candidaturas disponíveis no recorte.</p>
          </div>
          {expense_totals_chart}
        </div>
      </section>

      <section class="slide">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div class="visual-layout">
          <div class="visual-stack">
            <div>
              <div class="kicker">Dados descritivos · Receitas</div>
              <h2>As receitas médias revelam diferenças de estrutura financeira.</h2>
            </div>
            <p>O recorte permite comparar cristãos e não cristãos, vencedores e derrotados, direita e esquerda, sempre por ano e esfera.</p>
          </div>
          {receipt_totals_chart}
        </div>
      </section>

      <section class="slide">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div class="visual-layout">
          <div class="visual-stack">
            <div>
              <div class="kicker">Ápice · Estrutura de despesas</div>
              <h2>Os gastos revelam a campanha cristã vencedora.</h2>
            </div>
            <p>Use os controles laterais do gráfico para comparar cristãos e não cristãos, vencedores e derrotados, direita e esquerda, por ano e esfera.</p>
          </div>
          {expense_structure_chart}
        </div>
      </section>

      <section class="slide">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div class="visual-layout">
          <div class="visual-stack">
            <div>
              <div class="kicker">Ápice · Estrutura de arrecadação</div>
              <h2>As receitas mostram quem sustenta a competitividade.</h2>
            </div>
            <p>O detalhe por rubrica ajuda a separar recursos partidários, recursos próprios, pessoas físicas e transferências eleitorais.</p>
          </div>
          {receipt_structure_chart}
        </div>
      </section>

      <section class="slide slide-law">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div>
          <div class="kicker">Possível infringência · Lei das Eleições, art. 37</div>
          <h2>Materiais impressos e circulação em templos exigem atenção jurídica.</h2>
        </div>
        <div class="law-box">
          <blockquote>
            <p><strong>Art. 37.</strong> Nos bens cujo uso dependa de cessão ou permissão do poder público, ou que a ele pertençam, e nos bens de uso comum, inclusive postes de iluminação pública, sinalização de tráfego, viadutos, passarelas, pontes, paradas de ônibus e outros equipamentos urbanos, é vedada a veiculação de propaganda de qualquer natureza, inclusive pichação, inscrição a tinta e exposição de placas, estandartes, faixas, cavaletes, bonecos e assemelhados.</p>
            <p><strong>§ 4º</strong> Bens de uso comum, para fins eleitorais, são os assim definidos pela Lei nº 10.406, de 10 de janeiro de 2002 - Código Civil e também aqueles a que a população em geral tem acesso, tais como cinemas, clubes, lojas, centros comerciais, <strong>templos</strong>, ginásios, estádios, ainda que de propriedade privada.</p>
          </blockquote>
          <div class="justice-visual">
            <img src="{justice_image}" alt="Ilustração de uma balança da Justiça">
          </div>
        </div>
      </section>

      <section class="slide slide-cases">
        <div class="brand-row"><img src="{logo}" alt=""> APCE</div>
        <div>
          <div class="kicker">Processos julgados pelo TSE</div>
          <h2>Julgados mostram como templos e santinhos entram na controvérsia eleitoral.</h2>
        </div>
        {cases}
      </section>
    </div>

    <nav class="nav">
      <button type="button" id="prev">Anterior</button>
      <div class="status">
        <span id="counter">1 / 10</span>
        <div class="dots" id="dots"></div>
      </div>
      <button type="button" id="next">Próximo</button>
    </nav>
    <button type="button" class="nav-toggle" id="nav-toggle" aria-pressed="false">Ocultar navegação</button>
  </main>

  <script>
    const slides = Array.from(document.querySelectorAll(".slide"));
    const progress = document.getElementById("progress");
    const counter = document.getElementById("counter");
    const dots = document.getElementById("dots");
    const deck = document.querySelector(".deck");
    const navToggle = document.getElementById("nav-toggle");
    let current = 0;
    let currentCase = 0;
    const chartColors = ["{THEME["rose"]}", "{THEME["cosmos"]}", "{THEME["sand"]}"];
    const comparisonLabels = {json.dumps(COMPARISON_LABELS, ensure_ascii=False)};
    const groupOrders = {json.dumps(COMPARISON_GROUPS, ensure_ascii=False)};

    slides.forEach((_, index) => {{
      const dot = document.createElement("span");
      dot.className = "dot";
      dot.addEventListener("click", () => show(index));
      dots.appendChild(dot);
    }});

    function show(index) {{
      current = Math.max(0, Math.min(index, slides.length - 1));
      slides.forEach((slide, slideIndex) => slide.classList.toggle("active", slideIndex === current));
      Array.from(dots.children).forEach((dot, dotIndex) => dot.classList.toggle("active", dotIndex === current));
      progress.style.width = `${{((current + 1) / slides.length) * 100}}%`;
      counter.textContent = `${{current + 1}} / ${{slides.length}}`;
      document.getElementById("prev").disabled = current === 0;
      document.getElementById("next").disabled = current === slides.length - 1;
      slides[current].querySelectorAll(".chart-dashboard").forEach((chart) => renderChart(chart.id));
      setTimeout(() => slides[current].querySelectorAll(".chart-panel").forEach((panel) => Plotly.Plots.resize(panel)), 80);
      setTimeout(() => slides[current].querySelectorAll("iframe.visual-frame").forEach((frame) => {{
        try {{
          frame.contentWindow.dispatchEvent(new Event("resize"));
        }} catch (error) {{
          /* iframe may still be loading */
        }}
      }}), 120);
    }}

    function checked(chartId, name) {{
      return document.querySelector(`input[name="${{chartId}}-${{name}}"]:checked`)?.value;
    }}

    function money(value) {{
      return new Intl.NumberFormat("pt-BR", {{ style: "currency", currency: "BRL", maximumFractionDigits: 0 }}).format(value);
    }}

    function renderChart(chartId) {{
      const root = document.getElementById(chartId);
      if (!root || root.dataset.rendering === "1") return;
      root.dataset.rendering = "1";
      const records = JSON.parse(root.dataset.records);
      const mode = root.dataset.mode;
      const comparison = checked(chartId, "comparison");
      const year = checked(chartId, "year");
      const sphere = checked(chartId, "sphere");
      const fixedMetric = root.dataset.fixedMetric || null;
      const metric = mode === "totals" ? fixedMetric : null;
      let filtered = records.filter((d) => d.comparison === comparison && d.year === year && d.sphere === sphere);
      if (mode === "totals") filtered = filtered.filter((d) => d.metric === metric);

      let traces = [];
      let title = `${{comparisonLabels[comparison]}} · ${{year}} · ${{sphere}}`;
      if (mode === "totals") {{
        const groups = groupOrders[comparison];
        const values = groups.map((group) => filtered.find((d) => d.group === group)?.value || 0);
        const ns = groups.map((group) => filtered.find((d) => d.group === group)?.n || 0);
        traces = [{{
          type: "bar",
          x: groups,
          y: values,
          marker: {{ color: groups.map((_, i) => chartColors[i]) }},
          text: values.map(money),
          textposition: "outside",
          customdata: ns,
          hovertemplate: "%{{x}}<br>Média: %{{y:,.0f}}<br>N: %{{customdata}}<extra></extra>"
        }}];
        title = `${{filtered[0]?.metricLabel || "Valores médios"}} · ${{title}}`;
      }} else {{
        const rubrics = [...new Set(filtered.map((d) => d.rubric))];
        const groups = groupOrders[comparison];
        traces = groups.map((group, index) => {{
          const values = rubrics.map((rubric) => filtered.find((d) => d.group === group && d.rubric === rubric)?.value || 0);
          const ns = rubrics.map((rubric) => filtered.find((d) => d.group === group && d.rubric === rubric)?.n || 0);
          return {{
            type: "bar",
            name: group,
            x: rubrics,
            y: values,
            marker: {{ color: chartColors[index] }},
            customdata: ns,
            hovertemplate: group + "<br>%{{x}}<br>Média: %{{y:.2%}}<br>N: %{{customdata}}<extra></extra>"
          }};
        }});
      }}

      Plotly.react(`${{chartId}}-plot`, traces, {{
        title,
        barmode: "group",
        bargap: 0.24,
        bargroupgap: 0.08,
        paper_bgcolor: "#fffdfb",
        plot_bgcolor: "white",
        font: {{ family: "Inter, Segoe UI, Arial, sans-serif", color: "{THEME["cosmos"]}" }},
        margin: {{ l: 72, r: 28, t: 74, b: mode === "totals" ? 86 : 170 }},
        yaxis: {{
          title: mode === "totals" ? "Média por candidatura" : "Participação média na estrutura",
          tickformat: mode === "totals" ? ",.0f" : ".0%",
          gridcolor: "rgba(60,60,71,.12)"
        }},
        xaxis: {{ tickangle: mode === "totals" ? 0 : -28, automargin: true }},
        legend: {{ orientation: "h", y: 1.08, x: 0 }}
      }}, {{ responsive: true, displayModeBar: false }});
      root.dataset.rendering = "0";
    }}

    document.querySelectorAll(".chart-dashboard input").forEach((input) => {{
      input.addEventListener("change", () => renderChart(input.closest(".chart-dashboard").id));
    }});

    document.getElementById("prev").addEventListener("click", () => show(current - 1));
    document.getElementById("next").addEventListener("click", () => show(current + 1));
    navToggle.addEventListener("click", () => {{
      const hidden = deck.classList.toggle("nav-hidden");
      navToggle.textContent = hidden ? "Mostrar navegação" : "Ocultar navegação";
      navToggle.setAttribute("aria-pressed", String(hidden));
      setTimeout(() => {{
        slides[current].querySelectorAll(".chart-panel").forEach((panel) => Plotly.Plots.resize(panel));
        slides[current].querySelectorAll("iframe.visual-frame").forEach((frame) => {{
          try {{
            frame.contentWindow.dispatchEvent(new Event("resize"));
          }} catch (error) {{}}
        }});
      }}, 240);
    }});
    function showCase(index) {{
      const cards = Array.from(document.querySelectorAll(".case-card"));
      if (!cards.length) return;
      currentCase = Math.max(0, Math.min(index, cards.length - 1));
      cards.forEach((card, cardIndex) => card.classList.toggle("active", cardIndex === currentCase));
      document.querySelectorAll(".case-counter").forEach((counter) => {{
        counter.textContent = `${{currentCase + 1}} / ${{cards.length}}`;
      }});
      document.querySelectorAll(".case-prev").forEach((button) => {{
        button.disabled = currentCase === 0;
      }});
      document.querySelectorAll(".case-next").forEach((button) => {{
        button.disabled = currentCase === cards.length - 1;
      }});
    }}
    document.querySelectorAll(".case-prev").forEach((button) => {{
      button.addEventListener("click", () => showCase(currentCase - 1));
    }});
    document.querySelectorAll(".case-next").forEach((button) => {{
      button.addEventListener("click", () => showCase(currentCase + 1));
    }});
    window.addEventListener("keydown", (event) => {{
      if (event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") show(current + 1);
      if (event.key === "ArrowLeft" || event.key === "PageUp") show(current - 1);
      if (event.key === "Home") show(0);
      if (event.key === "End") show(slides.length - 1);
    }});
    show(0);
    showCase(0);
  </script>
</body>
</html>"""


def main() -> None:
    PRESENTATION_DIR.mkdir(parents=True, exist_ok=True)
    output = PRESENTATION_DIR / "religiao_politica_brasil.html"
    output.write_text(build_html(), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
