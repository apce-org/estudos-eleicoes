from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from religiao_politica.config import PROCESSED_DIR, RAW_DIR
from religiao_politica.tse import (
    download_tse_ibge_municipality_codes,
    download_vote_zip,
    read_zip_csvs,
)


CANDIDATE_COLUMNS = [
    "ANO_ELEICAO_ANALISE",
    "SQ_CANDIDATO",
    "NM_CANDIDATO",
    "NM_URNA_CANDIDATO",
    "SG_PARTIDO",
    "DS_CARGO",
    "SG_UF",
    "ELEITO",
    "STATUS_RESULTADO",
    "FORCA_SINAL_CRISTAO",
    "TERMOS_CRISTAOS",
]


def read_tse_ibge_mapping() -> pd.DataFrame:
    zip_path = download_tse_ibge_municipality_codes()
    _, df = next(read_zip_csvs(zip_path))
    mapping = pd.DataFrame(
        {
            "SG_UF": df["SG_UF"],
            "CD_MUNICIPIO": df["CD_MUNICIPIO_TSE"].astype(str),
            "codigo_ibge_municipio": df["CD_MUNICIPIO_IBGE"].astype(str).str.zfill(7),
            "municipio_ibge": df["NM_MUNICIPIO_IBGE"],
        }
    ).drop_duplicates(["SG_UF", "CD_MUNICIPIO"])
    boa_esperanca_norte = mapping["SG_UF"].eq("MT") & mapping["CD_MUNICIPIO"].eq("73709")
    mapping.loc[boa_esperanca_norte, "codigo_ibge_municipio"] = "5101837"
    mapping.loc[boa_esperanca_norte, "municipio_ibge"] = "Boa Esperança do Norte"
    return mapping


def load_population() -> pd.DataFrame:
    path = PROCESSED_DIR / "populacao_municipios_ibge_tcu_pnad.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "Base de população não encontrada. Rode scripts/build_municipal_population_base.py antes."
        )
    population = pd.read_parquet(path)
    population["codigo_ibge_municipio"] = population["codigo_ibge_municipio"].astype(str).str.zfill(7)
    population["ano"] = pd.to_numeric(population["ano"], errors="coerce").astype("Int64")
    keep = [
        "codigo_ibge_municipio",
        "ano",
        "populacao_tcu",
        "municipio",
        "uf",
        "nome_uf",
        "regiao",
    ]
    extra = [column for column in ["populacao_pnad", "periodo", "periodo_nome"] if column in population.columns]
    return population[keep + extra].drop_duplicates(["codigo_ibge_municipio", "ano"])


def build_year_votes(year: int, candidates: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    year_candidates = candidates[candidates["ANO_ELEICAO_ANALISE"].astype(int).eq(year)].copy()
    year_candidates = year_candidates.drop_duplicates(["SQ_CANDIDATO"])
    if year_candidates.empty:
        return pd.DataFrame()

    candidate_ids = set(year_candidates["SQ_CANDIDATO"].astype(str))
    zip_path = RAW_DIR / f"votacao_candidato_munzona_{year}.zip"
    if not zip_path.exists():
        zip_path = download_vote_zip(year)

    grouped_frames = []
    for csv_name, reader in read_zip_csvs(zip_path, chunksize=250_000):
        normalized_name = Path(csv_name).name.upper()
        if "_BRASIL." in normalized_name or "_BR." in normalized_name:
            continue
        print(f"{year}: lendo {csv_name}")
        for chunk in reader:
            if "SQ_CANDIDATO" not in chunk.columns:
                continue
            filtered = chunk[chunk["SQ_CANDIDATO"].astype(str).isin(candidate_ids)].copy()
            if filtered.empty:
                continue

            vote_column = "QT_VOTOS_NOMINAIS"
            if vote_column not in filtered.columns:
                vote_column = "QT_VOTOS"
            if vote_column not in filtered.columns:
                continue

            filtered[vote_column] = pd.to_numeric(filtered[vote_column], errors="coerce").fillna(0).astype("int64")
            municipality_column = "CD_MUNICIPIO"
            if municipality_column not in filtered.columns:
                municipality_column = "SG_UE"

            grouped = (
                filtered.groupby(
                    ["ANO_ELEICAO", "SG_UF", municipality_column, "NM_MUNICIPIO", "SQ_CANDIDATO"],
                    dropna=False,
                )[vote_column]
                .sum()
                .reset_index()
                .rename(
                    columns={
                        municipality_column: "CD_MUNICIPIO",
                        vote_column: "votos_nominais",
                    }
                )
            )
            grouped_frames.append(grouped)

    if not grouped_frames:
        return pd.DataFrame()

    votes = (
        pd.concat(grouped_frames, ignore_index=True)
        .groupby(["ANO_ELEICAO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "SQ_CANDIDATO"], dropna=False)[
            "votos_nominais"
        ]
        .sum()
        .reset_index()
    )
    votes = votes[votes["votos_nominais"].gt(0)].copy()
    votes["CD_MUNICIPIO"] = votes["CD_MUNICIPIO"].astype(str)
    votes = votes.merge(mapping, on=["SG_UF", "CD_MUNICIPIO"], how="left")
    votes = votes[votes["codigo_ibge_municipio"].notna()].copy()
    return votes.merge(year_candidates[CANDIDATE_COLUMNS], on="SQ_CANDIDATO", how="left", suffixes=("_voto", "_cand"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria painel candidato cristão x município onde recebeu votos, com população municipal."
    )
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2014, 2016, 2018, 2020, 2022, 2024])
    args = parser.parse_args()

    candidates_path = PROCESSED_DIR / "candidatos_cristaos_2012_2024.parquet"
    if not candidates_path.exists():
        raise FileNotFoundError("Base de candidatos cristãos não encontrada.")

    candidates = pd.read_parquet(candidates_path)
    candidates["SQ_CANDIDATO"] = candidates["SQ_CANDIDATO"].astype(str)
    mapping = read_tse_ibge_mapping()
    population = load_population()

    frames = []
    for year in args.years:
        frame = build_year_votes(year, candidates, mapping)
        if not frame.empty:
            frame["ano"] = year
            frames.append(frame)
            print(f"{year}: {len(frame):,} linhas candidato-município".replace(",", "."))

    if not frames:
        raise RuntimeError("Nenhuma votação encontrada para os candidatos cristãos.")

    panel = pd.concat(frames, ignore_index=True)
    panel["codigo_ibge_municipio"] = panel["codigo_ibge_municipio"].astype("string").str.zfill(7)
    panel = panel.merge(population, on=["codigo_ibge_municipio", "ano"], how="left")

    output_parquet = PROCESSED_DIR / "candidatos_cristaos_votos_municipios_populacao.parquet"
    output_csv = PROCESSED_DIR / "candidatos_cristaos_votos_municipios_populacao.csv"
    panel.to_parquet(output_parquet, index=False)
    panel.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print(output_parquet)
    print(output_csv)
    print(f"Linhas: {len(panel):,}".replace(",", "."))


if __name__ == "__main__":
    main()
