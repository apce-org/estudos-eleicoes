from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import folium
from branca.colormap import LinearColormap
import plotly.express as px
import plotly.graph_objects as go
import requests
from plotly.io import write_html
from unidecode import unidecode

from religiao_politica.config import FIGURES_DIR, PROCESSED_DIR, PROJECT_ROOT, RAW_DIR
from religiao_politica.tse import download_vote_zip, read_zip_csvs


THEME = {
    "cosmos": "#3c3c47",
    "rose": "#f04e63",
    "sand": "#e6d2c9",
    "paper": "#fbf7f4",
    "line": "#d9c4bd",
    "muted": "#6f6a70",
}

UF_TO_IBGE = {
    "RO": "11",
    "AC": "12",
    "AM": "13",
    "RR": "14",
    "PA": "15",
    "AP": "16",
    "TO": "17",
    "MA": "21",
    "PI": "22",
    "CE": "23",
    "RN": "24",
    "PB": "25",
    "PE": "26",
    "AL": "27",
    "SE": "28",
    "BA": "29",
    "MG": "31",
    "ES": "32",
    "RJ": "33",
    "SP": "35",
    "PR": "41",
    "SC": "42",
    "RS": "43",
    "MS": "50",
    "MT": "51",
    "GO": "52",
    "DF": "53",
}

SPHERE_ORDER = ["municipal", "estadual", "federal"]
IDEOLOGY_ORDER = ["direita", "esquerda"]
IBGE_MUNICIPAL_GEOJSON_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade=minima"
)


def slugify(value: str) -> str:
    text = unidecode(str(value)).casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "sem_nome"


def ensure_dirs(output_dir: Path) -> tuple[Path, Path]:
    figures_dir = FIGURES_DIR / "presentation_assets"
    data_dir = output_dir / "presentation_assets"
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    return figures_dir, data_dir


def apply_theme(fig: go.Figure, title: str | None = None) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_white",
        font={"family": "Inter, Segoe UI, Arial, sans-serif", "color": THEME["cosmos"]},
        paper_bgcolor=THEME["paper"],
        plot_bgcolor="white",
        colorway=[THEME["rose"], THEME["cosmos"], THEME["sand"], "#8f3646", "#777888"],
        margin={"l": 56, "r": 24, "t": 76, "b": 56},
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, linecolor=THEME["line"], zeroline=False)
    fig.update_yaxes(gridcolor="rgba(60,60,71,0.12)", linecolor=THEME["line"], zeroline=False)
    return fig


def save_figure(fig: go.Figure, path: Path) -> None:
    write_html(fig, path, include_plotlyjs="cdn", full_html=True, config={"displayModeBar": False, "responsive": True})


