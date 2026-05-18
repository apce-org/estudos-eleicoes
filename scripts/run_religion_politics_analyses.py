from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from religiao_politica.analysis import (
    add_analysis_dimensions,
    anova_rows,
    dedupe_candidates,
    ensure_outputs_dir,
    safe_rate,
    t_test_rows,
    write_csv,
)
from religiao_politica.config import PROCESSED_DIR


FINANCE_COLUMNS = [
    "receita_total",
    "receita_publica",
    "receita_pessoa_fisica",
    "receita_recursos_proprios",
    "receita_partido_ou_candidato",
    "receita_estimavel",
    "despesa_contratada",
    "despesa_paga",
    "doadores_distintos",
]


def load_all_candidates() -> pd.DataFrame:
    path = PROCESSED_DIR / "candidatos_legislativos_2012_2024.parquet"
    if not path.exists():
        raise FileNotFoundError("Rode scripts/build_all_legislative_candidates_base.py antes.")
    df = pd.read_parquet(path)
    df["SQ_CANDIDATO"] = df["SQ_CANDIDATO"].astype(str)
    df["SINAL_CRISTAO"] = df["SINAL_CRISTAO"].fillna(False).astype(bool)
    df["ELEITO"] = df["ELEITO"].fillna(False).astype(bool)
    return add_analysis_dimensions(dedupe_candidates(df))


def load_finance() -> pd.DataFrame:
    path = PROCESSED_DIR / "candidatos_legislativos_financiamento_resumo.parquet"
    if not path.exists():
        raise FileNotFoundError("Rode scripts/build_all_campaign_finance_summary.py antes.")
    df = pd.read_parquet(path)
    df["SQ_CANDIDATO"] = df["SQ_CANDIDATO"].astype(str)
    for column in FINANCE_COLUMNS:
        if column not in df.columns:
            df[column] = 0.0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    df["SINAL_CRISTAO"] = df["SINAL_CRISTAO"].fillna(False).astype(bool)
    df["ELEITO"] = df["ELEITO"].fillna(False).astype(bool)
    return add_analysis_dimensions(dedupe_candidates(df))


def load_votes_panel() -> pd.DataFrame:
    path = PROCESSED_DIR / "painel_candidatos_cristaos_votos_populacao_financiamento.parquet"
    if not path.exists():
        raise FileNotFoundError("Rode scripts/build_christian_integrated_panel.py antes.")
    df = pd.read_parquet(path)
    df["SQ_CANDIDATO"] = df["SQ_CANDIDATO"].astype(str)
    df["ANO_ELEICAO_ANALISE"] = pd.to_numeric(df["ANO_ELEICAO_ANALISE"], errors="coerce").astype("Int64")
    df = df.rename(columns={"SG_UF_voto": "SG_UF_VOTO"})
    df = add_analysis_dimensions(df)
    return df


def load_optional_socioeconomic() -> pd.DataFrame | None:
    parquet_path = PROCESSED_DIR / "municipios_socioeconomicos.parquet"
    csv_path = PROCESSED_DIR / "municipios_socioeconomicos.csv"
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    elif csv_path.exists():
        df = pd.read_csv(csv_path, dtype={"codigo_ibge_municipio": str})
    else:
        return None
    df["codigo_ibge_municipio"] = df["codigo_ibge_municipio"].astype(str).str.zfill(7)
    if "ano" in df.columns:
        df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
    return df


