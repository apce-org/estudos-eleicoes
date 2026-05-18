from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
from unidecode import unidecode

from religiao_politica.config import PROCESSED_DIR, RAW_DIR
from religiao_politica.tse import download_campaign_finance_zip, read_zip_csvs


VALUE_COLUMNS_RECEIPTS = ["VR_RECEITA", "VALOR_RECEITA", "VR_RECEITA_ESTIMAVEL"]
VALUE_COLUMNS_EXPENSES = ["VR_DESPESA_CONTRATADA", "VR_PAGTO_DESPESA", "VR_DESPESA", "VALOR_DESPESA"]
CANDIDATE_ID_COLUMNS = ["SQ_CANDIDATO", "SEQUENCIAL_CANDIDATO", "SEQUENCIAL DO CANDIDATO", "SEQUENCIAL CANDIDATO"]
DONOR_COLUMNS = ["NR_CPF_CNPJ_DOADOR", "CPF_CNPJ_DOADOR", "CPF/CNPJ DO DOADOR", "NR_CPF_CNPJ_DOADOR_ORIGINARIO"]


def normalize_column(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", unidecode(value).upper()).strip("_")


def find_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {normalize_column(column): column for column in columns}
    for candidate in candidates:
        found = normalized.get(normalize_column(candidate))
        if found:
            return found
    return None


def money_to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.fillna("0").astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0.0)


def normalized_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
        .str.casefold()
    )


def add_bucket(sums: dict[str, pd.Series], key: str, ids: pd.Series, values: pd.Series) -> None:
    grouped = values.groupby(ids).sum()
    sums[key] = sums.get(key, pd.Series(dtype="float64")).add(grouped, fill_value=0)


def classify_receipts(chunk: pd.DataFrame, ids: pd.Series, values: pd.Series, sums: dict[str, pd.Series]) -> None:
    source_columns = [
        column
        for column in [
            "DS_ORIGEM_RECEITA",
            "DS_FONTE_RECEITA",
            "DS_ESPECIE_RECEITA",
            "DS_NATUREZA_RECEITA",
            "NM_DOADOR",
            "NM_DOADOR_ORIGINARIO",
        ]
        if column in chunk.columns
    ]
    text = normalized_text(chunk[source_columns].astype(str).agg(" ".join, axis=1)) if source_columns else pd.Series("", index=chunk.index)
    public_mask = text.str.contains("fundo especial|fefc|fundo partidario|direcao partidaria", na=False)
    person_mask = text.str.contains("pessoa fisica", na=False)
    own_mask = text.str.contains("recursos proprios", na=False)
    party_candidate_mask = text.str.contains("partido|candidato", na=False)
    estimated_mask = text.str.contains("estimavel", na=False)

    add_bucket(sums, "receita_total", ids, values)
    add_bucket(sums, "receita_publica", ids[public_mask], values[public_mask])
    add_bucket(sums, "receita_pessoa_fisica", ids[person_mask], values[person_mask])
    add_bucket(sums, "receita_recursos_proprios", ids[own_mask], values[own_mask])
    add_bucket(sums, "receita_partido_ou_candidato", ids[party_candidate_mask], values[party_candidate_mask])
    add_bucket(sums, "receita_estimavel", ids[estimated_mask], values[estimated_mask])


def find_finance_zip(year: int) -> Path:
    preferred = [
        RAW_DIR / f"prestacao_de_contas_eleitorais_candidatos_{year}.zip",
        RAW_DIR / f"prestacao_final_{year}.zip",
        RAW_DIR / f"prestacao_contas_final_sup_{year}.zip",
    ]
    for path in preferred:
        if path.exists():
            return path
    matches = sorted(path for path in RAW_DIR.glob(f"*{year}.zip") if "prestacao" in unidecode(path.name).casefold())
    if matches:
        return matches[0]
    return download_campaign_finance_zip(year)


