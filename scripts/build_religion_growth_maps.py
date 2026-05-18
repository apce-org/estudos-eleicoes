from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests


DEFAULT_STATES_GEOJSON_URL = (
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
)


def load_geojson(path_or_url: str) -> dict:
    if path_or_url.startswith(("http://", "https://")):
        response = requests.get(path_or_url, timeout=120)
        response.raise_for_status()
        return response.json()
    with Path(path_or_url).open(encoding="utf-8") as file:
        return json.load(file)


def add_growth_columns(df: pd.DataFrame, id_columns: list[str], value_column: str) -> pd.DataFrame:
    ordered = df.sort_values("ANO_ELEICAO_ANALISE")
    first = ordered.groupby(id_columns, dropna=False).first().reset_index()
    last = ordered.groupby(id_columns, dropna=False).last().reset_index()
    merged = first[id_columns + [value_column, "ANO_ELEICAO_ANALISE"]].merge(
        last[id_columns + [value_column, "ANO_ELEICAO_ANALISE"]],
        on=id_columns,
        suffixes=("_inicial", "_final"),
    )
    merged["variacao_pontos_percentuais"] = (
        merged[f"{value_column}_final"] - merged[f"{value_column}_inicial"]
    ) * 100
    merged["variacao_percentual"] = (
        merged[f"{value_column}_final"] / merged[f"{value_column}_inicial"].replace(0, pd.NA) - 1
    ) * 100
    return merged


def build_state_maps(output_dir: Path, states_geojson: dict) -> None:
    source = output_dir / "crescimento_candidatos_cristaos_por_uf_esfera.csv"
    if not source.exists():
        raise FileNotFoundError("Rode scripts/run_religion_politics_analyses.py antes.")
    df = pd.read_csv(source)
    maps_dir = output_dir / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    for sphere, group in df.groupby("ESFERA", dropna=False):
        growth = add_growth_columns(group, ["SG_UF"], "pct_cristaos")
        fig = px.choropleth(
            growth,
            geojson=states_geojson,
            locations="SG_UF",
            featureidkey="properties.sigla",
            color="variacao_pontos_percentuais",
            color_continuous_scale="RdBu",
            color_continuous_midpoint=0,
            hover_name="SG_UF",
            hover_data={
                "pct_cristaos_inicial": ":.2%",
                "pct_cristaos_final": ":.2%",
                "variacao_pontos_percentuais": ":.2f",
                "variacao_percentual": ":.2f",
            },
            title=f"Crescimento de candidatos cristãos - esfera {sphere}",
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin={"r": 0, "t": 50, "l": 0, "b": 0})
        fig.write_html(maps_dir / f"mapa_crescimento_uf_{sphere}.html", include_plotlyjs="cdn")


def build_municipal_map(output_dir: Path, municipal_geojson_path: str | None) -> None:
    if not municipal_geojson_path:
        note = output_dir / "maps" / "nota_mapa_municipal.txt"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            "Para gerar o mapa municipal, rode este script com --municipal-geojson apontando "
            "para um GeoJSON municipal com código IBGE em properties.codigo_ibge_municipio.\n",
            encoding="utf-8",
        )
        return

    source = output_dir / "crescimento_candidatos_cristaos_municipal.csv"
    if not source.exists():
        raise FileNotFoundError("Rode scripts/run_religion_politics_analyses.py antes.")
    df = pd.read_csv(source, dtype={"codigo_ibge_municipio": str})
    if "codigo_ibge_municipio" not in df.columns:
        raise ValueError(
            "A base municipal precisa ter codigo_ibge_municipio. "
            "Use a base de votos municipais para mapas municipais detalhados."
        )
    municipal_geojson = load_geojson(municipal_geojson_path)
    growth = add_growth_columns(df, ["codigo_ibge_municipio", "NM_UE", "SG_UF"], "pct_cristaos")
    fig = px.choropleth(
        growth,
        geojson=municipal_geojson,
        locations="codigo_ibge_municipio",
        featureidkey="properties.codigo_ibge_municipio",
        color="variacao_pontos_percentuais",
        color_continuous_scale="RdBu",
        color_continuous_midpoint=0,
        hover_name="NM_UE",
        title="Crescimento de candidatos cristãos - esfera municipal",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.write_html(output_dir / "maps" / "mapa_crescimento_municipal.html", include_plotlyjs="cdn")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera mapas HTML de crescimento de candidatos cristãos.")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--states-geojson", default=DEFAULT_STATES_GEOJSON_URL)
    parser.add_argument("--municipal-geojson", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    states_geojson = load_geojson(args.states_geojson)
    build_state_maps(output_dir, states_geojson)
    build_municipal_map(output_dir, args.municipal_geojson)
    print((output_dir / "maps").resolve())


if __name__ == "__main__":
    main()