def add_finance_ratios(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    total = output["receita_total"].replace(0, np.nan)
    output["pct_receita_publica"] = output["receita_publica"] / total
    output["pct_receita_pessoa_fisica"] = output["receita_pessoa_fisica"] / total
    output["pct_receita_recursos_proprios"] = output["receita_recursos_proprios"] / total
    output["log_receita_total"] = np.log1p(output["receita_total"])
    output["log_despesa_contratada"] = np.log1p(output["despesa_contratada"])
    return output


def build_growth_outputs(candidates: pd.DataFrame, output_dir: Path) -> None:
    candidates = candidates.copy()
    candidates["total"] = 1
    candidates["cristao"] = candidates["SINAL_CRISTAO"].astype(int)
    candidates["eleito"] = candidates["ELEITO"].astype(int)
    candidates["cristao_eleito"] = (candidates["SINAL_CRISTAO"] & candidates["ELEITO"]).astype(int)

    by_level = (
        candidates.groupby(["ANO_ELEICAO_ANALISE", "ESFERA"], dropna=False)
        .agg(
            total_candidatos=("total", "sum"),
            candidatos_cristaos=("cristao", "sum"),
            eleitos_total=("eleito", "sum"),
            cristaos_eleitos=("cristao_eleito", "sum"),
        )
        .reset_index()
    )
    by_level["pct_cristaos"] = safe_rate(by_level["candidatos_cristaos"], by_level["total_candidatos"])
    by_level["chance_eleicao_cristaos"] = safe_rate(by_level["cristaos_eleitos"], by_level["candidatos_cristaos"])
    by_level["chance_eleicao_total"] = safe_rate(by_level["eleitos_total"], by_level["total_candidatos"])
    write_csv(by_level, output_dir / "crescimento_candidatos_cristaos_por_esfera.csv")

    uf = (
        candidates.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF"], dropna=False)
        .agg(
            total_candidatos=("total", "sum"),
            candidatos_cristaos=("cristao", "sum"),
            eleitos_total=("eleito", "sum"),
            cristaos_eleitos=("cristao_eleito", "sum"),
        )
        .reset_index()
    )
    uf["pct_cristaos"] = safe_rate(uf["candidatos_cristaos"], uf["total_candidatos"])
    uf["chance_eleicao_cristaos"] = safe_rate(uf["cristaos_eleitos"], uf["candidatos_cristaos"])
    write_csv(uf, output_dir / "crescimento_candidatos_cristaos_por_uf_esfera.csv")

    municipal = candidates[candidates["ESFERA"].eq("municipal")].copy()
    municipal_group_columns = ["ANO_ELEICAO_ANALISE", "SG_UF", "SG_UE", "NM_UE"]
    if "codigo_ibge_municipio" in municipal.columns:
        municipal_group_columns.append("codigo_ibge_municipio")
    municipal_growth = (
        municipal.groupby(municipal_group_columns, dropna=False)
        .agg(
            total_candidatos=("total", "sum"),
            candidatos_cristaos=("cristao", "sum"),
            eleitos_total=("eleito", "sum"),
            cristaos_eleitos=("cristao_eleito", "sum"),
        )
        .reset_index()
    )
    municipal_growth["pct_cristaos"] = safe_rate(
        municipal_growth["candidatos_cristaos"],
        municipal_growth["total_candidatos"],
    )
    municipal_growth["chance_eleicao_cristaos"] = safe_rate(
        municipal_growth["cristaos_eleitos"],
        municipal_growth["candidatos_cristaos"],
    )
    write_csv(municipal_growth, output_dir / "crescimento_candidatos_cristaos_municipal.csv")

    tests = t_test_rows(
        candidates.assign(eleito_num=candidates["ELEITO"].astype(int)),
        ["eleito_num"],
        "SINAL_CRISTAO",
        True,
        False,
        ["ANO_ELEICAO_ANALISE", "ESFERA"],
    )
    write_csv(tests, output_dir / "testes_chance_eleicao_cristaos_vs_nao_cristaos.csv")


def build_finance_outputs(finance: pd.DataFrame, output_dir: Path) -> None:
    finance = add_finance_ratios(finance)
    analysis_columns = FINANCE_COLUMNS + [
        "pct_receita_publica",
        "pct_receita_pessoa_fisica",
        "pct_receita_recursos_proprios",
        "log_receita_total",
        "log_despesa_contratada",
    ]
    finance["grupo_religiao_resultado"] = np.select(
        [
            finance["SINAL_CRISTAO"] & finance["ELEITO"],
            finance["SINAL_CRISTAO"] & ~finance["ELEITO"],
            ~finance["SINAL_CRISTAO"],
        ],
        ["cristao_eleito", "cristao_derrotado", "nao_cristao"],
        default="indefinido",
    )
    summary = (
        finance.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "grupo_religiao_resultado"], dropna=False)[analysis_columns]
        .agg(["count", "mean", "median", "sum"])
        .reset_index()
    )
    summary.columns = ["_".join([str(part) for part in column if part]) for column in summary.columns]
    write_csv(summary, output_dir / "financiamento_resumo_por_grupo_esfera.csv")

    religious = finance[finance["SINAL_CRISTAO"]].copy()
    tests_elected = t_test_rows(
        religious,
        analysis_columns,
        "ELEITO",
        True,
        False,
        ["ANO_ELEICAO_ANALISE", "ESFERA"],
    )
    write_csv(tests_elected, output_dir / "testes_financiamento_cristaos_eleitos_vs_derrotados.csv")

    tests_religion = t_test_rows(
        finance,
        analysis_columns,
        "SINAL_CRISTAO",
        True,
        False,
        ["ANO_ELEICAO_ANALISE", "ESFERA"],
    )
    write_csv(tests_religion, output_dir / "testes_financiamento_cristaos_vs_nao_cristaos.csv")

    tests_anova = anova_rows(
        finance,
        analysis_columns,
        "grupo_religiao_resultado",
        ["ANO_ELEICAO_ANALISE", "ESFERA"],
    )
    write_csv(tests_anova, output_dir / "anova_financiamento_grupos_religiao_resultado.csv")


