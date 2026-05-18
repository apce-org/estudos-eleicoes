from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from unidecode import unidecode

from religiao_politica.analysis import add_analysis_dimensions, ensure_outputs_dir, write_csv
from religiao_politica.config import PROCESSED_DIR, RAW_DIR
from religiao_politica.tse import download_campaign_finance_zip, read_zip_csvs


CANDIDATE_ID_COLUMNS = [
    "SQ_CANDIDATO",
    "SEQUENCIAL_CANDIDATO",
    "SEQUENCIAL CANDIDATO",
    "SEQUENCIAL DO CANDIDATO",
    "Sequencial Candidato",
]
PRESTADOR_COLUMNS = ["SQ_PRESTADOR_CONTAS"]
EXPENSE_VALUE_COLUMNS = [
    "VR_DESPESA_CONTRATADA",
    "VR_PAGTO_DESPESA",
    "VR_DESPESA",
    "VALOR_DESPESA",
    "Valor despesa",
]
EXPENSE_TYPE_COLUMNS = [
    "DS_ORIGEM_DESPESA",
    "Tipo despesa",
    "TIPO_DESPESA",
]
EXPENSE_NATURE_COLUMNS = [
    "DS_NATUREZA_DESPESA",
    "DS_FONTE_DESPESA",
    "Setor econômico do fornecedor",
    "SETOR ECONOMICO DO FORNECEDOR",
]


