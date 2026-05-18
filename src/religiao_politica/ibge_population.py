from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import requests


SIDRA_API = "https://apisidra.ibge.gov.br/values"
LOCALIDADES_MUNICIPIOS_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
)

TCU_ESTIMATE_TABLE = "6579"
TCU_ESTIMATE_VARIABLE = "9324"

CENSUS_2022_TABLE = "4714"
CENSUS_2022_VARIABLE = "93"

PNAD_POPULATION_TABLE = "5917"
PNAD_POPULATION_VARIABLE = "606"
PNAD_TOTAL_SEX_CLASSIFICATION = "c2/6794"

SPECIAL_MUNICIPAL_POPULATION = {
    # Município incluído na estrutura territorial de 2024. A tabela 6579 já
    # retorna o código, mas sem valor de população em algumas consultas.
    # Fonte: IBGE Cidades e Estados, Boa Esperança do Norte (MT), 2024.
    ("5101837", 2024): 5_772,
}


def _as_sidra_period(periods: int | str | Iterable[int | str]) -> str:
    if isinstance(periods, (int, str)):
        return str(periods)
    return ",".join(str(period) for period in periods)


def _sidra_json(path: str, timeout: int = 120) -> list[dict[str, str]]:
    url = f"{SIDRA_API}/{path.lstrip('/')}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not data or len(data) == 1:
        return []
    return data[1:]


def _to_number(series: pd.Series) -> pd.Series:
    normalized = (
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .replace({"-": pd.NA, "...": pd.NA, "X": pd.NA})
    )
    return pd.to_numeric(normalized, errors="coerce")


def fetch_municipalities() -> pd.DataFrame:
    """Baixa a lista oficial de municípios do IBGE, indexada pelo código de 7 dígitos."""
    response = requests.get(LOCALIDADES_MUNICIPIOS_URL, timeout=120)
    response.raise_for_status()
    df = pd.DataFrame(response.json())

    output = pd.DataFrame(
        {
            "codigo_ibge_municipio": df["municipio-id"].astype(str).str.zfill(7),
            "municipio": df["municipio-nome"],
            "codigo_ibge_uf": df["UF-id"].astype(str).str.zfill(2),
            "uf": df["UF-sigla"],
            "nome_uf": df["UF-nome"],
            "regiao": df["regiao-nome"],
        }
    )
    return output.set_index("codigo_ibge_municipio").sort_index()


def fetch_tcu_municipal_population(
    years: int | str | Iterable[int | str],
) -> pd.DataFrame:
    """Baixa estimativas anuais de população municipal usadas pelo TCU.

    Fonte: SIDRA/IBGE tabela 6579. Nem todos os anos existem nessa série; anos de
    Censo ou sem divulgação no SIDRA simplesmente não retornam linhas.
    """
    period = _as_sidra_period(years)
    path = f"t/{TCU_ESTIMATE_TABLE}/n6/all/v/{TCU_ESTIMATE_VARIABLE}/p/{period}?formato=json"
    rows = _sidra_json(path)
    if not rows:
        return pd.DataFrame(
            columns=[
                "codigo_ibge_municipio",
                "municipio_uf",
                "ano",
                "populacao_tcu",
                "unidade",
                "fonte",
            ]
        ).set_index("codigo_ibge_municipio")

    df = pd.DataFrame(rows)
    output = pd.DataFrame(
        {
            "codigo_ibge_municipio": df["D1C"].astype(str).str.zfill(7),
            "municipio_uf": df["D1N"],
            "ano": pd.to_numeric(df["D3C"], errors="coerce").astype("Int64"),
            "populacao_tcu": _to_number(df["V"]).astype("Int64"),
            "unidade": df["MN"],
            "fonte": "IBGE/SIDRA tabela 6579 - Estimativas de População",
        }
    )
    return output.set_index("codigo_ibge_municipio").sort_index()