def build_vote_distribution_outputs(votes: pd.DataFrame, output_dir: Path) -> None:
    votes = votes.copy()
    votes["votos_nominais"] = pd.to_numeric(votes["votos_nominais"], errors="coerce").fillna(0)
    votes["votos_por_100_mil_hab"] = votes["votos_nominais"] / votes["populacao_tcu"].replace(0, np.nan) * 100_000

    uf = (
        votes.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "SG_UF_VOTO"], dropna=False)
        .agg(
            votos_cristaos=("votos_nominais", "sum"),
            candidatos_cristaos=("SQ_CANDIDATO", "nunique"),
            municipios_com_votos=("codigo_ibge_municipio", "nunique"),
        )
        .reset_index()
    )
    write_csv(uf, output_dir / "distribuicao_votos_cristaos_por_uf_esfera.csv")

    municipality = (
        votes.groupby(
            [
                "ANO_ELEICAO_ANALISE",
                "ESFERA",
                "codigo_ibge_municipio",
                "municipio",
                "uf",
                "regiao",
                "populacao_tcu",
            ],
            dropna=False,
        )
        .agg(
            votos_cristaos=("votos_nominais", "sum"),
            candidatos_cristaos=("SQ_CANDIDATO", "nunique"),
            cristaos_eleitos=("ELEITO", "sum"),
        )
        .reset_index()
    )
    municipality["votos_por_100_mil_hab"] = (
        municipality["votos_cristaos"] / municipality["populacao_tcu"].replace(0, np.nan) * 100_000
    )
    write_csv(municipality, output_dir / "distribuicao_votos_cristaos_por_municipio_esfera.csv")


def build_municipal_characteristic_outputs(votes: pd.DataFrame, output_dir: Path) -> None:
    municipality = (
        votes.groupby(
            ["ANO_ELEICAO_ANALISE", "codigo_ibge_municipio", "municipio", "uf", "regiao", "populacao_tcu"],
            dropna=False,
        )
        .agg(votos_cristaos=("votos_nominais", "sum"), candidatos_cristaos=("SQ_CANDIDATO", "nunique"))
        .reset_index()
    )
    municipality["votos_por_100_mil_hab"] = (
        municipality["votos_cristaos"] / municipality["populacao_tcu"].replace(0, np.nan) * 100_000
    )
    municipality["faixa_populacional"] = pd.cut(
        municipality["populacao_tcu"],
        bins=[0, 20_000, 100_000, 500_000, np.inf],
        labels=["até_20_mil", "20_a_100_mil", "100_a_500_mil", "mais_de_500_mil"],
    )
    socioeconomic = load_optional_socioeconomic()
    if socioeconomic is not None:
        join_columns = ["codigo_ibge_municipio"]
        if "ano" in socioeconomic.columns:
            municipality = municipality.merge(
                socioeconomic,
                left_on=["codigo_ibge_municipio", "ANO_ELEICAO_ANALISE"],
                right_on=["codigo_ibge_municipio", "ano"],
                how="left",
            )
        else:
            municipality = municipality.merge(socioeconomic, on=join_columns, how="left")

    write_csv(municipality, output_dir / "caracteristicas_municipios_voto_cristao.csv")

    numeric_columns = [
        column
        for column in municipality.columns
        if column
        not in {
            "ANO_ELEICAO_ANALISE",
            "codigo_ibge_municipio",
            "municipio",
            "uf",
            "regiao",
            "faixa_populacional",
        }
        and pd.api.types.is_numeric_dtype(municipality[column])
    ]
    municipality["alto_voto_cristao"] = municipality.groupby("ANO_ELEICAO_ANALISE")[
        "votos_por_100_mil_hab"
    ].transform(lambda s: s >= s.median())
    tests = t_test_rows(
        municipality,
        numeric_columns,
        "alto_voto_cristao",
        True,
        False,
        ["ANO_ELEICAO_ANALISE"],
    )
    write_csv(tests, output_dir / "testes_caracteristicas_municipios_alto_vs_baixo_voto_cristao.csv")

    missing = pd.DataFrame(
        {
            "tema": ["renda_media_municipal", "nivel_instrucao_municipal"],
            "status": [
                "incluído se existir em data/processed/municipios_socioeconomicos.csv ou parquet",
                "incluído se existir em data/processed/municipios_socioeconomicos.csv ou parquet",
            ],
        }
    )
    write_csv(missing, output_dir / "nota_base_socioeconomica_municipal.csv")