def load_uf_geojson() -> dict:
    path = RAW_DIR / "ibge_malha_ufs_minima.geojson"
    if not path.exists():
        raise FileNotFoundError(
            "Arquivo data/raw/ibge_malha_ufs_minima.geojson não encontrado. "
            "Rode scripts/build_brazil_map_demo.py ou baixe a malha mínima de UFs do IBGE."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_municipal_geojson(path: Path | None = None) -> dict:
    geojson_path = path or (RAW_DIR / "ibge_malha_municipios_minima.geojson")
    if not geojson_path.exists():
        response = requests.get(IBGE_MUNICIPAL_GEOJSON_URL, timeout=180)
        response.raise_for_status()
        geojson_path.write_text(response.text, encoding="utf-8")
    return json.loads(geojson_path.read_text(encoding="utf-8"))


def load_tse_ibge_municipality_map() -> pd.DataFrame:
    path = RAW_DIR / "municipio_tse_ibge.zip"
    if not path.exists():
        raise FileNotFoundError(
            "Arquivo data/raw/municipio_tse_ibge.zip não encontrado. "
            "Rode scripts/download_tse_votes_finance.py antes."
        )
    with zipfile.ZipFile(path) as archive:
        csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        mapping = pd.read_csv(archive.open(csv_name), sep=";", encoding="latin1", dtype=str)
    mapping = mapping.rename(
        columns={
            "CD_MUNICIPIO_TSE": "CD_MUNICIPIO",
            "CD_MUNICIPIO_IBGE": "codigo_ibge_municipio",
            "NM_MUNICIPIO_IBGE": "municipio_ibge",
        }
    )
    mapping["CD_MUNICIPIO"] = mapping["CD_MUNICIPIO"].astype(str).str.zfill(5)
    mapping["codigo_ibge_municipio"] = mapping["codigo_ibge_municipio"].astype(str).str.zfill(7)
    population_path = PROCESSED_DIR / "populacao_municipios_ibge_tcu_pnad.parquet"
    if population_path.exists():
        population = pd.read_parquet(population_path)
        population["nome_join"] = population["municipio"].map(lambda value: unidecode(str(value)).casefold().strip())
        population["uf"] = population["uf"].astype(str)
        population["codigo_ibge_municipio"] = population["codigo_ibge_municipio"].astype(str).str.zfill(7)
        name_lookup = (
            population[["uf", "nome_join", "codigo_ibge_municipio"]]
            .dropna()
            .drop_duplicates(["uf", "nome_join"])
        )
        mapping["nome_join"] = mapping["municipio_ibge"].map(lambda value: unidecode(str(value)).casefold().strip())
        mapping = mapping.merge(
            name_lookup.rename(columns={"uf": "SG_UF", "codigo_ibge_municipio": "codigo_ibge_municipio_nome"}),
            on=["SG_UF", "nome_join"],
            how="left",
        )
        mapping["codigo_ibge_municipio"] = mapping["codigo_ibge_municipio_nome"].fillna(mapping["codigo_ibge_municipio"])
        mapping = mapping.drop(columns=["nome_join", "codigo_ibge_municipio_nome"])
    return mapping[["SG_UF", "CD_MUNICIPIO", "codigo_ibge_municipio", "municipio_ibge"]].drop_duplicates()


def load_municipality_reference() -> dict[str, dict[str, str]]:
    references: list[pd.DataFrame] = []
    population_path = PROCESSED_DIR / "populacao_municipios_ibge_tcu_pnad.parquet"
    if population_path.exists():
        population = pd.read_parquet(population_path)
        population["codigo_ibge_municipio"] = population["codigo_ibge_municipio"].astype(str).str.zfill(7)
        references.append(
            population[["codigo_ibge_municipio", "municipio", "uf"]]
            .dropna()
            .drop_duplicates("codigo_ibge_municipio")
            .rename(columns={"municipio": "municipio_ibge", "uf": "SG_UF"})
        )
    try:
        references.append(load_tse_ibge_municipality_map()[["codigo_ibge_municipio", "municipio_ibge", "SG_UF"]])
    except FileNotFoundError:
        pass
    if not references:
        return {}
    reference = pd.concat(references, ignore_index=True).drop_duplicates("codigo_ibge_municipio")
    return {
        str(row.codigo_ibge_municipio).zfill(7): {"municipio": str(row.municipio_ibge), "uf": str(row.SG_UF)}
        for row in reference.itertuples(index=False)
    }


def load_candidates() -> pd.DataFrame:
    path = PROCESSED_DIR / "candidatos_legislativos_2012_2024.parquet"
    if not path.exists():
        raise FileNotFoundError("Rode scripts/build_all_legislative_candidates_base.py antes.")
    df = pd.read_parquet(path)
    df["SQ_CANDIDATO"] = df["SQ_CANDIDATO"].astype(str)
    df["ANO_ELEICAO_ANALISE"] = pd.to_numeric(df["ANO_ELEICAO_ANALISE"], errors="coerce").astype("Int64")
    df["SINAL_CRISTAO"] = df["SINAL_CRISTAO"].fillna(False).astype(bool)
    df["ELEITO"] = df["ELEITO"].fillna(False).astype(bool)
    df["ESFERA"] = df["ESFERA"].fillna("sem_esfera")
    df["IDEOLOGIA_PARTIDO"] = df["IDEOLOGIA_PARTIDO"].fillna("centro_ou_indefinido")
    keep = [
        "ANO_ELEICAO_ANALISE",
        "SQ_CANDIDATO",
        "SG_UF",
        "DS_CARGO",
        "DS_ELEICAO",
        "ESFERA",
        "SG_PARTIDO",
        "IDEOLOGIA_PARTIDO",
        "ELEITO",
        "SINAL_CRISTAO",
    ]
    return df[[column for column in keep if column in df.columns]].drop_duplicates(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"])


def vote_zip_path(year: int) -> Path:
    path = RAW_DIR / f"votacao_candidato_munzona_{year}.zip"
    return path if path.exists() else download_vote_zip(year)


def extract_votes_for_year(year: int, candidates: pd.DataFrame) -> pd.DataFrame:
    year_candidates = candidates[candidates["ANO_ELEICAO_ANALISE"].eq(year)]
    candidate_ids = set(year_candidates["SQ_CANDIDATO"])
    frames: list[pd.DataFrame] = []
    for csv_name, reader in read_zip_csvs(vote_zip_path(year), chunksize=250_000):
        if "_BRASIL" in Path(csv_name).name.upper():
            continue
        for chunk in reader:
            needed = {"SQ_CANDIDATO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "QT_VOTOS_NOMINAIS"}
            if not needed.issubset(chunk.columns):
                continue
            chunk["SQ_CANDIDATO"] = chunk["SQ_CANDIDATO"].astype(str)
            local = chunk[chunk["SQ_CANDIDATO"].isin(candidate_ids)].copy()
            if local.empty:
                continue
            local["votos"] = pd.to_numeric(
                local["QT_VOTOS_NOMINAIS"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                errors="coerce",
            ).fillna(0)
            local["CD_MUNICIPIO"] = local["CD_MUNICIPIO"].astype(str).str.zfill(5)
            frames.append(local[["SQ_CANDIDATO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "votos"]])
    if not frames:
        return pd.DataFrame(columns=["ANO_ELEICAO_ANALISE", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "SQ_CANDIDATO", "votos"])
    votes = pd.concat(frames, ignore_index=True)
    votes["ANO_ELEICAO_ANALISE"] = year
    return votes.groupby(["ANO_ELEICAO_ANALISE", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "SQ_CANDIDATO"], as_index=False)["votos"].sum()


def build_vote_base(candidates: pd.DataFrame, years: list[int], force: bool, data_dir: Path) -> pd.DataFrame:
    cache = data_dir / "votos_municipio_esfera_grupos_base.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, dtype={"CD_MUNICIPIO": str, "codigo_ibge_municipio": str})

    votes = pd.concat([extract_votes_for_year(year, candidates) for year in years], ignore_index=True)
    base = votes.merge(candidates, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left", suffixes=("_voto", "_cand"))
    base["SG_UF"] = base["SG_UF_voto"].fillna(base.get("SG_UF_cand"))
    base = base[base["ESFERA"].isin(SPHERE_ORDER)].copy()
    mapping = load_tse_ibge_municipality_map()
    base = base.merge(mapping, on=["SG_UF", "CD_MUNICIPIO"], how="left")
    base["codigo_ibge_municipio"] = base["codigo_ibge_municipio"].astype("string").str.zfill(7)
    base = (
        base.groupby(
            [
                "ANO_ELEICAO_ANALISE",
                "ESFERA",
                "SG_UF",
                "CD_MUNICIPIO",
                "NM_MUNICIPIO",
                "codigo_ibge_municipio",
                "municipio_ibge",
                "SINAL_CRISTAO",
                "IDEOLOGIA_PARTIDO",
            ],
            dropna=False,
            as_index=False,
        )["votos"]
        .sum()
    )
    base.to_csv(cache, index=False, encoding="utf-8-sig")
    return base


def build_vote_summary(vote_base: pd.DataFrame, force: bool, data_dir: Path) -> pd.DataFrame:
    cache = data_dir / "votos_uf_esfera_grupos.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, dtype={"codarea": str})

    base = vote_base.copy()
    base["grupo_religioso"] = np.where(base["SINAL_CRISTAO"], "Cristãos", "Não cristãos")
    base["grupo_ideologico_cristao"] = np.where(
        base["SINAL_CRISTAO"] & base["IDEOLOGIA_PARTIDO"].isin(IDEOLOGY_ORDER),
        base["IDEOLOGIA_PARTIDO"].str.capitalize(),
        np.nan,
    )
    religion = (
        base.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF", "grupo_religioso"], as_index=False)["votos"].sum()
    )
    religion["total_recorte"] = religion.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF"])["votos"].transform("sum")
    religion["pct_votos"] = religion["votos"] / religion["total_recorte"].replace(0, np.nan)
    religion["comparacao"] = "cristaos_vs_nao_cristaos"

    ideology = base[base["grupo_ideologico_cristao"].notna()].copy()
    ideology = (
        ideology.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF", "grupo_ideologico_cristao"], as_index=False)["votos"].sum()
    )
    ideology["total_recorte"] = ideology.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF"])["votos"].transform("sum")
    ideology["pct_votos"] = ideology["votos"] / ideology["total_recorte"].replace(0, np.nan)
    ideology = ideology.rename(columns={"grupo_ideologico_cristao": "grupo_religioso"})
    ideology["comparacao"] = "cristaos_direita_vs_esquerda"

    out = pd.concat([religion, ideology], ignore_index=True)
    out["codarea"] = out["SG_UF"].map(UF_TO_IBGE).astype("string").str.zfill(2)
    out.to_csv(cache, index=False, encoding="utf-8-sig")
    return out


def build_municipal_vote_summary(vote_base: pd.DataFrame, force: bool, data_dir: Path) -> pd.DataFrame:
    cache = data_dir / "votos_municipio_esfera_grupos.csv"
    if cache.exists() and not force:
        return pd.read_csv(cache, dtype={"codigo_ibge_municipio": str})

    base = vote_base[vote_base["codigo_ibge_municipio"].notna()].copy()
    base["grupo_religioso"] = np.where(base["SINAL_CRISTAO"], "Cristãos", "Não cristãos")
    base["grupo_ideologico_cristao"] = np.where(
        base["SINAL_CRISTAO"] & base["IDEOLOGIA_PARTIDO"].isin(IDEOLOGY_ORDER),
        base["IDEOLOGIA_PARTIDO"].str.capitalize(),
        np.nan,
    )
    municipality_keys = ["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF", "codigo_ibge_municipio", "municipio_ibge"]
    religion = base.groupby(municipality_keys + ["grupo_religioso"], as_index=False)["votos"].sum()
    religion["total_recorte"] = religion.groupby(municipality_keys)["votos"].transform("sum")
    religion["pct_votos"] = religion["votos"] / religion["total_recorte"].replace(0, np.nan)
    religion["comparacao"] = "cristaos_vs_nao_cristaos"

    ideology = base[base["grupo_ideologico_cristao"].notna()].copy()
    ideology = ideology.groupby(municipality_keys + ["grupo_ideologico_cristao"], as_index=False)["votos"].sum()
    ideology["total_recorte"] = ideology.groupby(municipality_keys)["votos"].transform("sum")
    ideology["pct_votos"] = ideology["votos"] / ideology["total_recorte"].replace(0, np.nan)
    ideology = ideology.rename(columns={"grupo_ideologico_cristao": "grupo_religioso"})
    ideology["comparacao"] = "cristaos_direita_vs_esquerda"

    out = pd.concat([religion, ideology], ignore_index=True)
    out["codigo_ibge_municipio"] = out["codigo_ibge_municipio"].astype("string").str.zfill(7)
    out.to_csv(cache, index=False, encoding="utf-8-sig")
    return out


def build_vote_maps(vote_summary: pd.DataFrame, figures_dir: Path) -> None:
    geojson = load_uf_geojson()
    maps_dir = figures_dir / "mapas"
    maps_dir.mkdir(parents=True, exist_ok=True)
    vote_summary = vote_summary.copy()
    vote_summary["codarea"] = vote_summary["codarea"].astype(str).str.zfill(2)

    for sphere in SPHERE_ORDER:
        religion = vote_summary[
            vote_summary["ESFERA"].eq(sphere)
            & vote_summary["comparacao"].eq("cristaos_vs_nao_cristaos")
            & vote_summary["grupo_religioso"].eq("Cristãos")
        ].copy()
        if not religion.empty:
            religion["pct_votos_pp"] = religion["pct_votos"] * 100
            fig = px.choropleth(
                religion,
                geojson=geojson,
                locations="codarea",
                featureidkey="properties.codarea",
                color="pct_votos_pp",
                animation_frame="ANO_ELEICAO_ANALISE",
                hover_name="SG_UF",
                hover_data={"pct_votos_pp": ":.2f", "votos": ":,.0f", "total_recorte": ":,.0f", "codarea": False},
                color_continuous_scale=[[0, THEME["sand"]], [0.55, "#c7858a"], [1, THEME["rose"]]],
                range_color=(0, max(1.0, float(religion["pct_votos_pp"].max()))),
                labels={"pct_votos_pp": "% de votos cristãos"},
            )
            fig.update_geos(fitbounds="locations", visible=False)
            apply_theme(fig, f"Voto cristão versus não cristão - {sphere}")
            save_figure(fig, maps_dir / f"mapa_votos_cristaos_vs_nao_cristaos_{sphere}.html")

        ideology = vote_summary[
            vote_summary["ESFERA"].eq(sphere)
            & vote_summary["comparacao"].eq("cristaos_direita_vs_esquerda")
        ].copy()
        if not ideology.empty:
            wide = ideology.pivot_table(
                index=["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF", "codarea"],
                columns="grupo_religioso",
                values="pct_votos",
                aggfunc="sum",
                fill_value=0,
            ).reset_index()
            wide["Direita"] = wide.get("Direita", 0.0)
            wide["Esquerda"] = wide.get("Esquerda", 0.0)
            wide["saldo_direita_esquerda_pp"] = (wide["Direita"] - wide["Esquerda"]) * 100
            limit = max(1.0, float(wide["saldo_direita_esquerda_pp"].abs().max()))
            fig = px.choropleth(
                wide,
                geojson=geojson,
                locations="codarea",
                featureidkey="properties.codarea",
                color="saldo_direita_esquerda_pp",
                animation_frame="ANO_ELEICAO_ANALISE",
                hover_name="SG_UF",
                hover_data={"Direita": ":.2%", "Esquerda": ":.2%", "saldo_direita_esquerda_pp": ":.2f", "codarea": False},
                color_continuous_scale=[[0, THEME["cosmos"]], [0.5, THEME["sand"]], [1, THEME["rose"]]],
                range_color=(-limit, limit),
                labels={"saldo_direita_esquerda_pp": "Direita - esquerda (p.p.)"},
            )
            fig.update_geos(fitbounds="locations", visible=False)
            apply_theme(fig, f"Voto cristão de direita versus esquerda - {sphere}")
            save_figure(fig, maps_dir / f"mapa_votos_cristaos_direita_vs_esquerda_{sphere}.html")


SCRIPT_SRC_RE = re.compile(r'<script(?P<attrs>[^>]*)\s+src=["\'](?P<url>https?://[^"\']+)["\'](?P<rest>[^>]*)></script>')
STYLESHEET_RE = re.compile(r'<link(?P<attrs>[^>]*)href=["\'](?P<url>https?://[^"\']+)["\'](?P<rest>[^>]*)>')


def vendor_asset_path(url: str, vendor_dir: Path) -> Path:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".txt"
    stem = re.sub(r"[^A-Za-z0-9]+", "-", f"{parsed.netloc}{parsed.path}").strip("-").lower()
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return vendor_dir / f"{stem}-{digest}{suffix}"


def read_vendor_asset(url: str, vendor_dir: Path) -> str:
    vendor_dir.mkdir(parents=True, exist_ok=True)
    path = vendor_asset_path(url, vendor_dir)
    if not path.exists():
        response = requests.get(url, timeout=180)
        response.raise_for_status()
        path.write_text(response.text, encoding=response.encoding or "utf-8")
    return path.read_text(encoding="utf-8")


def inline_folium_external_assets(html_text: str, vendor_dir: Path) -> str:
    def replace_script(match: re.Match[str]) -> str:
        url = match.group("url")
        content = read_vendor_asset(url, vendor_dir)
        return f"<script>\n/* {url} */\n{content}\n</script>"

    def replace_stylesheet(match: re.Match[str]) -> str:
        tag = match.group(0)
        if 'rel="stylesheet"' not in tag and "rel='stylesheet'" not in tag:
            return tag
        url = match.group("url")
        content = read_vendor_asset(url, vendor_dir)
        return f"<style>\n/* {url} */\n{content}\n</style>"

    html_text = SCRIPT_SRC_RE.sub(replace_script, html_text)
    html_text = STYLESHEET_RE.sub(replace_stylesheet, html_text)
    return html_text


def save_folium_map(
    data: pd.DataFrame,
    geojson: dict,
    value_column: str,
    legend_name: str,
    title: str,
    output_path: Path,
    scale: LinearColormap,
    municipality_reference: dict[str, dict[str, str]],
    extra_layers: list[dict[str, object]] | None = None,
) -> None:
    brazil_map = folium.Map(location=[-14.235, -51.9253], zoom_start=4, tiles="cartodbpositron", control_scale=True)
    layer_entries: list[dict[str, str]] = []
    title_html = (
        f'<div style="position: fixed; top: 16px; left: 56px; z-index: 9999; '
        f'font: 16px Inter, Segoe UI, Arial, sans-serif; color: {THEME["cosmos"]}; '
        f'background: rgba(251,247,244,.92); padding: 8px 10px; border-radius: 4px;">{title}</div>'
    )
    brazil_map.get_root().html.add_child(folium.Element(title_html))

    for index, year in enumerate(sorted(data["ANO_ELEICAO_ANALISE"].dropna().unique())):
        local = data[data["ANO_ELEICAO_ANALISE"].eq(year)].copy()
        values = local.set_index("codigo_ibge_municipio")[value_column].to_dict()
        names = local.set_index("codigo_ibge_municipio")["municipio_ibge"].to_dict()
        ufs = local.set_index("codigo_ibge_municipio")["SG_UF"].to_dict()
        votes = local.set_index("codigo_ibge_municipio")["votos"].to_dict()
        totals = local.set_index("codigo_ibge_municipio")["total_recorte"].to_dict()

        layer_geojson = json.loads(json.dumps(geojson))
        for feature in layer_geojson["features"]:
            code = str(feature["properties"]["codarea"]).zfill(7)
            value = values.get(code)
            reference = municipality_reference.get(code, {})
            feature["properties"]["valor_mapa"] = None if pd.isna(value) else round(float(value), 4)
            feature["properties"]["municipio"] = names.get(code) or reference.get("municipio") or code
            feature["properties"]["uf"] = ufs.get(code) or reference.get("uf") or ""
            feature["properties"]["votos"] = int(votes.get(code, 0) or 0)
            feature["properties"]["total_recorte"] = int(totals.get(code, 0) or 0)
            feature["properties"]["situacao"] = "Com dados no recorte" if value is not None and not pd.isna(value) else "Sem dados no recorte"

        def style_function(feature: dict, values_by_code: dict[str, float] = values) -> dict:
            code = str(feature["properties"]["codarea"]).zfill(7)
            value = values_by_code.get(code)
            if value is None or pd.isna(value):
                return {
                    "fillColor": "#ffffff",
                    "color": "rgba(60,60,71,0.18)",
                    "weight": 0.15,
                    "fillOpacity": 0.04,
                }
            return {
                "fillColor": scale(float(value)),
                "color": "rgba(60,60,71,0.22)",
                "weight": 0.12,
                "fillOpacity": 0.78,
            }

        feature_group = folium.FeatureGroup(name=str(int(year)), show=index == 0, control=False)
        folium.GeoJson(
            layer_geojson,
            name=str(int(year)),
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=["municipio", "uf", "situacao", "valor_mapa", "votos", "total_recorte"],
                aliases=["Município", "UF", "Situação", legend_name, "Votos", "Total do recorte"],
                localize=True,
                sticky=False,
            ),
        ).add_to(feature_group)
        feature_group.add_to(brazil_map)
        layer_entries.append({"label": str(int(year)), "layer": feature_group.get_name()})

    for extra in extra_layers or []:
        local = extra["data"].copy()
        extra_value_column = str(extra["value_column"])
        extra_legend_name = str(extra["legend_name"])
        extra_scale = extra["scale"]
        values = local.set_index("codigo_ibge_municipio")[extra_value_column].to_dict()
        names = local.set_index("codigo_ibge_municipio")["municipio_ibge"].to_dict()
        ufs = local.set_index("codigo_ibge_municipio")["SG_UF"].to_dict()
        start_values = local.set_index("codigo_ibge_municipio").get("pct_2012_pp", pd.Series(dtype=float)).to_dict()
        end_values = local.set_index("codigo_ibge_municipio").get("pct_2024_pp", pd.Series(dtype=float)).to_dict()

        layer_geojson = json.loads(json.dumps(geojson))
        for feature in layer_geojson["features"]:
            code = str(feature["properties"]["codarea"]).zfill(7)
            value = values.get(code)
            reference = municipality_reference.get(code, {})
            feature["properties"]["valor_mapa"] = None if pd.isna(value) else round(float(value), 4)
            feature["properties"]["municipio"] = names.get(code) or reference.get("municipio") or code
            feature["properties"]["uf"] = ufs.get(code) or reference.get("uf") or ""
            feature["properties"]["pct_2012_pp"] = None if pd.isna(start_values.get(code)) else round(float(start_values.get(code)), 4)
            feature["properties"]["pct_2024_pp"] = None if pd.isna(end_values.get(code)) else round(float(end_values.get(code)), 4)
            feature["properties"]["situacao"] = "Com delta 2012-2024" if value is not None and not pd.isna(value) else "Sem delta 2012-2024"

        def extra_style_function(feature: dict, values_by_code: dict[str, float] = values, scale_obj: LinearColormap = extra_scale) -> dict:
            code = str(feature["properties"]["codarea"]).zfill(7)
            value = values_by_code.get(code)
            if value is None or pd.isna(value):
                return {
                    "fillColor": "#ffffff",
                    "color": "rgba(60,60,71,0.18)",
                    "weight": 0.15,
                    "fillOpacity": 0.04,
                }
            return {
                "fillColor": scale_obj(float(value)),
                "color": "rgba(60,60,71,0.22)",
                "weight": 0.12,
                "fillOpacity": 0.78,
            }

        feature_group = folium.FeatureGroup(name=str(extra["name"]), show=False, control=False)
        folium.GeoJson(
            layer_geojson,
            name=str(extra["name"]),
            style_function=extra_style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=["municipio", "uf", "situacao", "valor_mapa", "pct_2012_pp", "pct_2024_pp"],
                aliases=["Município", "UF", "Situação", extra_legend_name, "% em 2012", "% em 2024"],
                localize=True,
                sticky=False,
            ),
        ).add_to(feature_group)
        feature_group.add_to(brazil_map)
        layer_entries.append({"label": str(extra["name"]), "layer": feature_group.get_name()})

    scale.caption = legend_name
    scale.add_to(brazil_map)
    control_id = f"radio-control-{output_path.stem}"
    entries_json = json.dumps(layer_entries, ensure_ascii=False)
    map_name = brazil_map.get_name()
    control_script = f"""
    (function() {{
      const map = {map_name};
      const entries = {entries_json};
      const layers = entries.map((entry) => window[entry.layer]);
      const CustomControl = L.Control.extend({{
        options: {{ position: "topright" }},
        onAdd: function() {{
          const div = L.DomUtil.create("div", "map-radio-control");
          div.id = "{control_id}";
          div.innerHTML = entries.map((entry, index) => `
            <label>
              <input type="radio" name="{control_id}-layer" value="${{index}}" ${{index === 0 ? "checked" : ""}}>
              <span>${{entry.label}}</span>
            </label>
          `).join("");
          L.DomEvent.disableClickPropagation(div);
          L.DomEvent.disableScrollPropagation(div);
          div.addEventListener("change", function(event) {{
            const selected = Number(event.target.value);
            layers.forEach((layer, index) => {{
              if (index === selected) {{
                if (!map.hasLayer(layer)) map.addLayer(layer);
              }} else if (map.hasLayer(layer)) {{
                map.removeLayer(layer);
              }}
            }});
          }});
          return div;
        }}
      }});
      map.addControl(new CustomControl());
      window.addEventListener("resize", function() {{
        setTimeout(function() {{
          map.invalidateSize();
        }}, 80);
      }});
      setTimeout(function() {{
        map.invalidateSize();
      }}, 120);
    }})();
    """
    control_style = """
    <style>
      .map-radio-control {
        background: rgba(255, 253, 251, .94);
        border: 1px solid rgba(60,60,71,.28);
        border-radius: 6px;
        box-shadow: 0 1px 4px rgba(60,60,71,.18);
        color: #3c3c47;
        font: 12px Inter, "Segoe UI", Arial, sans-serif;
        padding: 8px 10px;
      }
      .map-radio-control label {
        display: flex;
        align-items: center;
        gap: 5px;
        margin: 5px 0;
        cursor: pointer;
        white-space: nowrap;
      }
      .map-radio-control input { accent-color: #f04e63; }
    </style>
    """
    brazil_map.get_root().header.add_child(folium.Element(control_style))
    brazil_map.save(output_path)
    html_text = output_path.read_text(encoding="utf-8")
    html_text = html_text.replace("</html>", f"<script>\n{control_script}\n</script>\n</html>")
    html_text = inline_folium_external_assets(html_text, output_path.parent / "vendor")
    output_path.write_text(html_text, encoding="utf-8")


def build_municipal_vote_maps(vote_summary: pd.DataFrame, figures_dir: Path, geojson_path: Path | None = None) -> None:
    geojson = load_municipal_geojson(geojson_path)
    municipality_reference = load_municipality_reference()
    maps_dir = figures_dir / "mapas_municipais"
    maps_dir.mkdir(parents=True, exist_ok=True)
    vote_summary = vote_summary.copy()
    vote_summary["codigo_ibge_municipio"] = vote_summary["codigo_ibge_municipio"].astype(str).str.zfill(7)

    for sphere in SPHERE_ORDER:
        religion = vote_summary[
            vote_summary["ESFERA"].eq(sphere)
            & vote_summary["comparacao"].eq("cristaos_vs_nao_cristaos")
            & vote_summary["grupo_religioso"].eq("Cristãos")
        ].copy()
        if not religion.empty:
            religion["pct_votos_pp"] = religion["pct_votos"] * 100
            max_value = max(1.0, float(religion["pct_votos_pp"].quantile(0.995)))
            scale = LinearColormap(
                colors=[THEME["sand"], "#c7858a", THEME["rose"]],
                vmin=0,
                vmax=max_value,
            )
            delta_layers = []
            wide_delta = religion.pivot_table(
                index=["ESFERA", "SG_UF", "codigo_ibge_municipio", "municipio_ibge"],
                columns="ANO_ELEICAO_ANALISE",
                values="pct_votos_pp",
                aggfunc="first",
            ).reset_index()
            if 2012 in wide_delta.columns and 2024 in wide_delta.columns:
                delta = wide_delta.dropna(subset=[2012, 2024]).copy()
                if not delta.empty:
                    delta["delta_2012_2024_pp"] = delta[2024] - delta[2012]
                    delta["pct_2012_pp"] = delta[2012]
                    delta["pct_2024_pp"] = delta[2024]
                    delta_limit = max(1.0, float(delta["delta_2012_2024_pp"].abs().quantile(0.995)))
                    delta_layers.append(
                        {
                            "name": "Δ 2012-2024",
                            "data": delta,
                            "value_column": "delta_2012_2024_pp",
                            "legend_name": "Variação 2012-2024 (p.p.)",
                            "scale": LinearColormap(
                                colors=[THEME["cosmos"], THEME["sand"], THEME["rose"]],
                                vmin=-delta_limit,
                                vmax=delta_limit,
                            ),
                        }
                    )
            save_folium_map(
                religion,
                geojson,
                "pct_votos_pp",
                "% de votos cristãos",
                f"Voto cristão versus não cristão por município - {sphere}",
                maps_dir / f"mapa_municipal_votos_cristaos_vs_nao_cristaos_{sphere}.html",
                scale,
                municipality_reference,
                delta_layers,
            )

        ideology = vote_summary[
            vote_summary["ESFERA"].eq(sphere)
            & vote_summary["comparacao"].eq("cristaos_direita_vs_esquerda")
        ].copy()
        if not ideology.empty:
            wide = ideology.pivot_table(
                index=["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF", "codigo_ibge_municipio", "municipio_ibge"],
                columns="grupo_religioso",
                values="pct_votos",
                aggfunc="sum",
                fill_value=0,
            ).reset_index()
            wide["Direita"] = wide.get("Direita", 0.0)
            wide["Esquerda"] = wide.get("Esquerda", 0.0)
            wide["saldo_direita_esquerda_pp"] = (wide["Direita"] - wide["Esquerda"]) * 100
            limit = max(1.0, float(wide["saldo_direita_esquerda_pp"].abs().quantile(0.995)))
            wide["votos"] = 0
            wide["total_recorte"] = 0
            scale = LinearColormap(
                colors=[THEME["cosmos"], THEME["sand"], THEME["rose"]],
                vmin=-limit,
                vmax=limit,
            )
            save_folium_map(
                wide,
                geojson,
                "saldo_direita_esquerda_pp",
                "Direita - esquerda (p.p.)",
                f"Voto cristão de direita versus esquerda por município - {sphere}",
                maps_dir / f"mapa_municipal_votos_cristaos_direita_vs_esquerda_{sphere}.html",
                scale,
                municipality_reference,
            )


def build_candidate_share_bars(candidates: pd.DataFrame, figures_dir: Path, data_dir: Path) -> None:
    bars_dir = figures_dir / "barras"
    bars_dir.mkdir(parents=True, exist_ok=True)
    base = candidates[candidates["ESFERA"].isin(SPHERE_ORDER)].copy()
    base["grupo"] = np.where(base["SINAL_CRISTAO"], "Cristãos", "Não cristãos")
    base["pleito"] = base["DS_ELEICAO"].fillna("").str.title()
    counts = base.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "pleito", "grupo"], as_index=False).size()
    counts["total_recorte"] = counts.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "pleito"])["size"].transform("sum")
    counts["proporcao"] = counts["size"] / counts["total_recorte"].replace(0, np.nan)
    counts.to_csv(data_dir / "proporcao_candidaturas_cristas_por_ano_esfera_pleito.csv", index=False, encoding="utf-8-sig")
    fig = px.bar(
        counts,
        x="ANO_ELEICAO_ANALISE",
        y="proporcao",
        color="grupo",
        facet_row="ESFERA",
        barmode="stack",
        hover_data={"size": ":,.0f", "total_recorte": ":,.0f", "proporcao": ":.2%"},
        labels={"ANO_ELEICAO_ANALISE": "Ano", "proporcao": "Proporção de candidaturas", "grupo": "Grupo"},
        color_discrete_map={"Cristãos": THEME["rose"], "Não cristãos": THEME["cosmos"]},
    )
    fig.update_yaxes(tickformat=".0%")
    apply_theme(fig, "Proporção de candidaturas cristãs e não cristãs por ano e esfera")
    save_figure(fig, bars_dir / "barras_proporcao_candidaturas_cristas_por_ano_esfera.html")

    fig_pleito = px.bar(
        counts,
        x="ANO_ELEICAO_ANALISE",
        y="proporcao",
        color="grupo",
        facet_col="ESFERA",
        animation_frame="pleito",
        barmode="stack",
        hover_data={"size": ":,.0f", "total_recorte": ":,.0f", "proporcao": ":.2%"},
        labels={"ANO_ELEICAO_ANALISE": "Ano", "proporcao": "Proporção de candidaturas"},
        color_discrete_map={"Cristãos": THEME["rose"], "Não cristãos": THEME["cosmos"]},
    )
    fig_pleito.update_yaxes(tickformat=".0%")
    apply_theme(fig_pleito, "Proporção de candidaturas por pleito, esfera e ano")
    save_figure(fig_pleito, bars_dir / "barras_proporcao_candidaturas_cristas_por_pleito.html")


def normalize_group_labels(df: pd.DataFrame, comparison: str) -> pd.DataFrame:
    out = df.copy()
    if comparison == "eleitos_vs_derrotados":
        out["grupo"] = np.where(out["ELEITO"].fillna(False).astype(bool), "Cristãos eleitos", "Cristãos derrotados")
    elif comparison == "direita_vs_esquerda":
        out = out[out["IDEOLOGIA_PARTIDO"].isin(IDEOLOGY_ORDER)].copy()
        out["grupo"] = out["IDEOLOGIA_PARTIDO"].map({"direita": "Cristãos de direita", "esquerda": "Cristãos de esquerda"})
    else:
        raise ValueError(f"Comparação desconhecida: {comparison}")
    return out


def structure_summary(
    df: pd.DataFrame,
    value_column: str,
    type_column: str,
    comparison: str,
    period: str,
    top_n: int,
) -> pd.DataFrame:
    base = normalize_group_labels(df, comparison)
    base = base[base[value_column].gt(0) & base[type_column].notna()].copy()
    if base.empty:
        return pd.DataFrame()
    if period == "total":
        keys = ["grupo"]
        facet_keys: list[str] = []
        base["periodo"] = "2012-2024"
    elif period == "ano":
        keys = ["ANO_ELEICAO_ANALISE", "grupo"]
        facet_keys = ["ANO_ELEICAO_ANALISE"]
    elif period == "esfera":
        keys = ["ESFERA", "grupo"]
        facet_keys = ["ESFERA"]
    elif period == "ano_esfera":
        keys = ["ANO_ELEICAO_ANALISE", "ESFERA", "grupo"]
        facet_keys = ["ANO_ELEICAO_ANALISE", "ESFERA"]
    else:
        raise ValueError(f"Período desconhecido: {period}")

    grouped = base.groupby(keys + [type_column], as_index=False)[value_column].sum()
    totals = grouped.groupby(keys, as_index=False)[value_column].sum().rename(columns={value_column: "total_grupo"})
    grouped = grouped.merge(totals, on=keys, how="left")
    grouped["proporcao"] = grouped[value_column] / grouped["total_grupo"].replace(0, np.nan)
    relevance = grouped.groupby(facet_keys + [type_column] if facet_keys else [type_column], as_index=False)[value_column].sum()
    relevance["rank"] = relevance.groupby(facet_keys, dropna=False)[value_column].rank(method="first", ascending=False) if facet_keys else relevance[value_column].rank(method="first", ascending=False)
    top_types = relevance[relevance["rank"].le(top_n)][(facet_keys + [type_column]) if facet_keys else [type_column]]
    return grouped.merge(top_types, on=(facet_keys + [type_column]) if facet_keys else [type_column], how="inner")


def chart_structure(summary: pd.DataFrame, type_column: str, value_label: str, title: str, period: str) -> go.Figure:
    if period == "total":
        fig = px.bar(
            summary,
            x=type_column,
            y="proporcao",
            color="grupo",
            barmode="group",
            hover_data={"proporcao": ":.2%", "total_grupo": ":,.0f"},
            labels={type_column: "Rubrica", "proporcao": value_label},
            color_discrete_sequence=[THEME["rose"], THEME["cosmos"]],
        )
    elif period == "ano":
        fig = px.bar(
            summary,
            x=type_column,
            y="proporcao",
            color="grupo",
            animation_frame="ANO_ELEICAO_ANALISE",
            barmode="group",
            hover_data={"proporcao": ":.2%", "total_grupo": ":,.0f"},
            labels={type_column: "Rubrica", "proporcao": value_label},
            color_discrete_sequence=[THEME["rose"], THEME["cosmos"]],
        )
    elif period == "esfera":
        fig = px.bar(
            summary,
            x=type_column,
            y="proporcao",
            color="grupo",
            facet_col="ESFERA",
            barmode="group",
            hover_data={"proporcao": ":.2%", "total_grupo": ":,.0f"},
            labels={type_column: "Rubrica", "proporcao": value_label},
            color_discrete_sequence=[THEME["rose"], THEME["cosmos"]],
        )
    else:
        fig = px.bar(
            summary,
            x=type_column,
            y="proporcao",
            color="grupo",
            facet_col="ESFERA",
            animation_frame="ANO_ELEICAO_ANALISE",
            barmode="group",
            hover_data={"proporcao": ":.2%", "total_grupo": ":,.0f"},
            labels={type_column: "Rubrica", "proporcao": value_label},
            color_discrete_sequence=[THEME["rose"], THEME["cosmos"]],
        )
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickangle=-28)
    return apply_theme(fig, title)


def build_finance_structure_charts(figures_dir: Path, data_dir: Path, top_n: int) -> None:
    charts_dir = figures_dir / "estruturas_financeiras"
    charts_dir.mkdir(parents=True, exist_ok=True)

    specs = [
        {
            "name": "gastos",
            "path": PROCESSED_DIR / "despesas_tipos_cristaos_contratadas.parquet",
            "value_column": "valor_despesa",
            "type_column": "tipo_despesa",
            "label": "Participação nos gastos",
        },
        {
            "name": "receitas",
            "path": PROCESSED_DIR / "receitas_tipos_comparativa.parquet",
            "value_column": "valor_receita",
            "type_column": "tipo_receita",
            "label": "Participação na arrecadação",
        },
    ]
    comparisons = {
        "eleitos_vs_derrotados": "cristãos eleitos e derrotados",
        "direita_vs_esquerda": "cristãos de direita e de esquerda",
    }
    periods = {
        "total": "período total",
        "ano": "por ano",
        "esfera": "por esfera",
        "ano_esfera": "por ano e esfera",
    }

    for spec in specs:
        if not spec["path"].exists():
            raise FileNotFoundError(f"Base não encontrada: {spec['path']}")
        df = pd.read_parquet(spec["path"])
        if spec["name"] == "receitas":
            df = df[df["SINAL_CRISTAO"].fillna(False).astype(bool)].copy()
        df[spec["value_column"]] = pd.to_numeric(df[spec["value_column"]], errors="coerce").fillna(0)
        df["ESFERA"] = df["ESFERA"].fillna("sem_esfera")
        for comparison, comparison_label in comparisons.items():
            for period, period_label in periods.items():
                summary = structure_summary(
                    df,
                    spec["value_column"],
                    spec["type_column"],
                    comparison,
                    period,
                    top_n,
                )
                if summary.empty:
                    continue
                csv_name = f"estrutura_{spec['name']}_{comparison}_{period}.csv"
                summary.to_csv(data_dir / csv_name, index=False, encoding="utf-8-sig")
                fig = chart_structure(
                    summary,
                    spec["type_column"],
                    spec["label"],
                    f"Estrutura de {spec['name']} entre {comparison_label} - {period_label}",
                    period,
                )
                save_figure(fig, charts_dir / f"barras_estrutura_{spec['name']}_{comparison}_{period}.html")


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


def prepare_comparison_universe(df: pd.DataFrame, comparison: str) -> pd.DataFrame:
    out = df.copy()
    if comparison == "cristaos_vs_nao_cristaos":
        out["grupo"] = np.where(out["SINAL_CRISTAO"].fillna(False).astype(bool), "Cristãos", "Não cristãos")
    elif comparison == "cristaos_eleitos_vs_derrotados":
        out = out[out["SINAL_CRISTAO"].fillna(False).astype(bool)].copy()
        out["grupo"] = np.where(out["ELEITO"].fillna(False).astype(bool), "Cristãos eleitos", "Cristãos derrotados")
    elif comparison == "cristaos_direita_vs_esquerda":
        out = out[out["SINAL_CRISTAO"].fillna(False).astype(bool) & out["IDEOLOGIA_PARTIDO"].isin(IDEOLOGY_ORDER)].copy()
        out["grupo"] = out["IDEOLOGIA_PARTIDO"].map(
            {"direita": "Cristãos de direita", "esquerda": "Cristãos de esquerda"}
        )
    else:
        raise ValueError(f"Comparação desconhecida: {comparison}")
    return out


def selected_periods(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    years = ["Total"] + [str(int(year)) for year in sorted(df["ANO_ELEICAO_ANALISE"].dropna().unique())]
    spheres = ["Total"] + [sphere for sphere in SPHERE_ORDER if sphere in set(df["ESFERA"].dropna())]
    return years, spheres


def filter_period(df: pd.DataFrame, year: str, sphere: str) -> pd.DataFrame:
    out = df
    if year != "Total":
        out = out[out["ANO_ELEICAO_ANALISE"].astype(str).eq(year)]
    if sphere != "Total":
        out = out[out["ESFERA"].eq(sphere)]
    return out


def build_total_mean_records(finance: pd.DataFrame, years: list[str], spheres: list[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for comparison in COMPARISON_LABELS:
        universe = prepare_comparison_universe(finance, comparison)
        for year in years:
            for sphere in spheres:
                local = filter_period(universe, year, sphere)
                for metric, label in [
                    ("despesa_contratada", "Despesas totais médias"),
                    ("receita_total", "Receitas totais médias"),
                ]:
                    grouped = (
                        local.groupby("grupo", as_index=False)
                        .agg(valor=(metric, "mean"), n=("SQ_CANDIDATO", "nunique"))
                    )
                    for group in COMPARISON_GROUPS[comparison]:
                        row = grouped[grouped["grupo"].eq(group)]
                        records.append(
                            {
                                "comparison": comparison,
                                "year": year,
                                "sphere": sphere,
                                "metric": metric,
                                "metricLabel": label,
                                "group": group,
                                "value": float(row["valor"].iloc[0]) if not row.empty and pd.notna(row["valor"].iloc[0]) else 0.0,
                                "n": int(row["n"].iloc[0]) if not row.empty else 0,
                            }
                        )
    return records


def build_structure_records(
    finance: pd.DataFrame,
    detail: pd.DataFrame,
    years: list[str],
    spheres: list[str],
    value_column: str,
    total_column: str,
    type_column: str,
    top_n: int,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    detail = detail.copy()
    detail["SQ_CANDIDATO"] = detail["SQ_CANDIDATO"].astype(str)
    detail[value_column] = pd.to_numeric(detail[value_column], errors="coerce").fillna(0.0)

    for comparison in COMPARISON_LABELS:
        universe_all = prepare_comparison_universe(finance, comparison)
        for year in years:
            for sphere in spheres:
                universe = filter_period(universe_all, year, sphere).copy()
                if universe.empty:
                    continue
                candidate_ids = set(universe["SQ_CANDIDATO"].astype(str))
                local_detail = detail[detail["SQ_CANDIDATO"].astype(str).isin(candidate_ids)].copy()
                if year != "Total":
                    local_detail = local_detail[local_detail["ANO_ELEICAO_ANALISE"].astype(str).eq(year)]
                if sphere != "Total":
                    local_detail = local_detail[local_detail["ESFERA"].eq(sphere)]
                if local_detail.empty:
                    continue

                top_types = (
                    local_detail.groupby(type_column, as_index=False)[value_column]
                    .sum()
                    .sort_values(value_column, ascending=False)
                    .head(top_n)[type_column]
                    .tolist()
                )
                if not top_types:
                    continue

                type_values = (
                    local_detail[local_detail[type_column].isin(top_types)]
                    .groupby(["SQ_CANDIDATO", type_column], as_index=False)[value_column]
                    .sum()
                )
                candidate_totals = universe[["SQ_CANDIDATO", "grupo", total_column]].copy()
                candidate_totals["SQ_CANDIDATO"] = candidate_totals["SQ_CANDIDATO"].astype(str)
                candidate_totals[total_column] = pd.to_numeric(candidate_totals[total_column], errors="coerce").fillna(0.0)

                grid = candidate_totals[["SQ_CANDIDATO", "grupo", total_column]].merge(
                    pd.DataFrame({type_column: top_types}), how="cross"
                )
                grid = grid.merge(type_values, on=["SQ_CANDIDATO", type_column], how="left")
                grid[value_column] = grid[value_column].fillna(0.0)
                grid["participacao"] = np.where(
                    grid[total_column].gt(0),
                    grid[value_column] / grid[total_column],
                    0.0,
                )
                grouped = (
                    grid.groupby(["grupo", type_column], as_index=False)
                    .agg(valor=("participacao", "mean"), n=("SQ_CANDIDATO", "nunique"))
                )
                for expense_type in top_types:
                    for group in COMPARISON_GROUPS[comparison]:
                        row = grouped[grouped["grupo"].eq(group) & grouped[type_column].eq(expense_type)]
                        records.append(
                            {
                                "comparison": comparison,
                                "year": year,
                                "sphere": sphere,
                                "rubric": expense_type,
                                "group": group,
                                "value": float(row["valor"].iloc[0]) if not row.empty and pd.notna(row["valor"].iloc[0]) else 0.0,
                                "n": int(row["n"].iloc[0]) if not row.empty else 0,
                            }
                        )
    return records


def interactive_bar_html(
    title: str,
    subtitle: str,
    records: list[dict[str, object]],
    years: list[str],
    spheres: list[str],
    mode: str,
    fixed_metric: str | None = None,
) -> str:
    metric_control = ""
    if mode == "totals" and fixed_metric is None:
        metric_control = """
      <fieldset>
        <legend>Indicador</legend>
        <label><input type="radio" name="metric" value="despesa_contratada" checked> Despesas totais</label>
        <label><input type="radio" name="metric" value="receita_total"> Receitas totais</label>
      </fieldset>"""

    def radios(name: str, values: list[str]) -> str:
        labels = []
        for index, value in enumerate(values):
            checked = " checked" if index == 0 else ""
            labels.append(f'<label><input type="radio" name="{name}" value="{value}"{checked}> {value}</label>')
        return "\n".join(labels)

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {{
      --cosmos: {THEME["cosmos"]};
      --rose: {THEME["rose"]};
      --sand: {THEME["sand"]};
      --paper: {THEME["paper"]};
      --line: {THEME["line"]};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--cosmos);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
    }}
    main {{ padding: 28px; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; font-weight: 760; }}
    p {{ margin: 0 0 18px; color: #6f6a70; }}
    .workspace {{
      display: grid;
      grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
      gap: 16px;
      align-items: stretch;
    }}
    .controls {{
      display: grid;
      gap: 12px;
      align-content: start;
    }}
    fieldset {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,.74);
      padding: 10px 12px;
      min-width: 0;
    }}
    legend {{ font-weight: 700; padding: 0 4px; }}
    label {{ display: flex; align-items: center; gap: 6px; margin: 7px 0; white-space: normal; line-height: 1.25; }}
    input {{ accent-color: var(--rose); }}
    #chart {{
      width: 100%;
      height: min(620px, calc(100vh - 156px));
      max-height: calc(100vh - 156px);
      min-height: 500px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
    }}
    @media (max-width: 980px) {{
      .workspace {{ grid-template-columns: 1fr; }}
      #chart {{ height: 58vh; min-height: 420px; max-height: 58vh; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <div class="workspace">
      <div class="controls">
        <fieldset>
          <legend>Comparação</legend>
          {radios("comparison", list(COMPARISON_LABELS.keys()))}
        </fieldset>
        <fieldset>
          <legend>Ano</legend>
          {radios("year", years)}
        </fieldset>
        <fieldset>
          <legend>Esfera</legend>
          {radios("sphere", spheres)}
        </fieldset>
        {metric_control}
      </div>
      <div id="chart"></div>
    </div>
  </main>
  <script>
    const records = {json.dumps(records, ensure_ascii=False)};
    const comparisonLabels = {json.dumps(COMPARISON_LABELS, ensure_ascii=False)};
    const groupOrders = {json.dumps(COMPARISON_GROUPS, ensure_ascii=False)};
    const colors = ["{THEME["rose"]}", "{THEME["cosmos"]}", "{THEME["sand"]}"];
    const mode = "{mode}";

    function checked(name) {{
      return document.querySelector(`input[name="${{name}}"]:checked`)?.value;
    }}

    function money(value) {{
      return new Intl.NumberFormat("pt-BR", {{ style: "currency", currency: "BRL", maximumFractionDigits: 0 }}).format(value);
    }}

    function render() {{
      const comparison = checked("comparison");
      const year = checked("year");
      const sphere = checked("sphere");
      const fixedMetric = """ + (json.dumps(fixed_metric) if fixed_metric else "null") + """;
      const metric = mode === "totals" ? (fixedMetric || checked("metric")) : null;
      let filtered = records.filter((d) => d.comparison === comparison && d.year === year && d.sphere === sphere);
      if (mode === "totals") filtered = filtered.filter((d) => d.metric === metric);

      let traces = [];
      let title = comparisonLabels[comparison] + " · " + year + " · " + sphere;
      if (mode === "totals") {{
        const groups = groupOrders[comparison];
        const values = groups.map((group) => filtered.find((d) => d.group === group)?.value || 0);
        const ns = groups.map((group) => filtered.find((d) => d.group === group)?.n || 0);
        traces = [{{
          type: "bar",
          x: groups,
          y: values,
          marker: {{ color: groups.map((_, i) => colors[i]) }},
          text: values.map(money),
          textposition: "outside",
          customdata: ns,
          hovertemplate: "%{{x}}<br>Média: %{{y:,.0f}}<br>N: %{{customdata}}<extra></extra>"
        }}];
        title = (filtered[0]?.metricLabel || "Valores médios") + " · " + title;
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
            marker: {{ color: colors[index] }},
            customdata: ns,
            hovertemplate: group + "<br>%{{x}}<br>Média: %{{y:.2%}}<br>N: %{{customdata}}<extra></extra>"
          }};
        }});
      }}

      Plotly.newPlot("chart", traces, {{
        title,
        barmode: "group",
        bargap: 0.24,
        bargroupgap: 0.08,
        paper_bgcolor: "{THEME["paper"]}",
        plot_bgcolor: "white",
        font: {{ family: "Inter, Segoe UI, Arial, sans-serif", color: "{THEME["cosmos"]}" }},
        margin: {{ l: 72, r: 28, t: 78, b: mode === "totals" ? 90 : 190 }},
        yaxis: {{
          title: mode === "totals" ? "Média por candidatura" : "Participação média na estrutura",
          tickformat: mode === "totals" ? ",.0f" : ".0%",
          gridcolor: "rgba(60,60,71,.12)"
        }},
        xaxis: {{ tickangle: mode === "totals" ? 0 : -28, automargin: true }},
        legend: {{ orientation: "h", y: 1.08, x: 0 }}
      }}, {{ responsive: true, displayModeBar: false }});
    }}

    document.querySelectorAll("input").forEach((input) => input.addEventListener("change", render));
    render();
  </script>