def fetch_census_2022_municipal_population() -> pd.DataFrame:
    """Baixa população residente municipal do Censo 2022.

    A saída mantém a coluna `populacao_tcu` para ser compatível com o painel já
    usado nos scripts. A fonte identifica explicitamente que o dado é censitário.
    """
    path = f"t/{CENSUS_2022_TABLE}/n6/all/v/{CENSUS_2022_VARIABLE}/p/2022?formato=json"
    rows = _sidra_json(path)
    if not rows:
        return pd.DataFrame(
            columns=[
                "codigo_ibge_municipio",
                "municipio_uf",
                "ano",
                "populacao_tcu",
                "unidade",
                "fonte",
            ]
        ).set_index("codigo_ibge_municipio")

    df = pd.DataFrame(rows)
    output = pd.DataFrame(
        {
            "codigo_ibge_municipio": df["D1C"].astype(str).str.zfill(7),
            "municipio_uf": df["D1N"],
            "ano": 2022,
            "populacao_tcu": _to_number(df["V"]).astype("Int64"),
            "unidade": df["MN"],
            "fonte": "IBGE/SIDRA tabela 4714 - Censo Demográfico 2022",
        }
    )
    return output.set_index("codigo_ibge_municipio").sort_index()


def fetch_pnad_population_by_municipality(
    periods: int | str | Iterable[int | str] = "last",
) -> pd.DataFrame:
    """Baixa população da PNAD Contínua para municípios disponíveis no SIDRA.

    A PNAD não tem estimativas para todos os municípios brasileiros. No recorte
    municipal do SIDRA, a tabela trimestral retorna principalmente capitais e
    municípios cobertos por recortes metropolitanos/RIDE. Para população de
    todos os municípios, use `fetch_tcu_municipal_population`.
    """
    period = _as_sidra_period(periods)
    path = (
        f"t/{PNAD_POPULATION_TABLE}/n6/all/v/{PNAD_POPULATION_VARIABLE}/"
        f"p/{period}/{PNAD_TOTAL_SEX_CLASSIFICATION}?formato=json"
    )
    rows = _sidra_json(path)
    if not rows:
        return pd.DataFrame(
            columns=[
                "codigo_ibge_municipio",
                "municipio_uf",
                "periodo",
                "periodo_nome",
                "populacao_pnad_mil_pessoas",
                "populacao_pnad",
                "unidade",
                "fonte",
            ]
        ).set_index("codigo_ibge_municipio")

    df = pd.DataFrame(rows)
    population_thousand = _to_number(df["V"])
    output = pd.DataFrame(
        {
            "codigo_ibge_municipio": df["D1C"].astype(str).str.zfill(7),
            "municipio_uf": df["D1N"],
            "periodo": df["D3C"].astype(str),
            "periodo_nome": df["D3N"],
            "populacao_pnad_mil_pessoas": population_thousand,
            "populacao_pnad": (population_thousand * 1000).round().astype("Int64"),
            "unidade": df["MN"],
            "fonte": "IBGE/SIDRA tabela 5917 - PNAD Contínua Trimestral",
        }
    )
    return output.set_index("codigo_ibge_municipio").sort_index()


def build_municipal_population_panel(
    tcu_years: int | str | Iterable[int | str],
    pnad_periods: int | str | Iterable[int | str] | None = None,
) -> pd.DataFrame:
    """Monta painel municipal com cadastro IBGE, estimativa TCU/Censo e PNAD disponível."""
    municipalities = fetch_municipalities()
    tcu = fetch_tcu_municipal_population(tcu_years)
    requested_years = {str(year) for year in _as_sidra_period(tcu_years).split(",")}
    if "2022" in requested_years:
        census_2022 = fetch_census_2022_municipal_population()
        tcu = pd.concat([tcu[tcu["ano"].astype(str).ne("2022")], census_2022])

    panel = tcu.join(municipalities, how="left")
    for (municipality_code, year), population in SPECIAL_MUNICIPAL_POPULATION.items():
        municipality_mask = panel.index.astype(str).str.zfill(7) == municipality_code
        year_mask = panel["ano"].astype("Int64").eq(year)
        mask = municipality_mask & year_mask
        panel.loc[mask, "populacao_tcu"] = population
        panel.loc[mask, "fonte"] = "IBGE Cidades e Estados - População estimada 2024"

    if pnad_periods is not None:
        pnad = fetch_pnad_population_by_municipality(pnad_periods)
        pnad_columns = [
            "periodo",
            "periodo_nome",
            "populacao_pnad_mil_pessoas",
            "populacao_pnad",
        ]
        panel = panel.join(pnad[pnad_columns], how="left")

    return panel.reset_index()