def summarize_finance_year(year: int, candidate_ids: set[str]) -> pd.DataFrame:
    zip_path = find_finance_zip(year)
    sums: dict[str, pd.Series] = {}
    donor_sets: dict[str, set[str]] = defaultdict(set)

    for csv_name, reader in read_zip_csvs(zip_path, chunksize=250_000):
        normalized_name = Path(csv_name).name.upper()
        if "_BRASIL." in normalized_name or "_BR." in normalized_name:
            continue
        lower_name = unidecode(Path(csv_name).name).casefold()
        is_receipt_file = "receita" in lower_name or "receitas" in lower_name
        is_expense_file = "despesa" in lower_name or "despesas" in lower_name
        if not is_receipt_file and not is_expense_file:
            continue

        print(f"{year}: lendo {csv_name}")
        for chunk in reader:
            candidate_column = find_column(list(chunk.columns), CANDIDATE_ID_COLUMNS)
            if candidate_column is None:
                continue
            chunk[candidate_column] = chunk[candidate_column].astype(str)
            chunk = chunk[chunk[candidate_column].isin(candidate_ids)].copy()
            if chunk.empty:
                continue

            value_column = find_column(
                list(chunk.columns),
                VALUE_COLUMNS_RECEIPTS if is_receipt_file else VALUE_COLUMNS_EXPENSES,
            )
            if value_column is None:
                continue

            ids = chunk[candidate_column].astype(str)
            values = money_to_number(chunk[value_column])

            if is_receipt_file:
                classify_receipts(chunk, ids, values, sums)
                donor_column = find_column(list(chunk.columns), DONOR_COLUMNS)
                if donor_column:
                    donors = chunk[[candidate_column, donor_column]].dropna().drop_duplicates()
                    for candidate_id, donor in donors.itertuples(index=False):
                        if str(donor).strip():
                            donor_sets[str(candidate_id)].add(str(donor))
            else:
                key = "despesa_paga" if "paga" in lower_name or "pagas" in lower_name else "despesa_contratada"
                add_bucket(sums, key, ids, values)

    summary = pd.DataFrame(index=sorted(candidate_ids))
    for column, values in sums.items():
        summary[column] = values
    for column in [
        "despesa_contratada",
        "despesa_paga",
        "receita_total",
        "receita_publica",
        "receita_pessoa_fisica",
        "receita_recursos_proprios",
        "receita_partido_ou_candidato",
        "receita_estimavel",
    ]:
        if column not in summary.columns:
            summary[column] = 0.0
    summary = summary.fillna(0.0)
    summary["doadores_distintos"] = [len(donor_sets.get(candidate_id, set())) for candidate_id in summary.index]
    summary["ANO_ELEICAO_ANALISE"] = year
    summary.index.name = "SQ_CANDIDATO"
    return summary.reset_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume financiamento de todos os candidatos legislativos.")
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2014, 2016, 2018, 2020, 2022, 2024])
    args = parser.parse_args()

    candidates_path = PROCESSED_DIR / "candidatos_legislativos_2012_2024.parquet"
    if not candidates_path.exists():
        raise FileNotFoundError("Rode scripts/build_all_legislative_candidates_base.py antes.")
    candidates = pd.read_parquet(candidates_path)
    candidates["SQ_CANDIDATO"] = candidates["SQ_CANDIDATO"].astype(str)

    frames = []
    for year in args.years:
        year_candidates = candidates[candidates["ANO_ELEICAO_ANALISE"].astype(int).eq(year)]
        frame = summarize_finance_year(year, set(year_candidates["SQ_CANDIDATO"]))
        frames.append(frame)
        print(f"{year}: {len(frame):,} candidatos no resumo financeiro".replace(",", "."))

    finance = pd.concat(frames, ignore_index=True)
    info_columns = [
        "ANO_ELEICAO_ANALISE",
        "SQ_CANDIDATO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "SG_UF",
        "DS_CARGO",
        "ESFERA",
        "SG_PARTIDO",
        "IDEOLOGIA_PARTIDO",
        "ELEITO",
        "SINAL_CRISTAO",
        "FORCA_SINAL_CRISTAO",
        "TERMOS_CRISTAOS",
    ]
    finance = finance.merge(
        candidates[[column for column in info_columns if column in candidates.columns]],
        on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"],
        how="left",
    )

    parquet_path = PROCESSED_DIR / "candidatos_legislativos_financiamento_resumo.parquet"
    csv_path = PROCESSED_DIR / "candidatos_legislativos_financiamento_resumo.csv"
    finance.to_parquet(parquet_path, index=False)
    finance.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(parquet_path)
    print(csv_path)
    print(f"Linhas: {len(finance):,}".replace(",", "."))


if __name__ == "__main__":
    main()
