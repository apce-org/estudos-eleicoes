from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from religiao_politica.analysis import LEGISLATIVE_OFFICES, add_analysis_dimensions
from religiao_politica.config import PROCESSED_DIR, RAW_DIR
from religiao_politica.religious_terms import SIGNAL_STRENGTH_ORDER, iter_christian_patterns
from religiao_politica.tse import download_tse_ibge_municipality_codes, read_zip_csvs


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


def read_tse_ibge_mapping() -> pd.DataFrame:
    zip_path = download_tse_ibge_municipality_codes()
    _, df = next(read_zip_csvs(zip_path))
    mapping = pd.DataFrame(
        {
            "SG_UF": df["SG_UF"],
            "SG_UE": df["CD_MUNICIPIO_TSE"].astype(str),
            "codigo_ibge_municipio": df["CD_MUNICIPIO_IBGE"].astype(str).str.zfill(7),
        }
    ).drop_duplicates(["SG_UF", "SG_UE"])
    boa_esperanca_norte = mapping["SG_UF"].eq("MT") & mapping["SG_UE"].eq("73709")
    mapping.loc[boa_esperanca_norte, "codigo_ibge_municipio"] = "5101837"
    return mapping


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


def append_unique(current: pd.Series, mask: pd.Series, value: str) -> pd.Series:
    return current.mask(mask, current.where(current.eq(""), current + ";") + value)


def strongest_strength(current: pd.Series, mask: pd.Series, value: str) -> pd.Series:
    current_order = current.map(SIGNAL_STRENGTH_ORDER).fillna(0)
    value_order = SIGNAL_STRENGTH_ORDER[value]
    return current.mask(mask & (value_order > current_order), value)


def classify_christian_signal(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    for column in TEXT_COLUMNS:
        if column not in output.columns:
            output[column] = ""

    normalized_columns = {column: normalize_series(output[column]) for column in TEXT_COLUMNS}
    matched_terms = pd.Series("", index=output.index)
    matched_fields = pd.Series("", index=output.index)
    signal_strength = pd.Series("", index=output.index)
    matched_categories: dict[str, pd.Series] = {}
    masks: list[pd.Series] = []

    for category, strength, label, pattern in iter_christian_patterns():
        field_masks = {
            column: normalized_columns[column].str.contains(pattern, regex=True, na=False)
            for column in TEXT_COLUMNS
        }
        mask = pd.concat(field_masks.values(), axis=1).any(axis=1)
        masks.append(mask)
        matched_categories[category] = matched_categories.get(
            category,
            pd.Series(False, index=output.index),
        ) | mask
        matched_terms = append_unique(matched_terms, mask, label)
        signal_strength = strongest_strength(signal_strength, mask, strength)
        for column, field_mask in field_masks.items():
            matched_fields = append_unique(matched_fields, field_mask, column)

    has_signal = pd.concat(masks, axis=1).any(axis=1) if masks else pd.Series(False, index=output.index)
    category_frame = pd.concat(
        [
            pd.Series(category, index=mask.index).where(mask, "")
            for category, mask in matched_categories.items()
        ],
        axis=1,
    )
    output["SINAL_CRISTAO"] = has_signal
    output["CATEGORIAS_CRISTAS"] = category_frame.apply(
        lambda row: ";".join(sorted({value for value in row if value})),
        axis=1,
    )
    output["TERMOS_CRISTAOS"] = matched_terms
    output["CAMPOS_SINAL_CRISTAO"] = matched_fields
    output["FORCA_SINAL_CRISTAO"] = signal_strength
    return output


def read_legislative_candidates_for_year(year: int, mapping: pd.DataFrame) -> pd.DataFrame:
    zip_path = RAW_DIR / f"consulta_cand_{year}.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"Arquivo ausente: {zip_path}")

    frames = []
    for csv_name, frame in read_zip_csvs(zip_path):
        normalized_name = Path(csv_name).name.upper()
        if "_BRASIL." in normalized_name or "_BR." in normalized_name:
            continue
        available = [column for column in PREFERRED_COLUMNS if column in frame.columns]
        partial = frame[available].copy()
        partial = partial[partial["DS_CARGO"].isin(LEGISLATIVE_OFFICES)].copy()
        if not partial.empty:
            frames.append(partial)

    if not frames:
        return pd.DataFrame()

    candidates = pd.concat(frames, ignore_index=True)
    candidates["ANO_ELEICAO_ANALISE"] = year
    status_column = "DS_SIT_TOT_TURNO"
    if status_column not in candidates.columns:
        status_column = "DS_SITUACAO_CANDIDATO_TOT"
    candidates["ELEITO"] = classify_elected(candidates.get(status_column, pd.Series("", index=candidates.index)))
    candidates["STATUS_RESULTADO"] = candidates.get(status_column, pd.Series("", index=candidates.index)).fillna("")
    candidates = classify_christian_signal(candidates)
    candidates = add_analysis_dimensions(candidates)
    candidates = candidates.merge(mapping, on=["SG_UF", "SG_UE"], how="left")
    return candidates.drop_duplicates(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria base de todos os candidatos legislativos com marcação de sinal cristão."
    )
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2014, 2016, 2018, 2020, 2022, 2024])
    args = parser.parse_args()

    mapping = read_tse_ibge_mapping()
    frames = []
    for year in args.years:
        print(f"Lendo candidaturas legislativas de {year}...")
        frame = read_legislative_candidates_for_year(year, mapping)
        frames.append(frame)
        print(f"{year}: {len(frame):,} candidaturas legislativas".replace(",", "."))

    all_candidates = pd.concat(frames, ignore_index=True)
    parquet_path = PROCESSED_DIR / "candidatos_legislativos_2012_2024.parquet"
    csv_path = PROCESSED_DIR / "candidatos_legislativos_2012_2024.csv"
    all_candidates.to_parquet(parquet_path, index=False)
    all_candidates.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(parquet_path)
    print(csv_path)
    print(f"Linhas: {len(all_candidates):,}".replace(",", "."))


if __name__ == "__main__":
    main()
