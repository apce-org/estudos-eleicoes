from __future__ import annotations

import argparse

import pandas as pd

from religiao_politica.config import PROCESSED_DIR, RAW_DIR
from religiao_politica.religious_terms import classify_religious_signal
from religiao_politica.tse import read_candidate_zip


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    columns = set(df.columns)
    for column in candidates:
        if column in columns:
            return column
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria resumo de sinais religiosos em candidaturas.")
    parser.add_argument("--years", nargs="+", type=int, default=[2014, 2018, 2022, 2024])
    args = parser.parse_args()

    rows = []
    enriched_frames = []

    for year in args.years:
        zip_path = RAW_DIR / f"consulta_cand_{year}.zip"
        if not zip_path.exists():
            print(f"Arquivo ausente, pulando: {zip_path}")
            continue

        df = read_candidate_zip(zip_path)
        ballot_name = pick_column(df, ["NM_URNA_CANDIDATO", "NM_CANDIDATO"])
        full_name = pick_column(df, ["NM_CANDIDATO"])
        occupation = pick_column(df, ["DS_OCUPACAO"])
        office = pick_column(df, ["DS_CARGO"])
        state = pick_column(df, ["SG_UF"])
        party = pick_column(df, ["SG_PARTIDO"])

        signal_values = []
        for _, row in df.iterrows():
            values = [
                row.get(ballot_name, ""),
                row.get(full_name, ""),
                row.get(occupation, ""),
            ]
            signal_values.append(classify_religious_signal(*values))

        df["ANO_ELEICAO_ANALISE"] = str(year)
        df["SINAL_RELIGIOSO"] = [match.has_religious_signal for match in signal_values]
        df["CATEGORIAS_RELIGIOSAS"] = [match.categories for match in signal_values]
        df["TERMOS_RELIGIOSOS"] = [match.matched_terms for match in signal_values]
        enriched_frames.append(df)

        grouped = (
            df.assign(total=1)
            .groupby(["ANO_ELEICAO_ANALISE", state, office, party, "SINAL_RELIGIOSO"], dropna=False)["total"]
            .sum()
            .reset_index()
        )
        rows.append(grouped)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    if enriched_frames:
        pd.concat(enriched_frames, ignore_index=True).to_parquet(
            PROCESSED_DIR / "candidaturas_enriquecidas.parquet",
            index=False,
        )
    if rows:
        pd.concat(rows, ignore_index=True).to_csv(
            PROCESSED_DIR / "resumo_sinais_religiosos.csv",
            index=False,
        )
        print(PROCESSED_DIR / "resumo_sinais_religiosos.csv")


if __name__ == "__main__":
    main()
