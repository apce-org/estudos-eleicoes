from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from religiao_politica.config import PROCESSED_DIR, RAW_DIR
from religiao_politica.religious_terms import SIGNAL_STRENGTH_ORDER, iter_christian_patterns
from religiao_politica.tse import read_candidate_zip


PREFERRED_COLUMNS = [
    "ANO_ELEICAO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "NR_TURNO",
    "SG_UF",
    "SG_UE",
    "NM_UE",
    "CD_CARGO",
    "DS_CARGO",
    "SQ_CANDIDATO",
    "NR_CANDIDATO",
    "NM_CANDIDATO",
    "NM_URNA_CANDIDATO",
    "NM_SOCIAL_CANDIDATO",
    "SG_PARTIDO",
    "NM_PARTIDO",
    "DS_GENERO",
    "DS_GRAU_INSTRUCAO",
    "DS_COR_RACA",
    "DS_OCUPACAO",
    "DS_SITUACAO_CANDIDATURA",
    "CD_SIT_TOT_TURNO",
    "DS_SIT_TOT_TURNO",
    "DS_SITUACAO_CANDIDATO_TOT",
]

TEXT_COLUMNS = ["NM_CANDIDATO", "NM_URNA_CANDIDATO", "NM_SOCIAL_CANDIDATO", "DS_OCUPACAO"]


def normalize_series(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
        .str.casefold()
    )


def classify_elected(status: pd.Series) -> pd.Series:
    normalized = normalize_series(status)
    has_eleito = normalized.str.contains(r"\beleito\b", regex=True, na=False)
    not_elected = normalized.str.contains(r"\bnao eleito\b", regex=True, na=False)
    return has_eleito & ~not_elected


def compact_match_columns(matches: dict[str, pd.Series]) -> tuple[pd.Series, pd.Series]:
    categories = []
    terms = []

    for category, mask in matches.items():
        categories.append(pd.Series(category, index=mask.index).where(mask, ""))

    category_frame = pd.concat(categories, axis=1) if categories else pd.DataFrame()
    category_values = category_frame.apply(
        lambda row: ";".join(sorted({value for value in row if value})),
        axis=1,
    )

    term_values = pd.Series("", index=next(iter(matches.values())).index)
    for category, mask in matches.items():
        term_values = term_values.mask(
            mask,
            term_values.where(term_values.eq(""), term_values + ";") + category,
        )

    return category_values, term_values


def append_unique(current: pd.Series, mask: pd.Series, value: str) -> pd.Series:
    return current.mask(mask, current.where(current.eq(""), current + ";") + value)


def strongest_strength(current: pd.Series, mask: pd.Series, value: str) -> pd.Series:
    current_order = current.map(SIGNAL_STRENGTH_ORDER).fillna(0)
    value_order = SIGNAL_STRENGTH_ORDER[value]
    return current.mask(mask & (value_order > current_order), value)


def build_for_year(year: int) -> pd.DataFrame | None:
    zip_path = RAW_DIR / f"consulta_cand_{year}.zip"
    if not zip_path.exists():
        print(f"Arquivo ausente, pulando: {zip_path}")
        return None

    print(f"Lendo {zip_path.name}...")
    df = read_candidate_zip(zip_path)
    available_columns = [column for column in PREFERRED_COLUMNS if column in df.columns]
    df = df[available_columns].copy()

    for column in TEXT_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    normalized_columns = {column: normalize_series(df[column]) for column in TEXT_COLUMNS}

    pattern_masks: dict[str, pd.Series] = {}
    matched_terms = pd.Series("", index=df.index)
    matched_fields = pd.Series("", index=df.index)
    signal_strength = pd.Series("", index=df.index)
    matched_categories: dict[str, pd.Series] = {}

    for category, strength, label, pattern in iter_christian_patterns():
        field_masks = {
            column: normalized_columns[column].str.contains(pattern, regex=True, na=False)
            for column in TEXT_COLUMNS
        }
        mask = pd.concat(field_masks.values(), axis=1).any(axis=1)
        pattern_masks[label] = mask
        matched_categories[category] = matched_categories.get(
            category,
            pd.Series(False, index=df.index),
        ) | mask
        matched_terms = append_unique(matched_terms, mask, label)
        signal_strength = strongest_strength(signal_strength, mask, strength)

        for column, field_mask in field_masks.items():
            matched_fields = append_unique(matched_fields, field_mask, column)

    has_signal = pd.concat(pattern_masks.values(), axis=1).any(axis=1)
    category_values, _ = compact_match_columns(matched_categories)

    status_column = "DS_SIT_TOT_TURNO"
    if status_column not in df.columns:
        status_column = "DS_SITUACAO_CANDIDATO_TOT"
    if status_column not in df.columns:
        df["DS_SIT_TOT_TURNO"] = ""
        status_column = "DS_SIT_TOT_TURNO"

    output = df.loc[has_signal].copy()
    output["SINAL_CRISTAO"] = True
    output["CATEGORIAS_CRISTAS"] = category_values.loc[has_signal]
    output["TERMOS_CRISTAOS"] = matched_terms.loc[has_signal]
    output["CAMPOS_SINAL_CRISTAO"] = matched_fields.loc[has_signal]
    output["FORCA_SINAL_CRISTAO"] = signal_strength.loc[has_signal]
    output["ELEITO"] = classify_elected(output[status_column])
    output["STATUS_RESULTADO"] = output[status_column].fillna("")
    output["ANO_ELEICAO_ANALISE"] = year
    return output


def write_outputs(frames: list[pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(frames, ignore_index=True)

    parquet_path = output_dir / "candidatos_cristaos_2012_2024.parquet"
    csv_path = output_dir / "candidatos_cristaos_2012_2024.csv"
    summary_path = output_dir / "resumo_candidatos_cristaos_2012_2024.csv"

    combined.to_parquet(parquet_path, index=False)
    combined.to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary = (
        combined.assign(total=1)
        .groupby(
            ["ANO_ELEICAO_ANALISE", "SG_UF", "DS_CARGO", "SG_PARTIDO", "ELEITO"],
            dropna=False,
        )["total"]
        .sum()
        .reset_index()
        .sort_values(["ANO_ELEICAO_ANALISE", "SG_UF", "DS_CARGO", "SG_PARTIDO", "ELEITO"])
    )
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print(parquet_path)
    print(csv_path)
    print(summary_path)
    print(f"Linhas: {len(combined):,}".replace(",", "."))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consolida candidaturas com sinais de relação com cristianismo."
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2012, 2014, 2016, 2018, 2020, 2022, 2024],
    )
    args = parser.parse_args()

    frames = []
    for year in args.years:
        frame = build_for_year(year)
        if frame is not None and not frame.empty:
            print(f"{year}: {len(frame):,} candidaturas com sinal cristão".replace(",", "."))
            frames.append(frame)
        elif frame is not None:
            print(f"{year}: nenhuma candidatura encontrada")

    if not frames:
        raise RuntimeError("Nenhuma candidatura com sinal cristão encontrada.")

    write_outputs(frames, PROCESSED_DIR)


if __name__ == "__main__":
    main()