</body>
</html>"""


def clean_old_bar_outputs(figures_dir: Path) -> Path:
    bars_dir = figures_dir / "barras"
    old_structure_dir = figures_dir / "estruturas_financeiras"
    bars_dir.mkdir(parents=True, exist_ok=True)
    for directory in [bars_dir, old_structure_dir]:
        if directory.exists():
            for path in directory.glob("*.html"):
                path.unlink()
    return bars_dir


def build_interactive_bar_dashboards(figures_dir: Path, data_dir: Path, top_n: int) -> None:
    bars_dir = clean_old_bar_outputs(figures_dir)
    finance_path = PROCESSED_DIR / "candidatos_legislativos_financiamento_resumo.parquet"
    expense_path = PROCESSED_DIR / "despesas_tipos_comparativa_contratadas.parquet"
    receipt_path = PROCESSED_DIR / "receitas_tipos_comparativa.parquet"
    for path in [finance_path, expense_path, receipt_path]:
        if not path.exists():
            raise FileNotFoundError(f"Base não encontrada: {path}")

    finance = pd.read_parquet(finance_path)
    finance["SQ_CANDIDATO"] = finance["SQ_CANDIDATO"].astype(str)
    finance["ESFERA"] = finance["ESFERA"].fillna("sem_esfera")
    finance["IDEOLOGIA_PARTIDO"] = finance["IDEOLOGIA_PARTIDO"].fillna("centro_ou_indefinido")
    for column in ["despesa_contratada", "receita_total"]:
        finance[column] = pd.to_numeric(finance[column], errors="coerce").fillna(0.0)

    years, spheres = selected_periods(finance)
    total_records = build_total_mean_records(finance, years, spheres)
    (data_dir / "barras_totais_medios.json").write_text(json.dumps(total_records, ensure_ascii=False), encoding="utf-8")
    (bars_dir / "barras_totais_medios.html").write_text(
        interactive_bar_html(
            "Despesas e receitas totais médias",
            "Barras simples com média por candidatura. Use os rádios para trocar comparação, ano e esfera.",
            total_records,
            years,
            spheres,
            "totals",
        ),
        encoding="utf-8",
    )
    (bars_dir / "barras_totais_despesas.html").write_text(
        interactive_bar_html(
            "Despesas totais médias",
            "Barras simples com despesa média por candidatura. Use os rádios para trocar comparação, ano e esfera.",
            total_records,
            years,
            spheres,
            "totals",
            fixed_metric="despesa_contratada",
        ),
        encoding="utf-8",
    )
    (bars_dir / "barras_totais_receitas.html").write_text(
        interactive_bar_html(
            "Receitas totais médias",
            "Barras simples com receita média por candidatura. Use os rádios para trocar comparação, ano e esfera.",
            total_records,
            years,
            spheres,
            "totals",
            fixed_metric="receita_total",
        ),
        encoding="utf-8",
    )

    expenses = pd.read_parquet(expense_path)
    expense_records = build_structure_records(
        finance,
        expenses,
        years,
        spheres,
        "valor_despesa",
        "despesa_contratada",
        "tipo_despesa",
        top_n,
    )
    (data_dir / "barras_estrutura_despesas.json").write_text(json.dumps(expense_records, ensure_ascii=False), encoding="utf-8")
    (bars_dir / "barras_estrutura_despesas.html").write_text(
        interactive_bar_html(
            "Estrutura média de despesas",
            f"Top {top_n} rubricas por volume no recorte selecionado. Barras indicam participação média por candidatura.",
            expense_records,
            years,
            spheres,
            "structure",
        ),
        encoding="utf-8",
    )

    receipts = pd.read_parquet(receipt_path)
    receipt_records = build_structure_records(
        finance,
        receipts,
        years,
        spheres,
        "valor_receita",
        "receita_total",
        "tipo_receita",
        top_n,
    )
    (data_dir / "barras_estrutura_receitas.json").write_text(json.dumps(receipt_records, ensure_ascii=False), encoding="utf-8")
    (bars_dir / "barras_estrutura_receitas.html").write_text(
        interactive_bar_html(
            "Estrutura média de arrecadação",
            f"Top {top_n} rubricas por volume no recorte selecionado. Barras indicam participação média por candidatura.",
            receipt_records,
            years,
            spheres,
            "structure",
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera mapas e gráficos para a apresentação sobre religião e política.")
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2014, 2016, 2018, 2020, 2022, 2024])
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--force-votes", action="store_true", help="Recalcula a base de votos por UF, esfera e grupo.")
    parser.add_argument("--skip-municipal-maps", action="store_true", help="Não gera mapas municipais.")
    parser.add_argument("--municipal-geojson", type=Path, default=None, help="GeoJSON municipal com código IBGE em properties.codarea.")
    args = parser.parse_args()

    figures_dir, data_dir = ensure_dirs(args.output_dir)
    candidates = load_candidates()
    vote_base = build_vote_base(candidates, args.years, args.force_votes, data_dir)
    vote_summary = build_vote_summary(vote_base, args.force_votes, data_dir)
    build_vote_maps(vote_summary, figures_dir)
    if not args.skip_municipal_maps:
        municipal_vote_summary = build_municipal_vote_summary(vote_base, args.force_votes, data_dir)
        build_municipal_vote_maps(municipal_vote_summary, figures_dir, args.municipal_geojson)
    build_interactive_bar_dashboards(figures_dir, data_dir, args.top_n)
    print(figures_dir.resolve())
    print(data_dir.resolve())


if __name__ == "__main__":
    main()