def build_ideology_outputs(candidates: pd.DataFrame, finance: pd.DataFrame, votes: pd.DataFrame, output_dir: Path) -> None:
    christian_candidates = candidates[candidates["SINAL_CRISTAO"]].copy()
    ideology_growth = (
        christian_candidates.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "IDEOLOGIA_PARTIDO"], dropna=False)
        .agg(candidatos=("SQ_CANDIDATO", "nunique"), eleitos=("ELEITO", "sum"))
        .reset_index()
    )
    ideology_growth["chance_eleicao"] = safe_rate(ideology_growth["eleitos"], ideology_growth["candidatos"])
    write_csv(ideology_growth, output_dir / "candidatos_cristaos_por_ideologia_esfera.csv")

    christian_finance = add_finance_ratios(finance[finance["SINAL_CRISTAO"]].copy())
    ideology_tests = t_test_rows(
        christian_finance[christian_finance["IDEOLOGIA_PARTIDO"].isin(["direita", "esquerda"])],
        FINANCE_COLUMNS + ["pct_receita_publica", "pct_receita_pessoa_fisica", "log_receita_total"],
        "IDEOLOGIA_PARTIDO",
        "direita",
        "esquerda",
        ["ANO_ELEICAO_ANALISE", "ESFERA"],
    )
    write_csv(ideology_tests, output_dir / "testes_financiamento_cristaos_direita_vs_esquerda.csv")

    elected_ids = set(christian_candidates[christian_candidates["ELEITO"]]["SQ_CANDIDATO"].astype(str))
    elected_votes = votes[votes["SQ_CANDIDATO"].isin(elected_ids)].copy()
    municipality = (
        elected_votes.groupby(
            [
                "ANO_ELEICAO_ANALISE",
                "IDEOLOGIA_PARTIDO",
                "codigo_ibge_municipio",
                "municipio",
                "uf",
                "regiao",
                "populacao_tcu",
            ],
            dropna=False,
        )
        .agg(votos_cristaos_eleitos=("votos_nominais", "sum"), candidatos_eleitos=("SQ_CANDIDATO", "nunique"))
        .reset_index()
    )
    write_csv(municipality, output_dir / "municipios_votos_cristaos_eleitos_por_ideologia.csv")

    ideology_municipal_tests = t_test_rows(
        municipality[municipality["IDEOLOGIA_PARTIDO"].isin(["direita", "esquerda"])],
        ["populacao_tcu", "votos_cristaos_eleitos", "candidatos_eleitos"],
        "IDEOLOGIA_PARTIDO",
        "direita",
        "esquerda",
        ["ANO_ELEICAO_ANALISE"],
    )
    write_csv(ideology_municipal_tests, output_dir / "testes_municipios_cristaos_eleitos_direita_vs_esquerda.csv")


def export_analysis_bases(candidates: pd.DataFrame, finance: pd.DataFrame, votes: pd.DataFrame, output_dir: Path) -> None:
    bases_dir = output_dir / "bases"
    bases_dir.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(bases_dir / "base_candidatos_legislativos_analise.csv", index=False, encoding="utf-8-sig")
    finance.to_csv(bases_dir / "base_financiamento_legislativo_analise.csv", index=False, encoding="utf-8-sig")
    votes.to_csv(bases_dir / "base_votos_cristaos_municipio_analise.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda cruzamentos e testes estatísticos do estudo religião-política.")
    parser.add_argument("--output-dir", default="outputs", help="Pasta de saída para bases e resultados CSV.")
    args = parser.parse_args()

    output_dir = ensure_outputs_dir(Path(args.output_dir))
    candidates = load_all_candidates()
    finance = load_finance()
    votes = load_votes_panel()

    export_analysis_bases(candidates, finance, votes, output_dir)
    build_growth_outputs(candidates, output_dir)
    build_finance_outputs(finance, output_dir)
    build_vote_distribution_outputs(votes, output_dir)
    build_municipal_characteristic_outputs(votes, output_dir)
    build_ideology_outputs(candidates, finance, votes, output_dir)

    print(output_dir.resolve())
    print("Análises concluídas.")


if __name__ == "__main__":
    main()