def normalize_column(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", unidecode(value).upper()).strip("_")


def normalize_label(value: Any) -> str:
    text = unidecode(str(value or "")).strip()
    text = re.sub(r"\s+", " ", text)
    return text if text and text.upper() not in {"#NULO", "#NE#", "NAN"} else "Sem classificação"


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


def load_christian_candidates() -> pd.DataFrame:
    path = PROCESSED_DIR / "candidatos_legislativos_2012_2024.parquet"
    if not path.exists():
        raise FileNotFoundError("Rode scripts/build_all_legislative_candidates_base.py antes.")
    candidates = pd.read_parquet(path)
    candidates["SQ_CANDIDATO"] = candidates["SQ_CANDIDATO"].astype(str)
    candidates = candidates[candidates["SINAL_CRISTAO"].fillna(False)].copy()
    candidates = add_analysis_dimensions(candidates)
    keep = [
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
        "FORCA_SINAL_CRISTAO",
        "TERMOS_CRISTAOS",
    ]
    return candidates[[column for column in keep if column in candidates.columns]].drop_duplicates(
        ["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"]
    )


def expense_file_matches(name: str, expense_kind: str) -> bool:
    lower_name = unidecode(Path(name).name).casefold()
    upper_name = Path(name).name.upper()
    if "_BRASIL." in upper_name or "_BR." in upper_name:
        return False
    if "despesa" not in lower_name and "despesas" not in lower_name:
        return False
    if "partidos" in lower_name or "comites" in lower_name:
        return False
    if expense_kind == "contratadas":
        return "contratada" in lower_name or "despesas_candidatos" in lower_name
    if expense_kind == "pagas":
        return "paga" in lower_name or "despesas_candidatos" in lower_name
    return True


def build_prestador_to_candidate_map(year: int, candidate_ids: set[str], zip_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for csv_name, reader in read_zip_csvs(zip_path, chunksize=250_000):
        name = Path(csv_name).name
        lower_name = unidecode(name).casefold()
        upper_name = name.upper()
        if "_BRASIL." in upper_name or "_BR." in upper_name:
            continue
        if not lower_name.startswith(f"receitas_candidatos_{year}") or "doador_originario" in lower_name:
            continue
        for chunk in reader:
            if "SQ_PRESTADOR_CONTAS" not in chunk.columns or "SQ_CANDIDATO" not in chunk.columns:
                continue
            partial = chunk[["SQ_PRESTADOR_CONTAS", "SQ_CANDIDATO"]].dropna().drop_duplicates()
            partial["SQ_CANDIDATO"] = partial["SQ_CANDIDATO"].astype(str)
            partial = partial[partial["SQ_CANDIDATO"].isin(candidate_ids)]
            mapping.update(
                {
                    str(prestador): str(candidate)
                    for prestador, candidate in partial.itertuples(index=False, name=None)
                }
            )
    return mapping


def extract_year_expenses(
    year: int,
    candidates: pd.DataFrame,
    expense_kind: str,
) -> pd.DataFrame:
    year_candidates = candidates[candidates["ANO_ELEICAO_ANALISE"].astype(int).eq(year)].copy()
    candidate_ids = set(year_candidates["SQ_CANDIDATO"].astype(str))
    zip_path = find_finance_zip(year)
    prestador_map = build_prestador_to_candidate_map(year, candidate_ids, zip_path)

    frames = []
    for csv_name, reader in read_zip_csvs(zip_path, chunksize=250_000):
        if not expense_file_matches(csv_name, expense_kind):
            continue
        print(f"{year}: lendo {csv_name}")
        for chunk in reader:
            value_column = find_column(list(chunk.columns), EXPENSE_VALUE_COLUMNS)
            type_column = find_column(list(chunk.columns), EXPENSE_TYPE_COLUMNS)
            nature_column = find_column(list(chunk.columns), EXPENSE_NATURE_COLUMNS)
            if value_column is None or type_column is None:
                continue

            candidate_column = find_column(list(chunk.columns), CANDIDATE_ID_COLUMNS)
            if candidate_column is None:
                prestador_column = find_column(list(chunk.columns), PRESTADOR_COLUMNS)
                if prestador_column is None or not prestador_map:
                    continue
                chunk["SQ_CANDIDATO_ANALISE"] = chunk[prestador_column].astype(str).map(prestador_map)
                candidate_column = "SQ_CANDIDATO_ANALISE"

            chunk[candidate_column] = chunk[candidate_column].astype(str)
            filtered = chunk[chunk[candidate_column].isin(candidate_ids)].copy()
            if filtered.empty:
                continue

            filtered["valor_despesa"] = money_to_number(filtered[value_column])
            filtered = filtered[filtered["valor_despesa"].gt(0)]
            if filtered.empty:
                continue

            filtered["tipo_despesa"] = filtered[type_column].map(normalize_label)
            filtered["natureza_despesa"] = (
                filtered[nature_column].map(normalize_label) if nature_column else "Sem classificação"
            )
            filtered["SQ_CANDIDATO"] = filtered[candidate_column].astype(str)
            frames.append(
                filtered[
                    [
                        "SQ_CANDIDATO",
                        "tipo_despesa",
                        "natureza_despesa",
                        "valor_despesa",
                    ]
                ]
            )

    if not frames:
        return pd.DataFrame(
            columns=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa", "natureza_despesa", "valor_despesa"]
        )
    expenses = pd.concat(frames, ignore_index=True)
    expenses["ANO_ELEICAO_ANALISE"] = year
    return expenses


def build_candidate_type_base(expenses: pd.DataFrame, candidates: pd.DataFrame, expense_kind: str) -> pd.DataFrame:
    if expenses.empty:
        return pd.DataFrame()
    grouped = (
        expenses.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa", "natureza_despesa"], dropna=False)[
            "valor_despesa"
        ]
        .sum()
        .reset_index()
    )
    totals = (
        grouped.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], dropna=False)["valor_despesa"]
        .sum()
        .reset_index(name="despesa_total_candidato")
    )
    grouped = grouped.merge(totals, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")
    grouped["pct_despesa_tipo"] = grouped["valor_despesa"] / grouped["despesa_total_candidato"].replace(0, np.nan)
    grouped["tipo_base_despesa"] = expense_kind
    return grouped.merge(candidates, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")


def make_candidate_type_matrix(base: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    observed_types = base[["ANO_ELEICAO_ANALISE", "ESFERA", "tipo_despesa"]].drop_duplicates()
    candidate_keys = candidates[
        ["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "ESFERA", "ELEITO"]
    ].drop_duplicates()
    grids = []
    for (year, sphere), type_group in observed_types.groupby(["ANO_ELEICAO_ANALISE", "ESFERA"], dropna=False):
        local_candidates = candidate_keys[
            candidate_keys["ANO_ELEICAO_ANALISE"].eq(year) & candidate_keys["ESFERA"].eq(sphere)
        ]
        if local_candidates.empty:
            continue
        grid = local_candidates.merge(type_group[["tipo_despesa"]], how="cross")
        grids.append(grid)
    if not grids:
        return pd.DataFrame()

    matrix = pd.concat(grids, ignore_index=True)
    candidate_totals = (
        base.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], dropna=False)["despesa_total_candidato"]
        .max()
        .reset_index()
    )
    type_totals = (
        base.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa"], dropna=False)["valor_despesa"]
        .sum()
        .reset_index()
    )
    matrix = matrix.merge(type_totals, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa"], how="left")
    matrix = matrix.merge(candidate_totals, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")
    matrix["valor_despesa"] = matrix["valor_despesa"].fillna(0.0)
    matrix["despesa_total_candidato"] = matrix["despesa_total_candidato"].fillna(0.0)
    matrix["pct_despesa_tipo"] = matrix["valor_despesa"] / matrix["despesa_total_candidato"].replace(0, np.nan)
    matrix["pct_despesa_tipo"] = matrix["pct_despesa_tipo"].fillna(0.0)
    return matrix


def summarize_and_test(matrix: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = (
        matrix.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "tipo_despesa", "ELEITO"], dropna=False)
        .agg(
            candidatos=("SQ_CANDIDATO", "nunique"),
            candidatos_com_gasto=("valor_despesa", lambda s: int((s > 0).sum())),
            gasto_total=("valor_despesa", "sum"),
            gasto_medio=("valor_despesa", "mean"),
            gasto_mediano=("valor_despesa", "median"),
            pct_medio=("pct_despesa_tipo", "mean"),
            pct_mediano=("pct_despesa_tipo", "median"),
        )
        .reset_index()
    )

    rows = []
    for keys, group in matrix.groupby(["ANO_ELEICAO_ANALISE", "ESFERA", "tipo_despesa"], dropna=False):
        year, sphere, expense_type = keys
        elected = group[group["ELEITO"].fillna(False)]
        defeated = group[~group["ELEITO"].fillna(False)]
        for variable in ["valor_despesa", "pct_despesa_tipo"]:
            a = pd.to_numeric(elected[variable], errors="coerce").dropna()
            b = pd.to_numeric(defeated[variable], errors="coerce").dropna()
            row = {
                "ANO_ELEICAO_ANALISE": year,
                "ESFERA": sphere,
                "tipo_despesa": expense_type,
                "variavel": variable,
                "n_eleitos": len(a),
                "n_derrotados": len(b),
                "media_eleitos": a.mean() if len(a) else np.nan,
                "media_derrotados": b.mean() if len(b) else np.nan,
                "diferenca_media": (a.mean() - b.mean()) if len(a) and len(b) else np.nan,
                "teste": "t_welch",
            }
            if len(a) >= 2 and len(b) >= 2:
                test = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
                row["estatistica"] = float(test.statistic)
                row["p_valor"] = float(test.pvalue)
            else:
                row["estatistica"] = np.nan
                row["p_valor"] = np.nan
            rows.append(row)

    tests = pd.DataFrame(rows)
    top = tests[
        tests["variavel"].eq("pct_despesa_tipo")
        & tests["p_valor"].lt(0.05)
        & tests["diferenca_media"].notna()
    ].copy()
    top["diferenca_abs"] = top["diferenca_media"].abs()
    top = top.sort_values(["ANO_ELEICAO_ANALISE", "ESFERA", "diferenca_abs"], ascending=[True, True, False])
    top = top.groupby(["ANO_ELEICAO_ANALISE", "ESFERA"], dropna=False).head(15).drop(columns="diferenca_abs")
    return summary, tests, top


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analisa tipos de despesa que diferenciam candidatos cristãos eleitos e não eleitos."
    )
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2014, 2016, 2018, 2020, 2022, 2024])
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument(
        "--expense-kind",
        choices=["contratadas", "pagas", "todas"],
        default="contratadas",
        help="Usa despesas contratadas por padrão para representar a estrutura de campanha.",
    )
    args = parser.parse_args()

    output_dir = ensure_outputs_dir(Path(args.output_dir))
    candidates = load_christian_candidates()
    frames = []
    for year in args.years:
        frame = extract_year_expenses(year, candidates, args.expense_kind)
        frames.append(frame)

    expenses = pd.concat(frames, ignore_index=True)
    base = build_candidate_type_base(expenses, candidates, args.expense_kind)
    matrix = make_candidate_type_matrix(base, candidates)
    summary, tests, top = summarize_and_test(matrix)

    bases_dir = output_dir / "bases"
    bases_dir.mkdir(parents=True, exist_ok=True)
    base_path = bases_dir / f"base_despesas_tipos_cristaos_{args.expense_kind}.csv"
    write_csv(base, base_path)
    write_csv(summary, output_dir / f"despesas_tipos_cristaos_resumo_eleitos_vs_derrotados_{args.expense_kind}.csv")
    write_csv(tests, output_dir / f"testes_despesas_tipos_cristaos_eleitos_vs_derrotados_{args.expense_kind}.csv")
    write_csv(top, output_dir / f"top_diferenciais_despesas_tipos_cristaos_{args.expense_kind}.csv")

    parquet_path = PROCESSED_DIR / f"despesas_tipos_cristaos_{args.expense_kind}.parquet"
    base.to_parquet(parquet_path, index=False)
    print(base_path)
    print(parquet_path)
    print(f"Linhas candidato-tipo: {len(base):,}".replace(",", "."))
    print("Análise de tipos de despesa concluída.")


if __name__ == "__main__":
    main()
