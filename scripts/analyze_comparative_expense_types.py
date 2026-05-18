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


CANDIDATE_ID_COLUMNS = ["SQ_CANDIDATO", "SEQUENCIAL_CANDIDATO", "SEQUENCIAL CANDIDATO", "SEQUENCIAL DO CANDIDATO", "Sequencial Candidato"]
PRESTADOR_COLUMNS = ["SQ_PRESTADOR_CONTAS"]
EXPENSE_VALUE_COLUMNS = ["VR_DESPESA_CONTRATADA", "VR_PAGTO_DESPESA", "VR_DESPESA", "VALOR_DESPESA", "Valor despesa"]
EXPENSE_TYPE_COLUMNS = ["DS_ORIGEM_DESPESA", "Tipo despesa", "TIPO_DESPESA"]
EXPENSE_NATURE_COLUMNS = ["DS_NATUREZA_DESPESA", "DS_FONTE_DESPESA", "Setor econômico do fornecedor"]


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


def load_candidates() -> pd.DataFrame:
    path = PROCESSED_DIR / "candidatos_legislativos_2012_2024.parquet"
    if not path.exists():
        raise FileNotFoundError("Rode scripts/build_all_legislative_candidates_base.py antes.")
    df = pd.read_parquet(path)
    df["SQ_CANDIDATO"] = df["SQ_CANDIDATO"].astype(str)
    df["SINAL_CRISTAO"] = df["SINAL_CRISTAO"].fillna(False).astype(bool)
    df["ELEITO"] = df["ELEITO"].fillna(False).astype(bool)
    df = add_analysis_dimensions(df)
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
        "SINAL_CRISTAO",
        "FORCA_SINAL_CRISTAO",
        "TERMOS_CRISTAOS",
    ]
    return df[[column for column in keep if column in df.columns]].drop_duplicates(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"])


def file_matches(name: str, expense_kind: str) -> bool:
    lower = unidecode(Path(name).name).casefold()
    upper = Path(name).name.upper()
    if "_BRASIL." in upper or "_BR." in upper:
        return False
    if "despesa" not in lower and "despesas" not in lower:
        return False
    if "partidos" in lower or "comites" in lower:
        return False
    if expense_kind == "contratadas":
        return "contratada" in lower or "despesas_candidatos" in lower
    if expense_kind == "pagas":
        return "paga" in lower or "despesas_candidatos" in lower
    return True


def build_prestador_map(year: int, candidate_ids: set[str], zip_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for csv_name, reader in read_zip_csvs(zip_path, chunksize=300_000):
        name = Path(csv_name).name
        lower = unidecode(name).casefold()
        upper = name.upper()
        if "_BRASIL." in upper or "_BR." in upper:
            continue
        if not lower.startswith(f"receitas_candidatos_{year}") or "doador_originario" in lower:
            continue
        for chunk in reader:
            if "SQ_PRESTADOR_CONTAS" not in chunk.columns or "SQ_CANDIDATO" not in chunk.columns:
                continue
            partial = chunk[["SQ_PRESTADOR_CONTAS", "SQ_CANDIDATO"]].dropna().drop_duplicates()
            partial["SQ_CANDIDATO"] = partial["SQ_CANDIDATO"].astype(str)
            partial = partial[partial["SQ_CANDIDATO"].isin(candidate_ids)]
            mapping.update({str(p): str(c) for p, c in partial.itertuples(index=False, name=None)})
    return mapping


def extract_year(year: int, candidates: pd.DataFrame, expense_kind: str) -> pd.DataFrame:
    year_candidates = candidates[candidates["ANO_ELEICAO_ANALISE"].astype(int).eq(year)]
    candidate_ids = set(year_candidates["SQ_CANDIDATO"].astype(str))
    zip_path = find_finance_zip(year)
    prestador_map = build_prestador_map(year, candidate_ids, zip_path)
    frames = []
    for csv_name, reader in read_zip_csvs(zip_path, chunksize=300_000):
        if not file_matches(csv_name, expense_kind):
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
            filtered["SQ_CANDIDATO"] = filtered[candidate_column].astype(str)
            filtered["tipo_despesa"] = filtered[type_column].map(normalize_label)
            filtered["natureza_despesa"] = filtered[nature_column].map(normalize_label) if nature_column else "Sem classificação"
            frames.append(filtered[["SQ_CANDIDATO", "tipo_despesa", "natureza_despesa", "valor_despesa"]])
    if not frames:
        return pd.DataFrame(columns=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa", "natureza_despesa", "valor_despesa"])
    df = pd.concat(frames, ignore_index=True)
    df["ANO_ELEICAO_ANALISE"] = year
    return df


def build_base(expenses: pd.DataFrame, candidates: pd.DataFrame, expense_kind: str) -> pd.DataFrame:
    grouped = (
        expenses.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa", "natureza_despesa"], dropna=False)["valor_despesa"]
        .sum()
        .reset_index()
    )
    totals = grouped.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"])["valor_despesa"].sum().reset_index(name="despesa_total_candidato")
    grouped = grouped.merge(totals, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")
    grouped["pct_despesa_tipo"] = grouped["valor_despesa"] / grouped["despesa_total_candidato"].replace(0, np.nan)
    grouped["tipo_base_despesa"] = expense_kind
    return grouped.merge(candidates, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")


def compare_two_groups(
    base: pd.DataFrame,
    candidates: pd.DataFrame,
    group_column: str,
    group_a: Any,
    group_b: Any,
    label: str,
) -> pd.DataFrame:
    candidate_totals = (
        base.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], dropna=False)["despesa_total_candidato"].max().reset_index()
    )
    type_totals = (
        base.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa"], dropna=False)["valor_despesa"].sum().reset_index()
    )
    types = base[["ANO_ELEICAO_ANALISE", "ESFERA", "tipo_despesa"]].drop_duplicates()
    rows = []
    for year, sphere, expense_type in types.itertuples(index=False):
        universe = candidates[
            candidates["ANO_ELEICAO_ANALISE"].eq(year)
            & candidates["ESFERA"].eq(sphere)
            & candidates[group_column].isin([group_a, group_b])
        ][["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", group_column]].copy()
        if universe.empty:
            continue
        local = universe.merge(
            type_totals[type_totals["ANO_ELEICAO_ANALISE"].eq(year) & type_totals["tipo_despesa"].eq(expense_type)],
            on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"],
            how="left",
        )
        local = local.merge(candidate_totals, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")
        local["valor_despesa"] = local["valor_despesa"].fillna(0.0)
        local["despesa_total_candidato"] = local["despesa_total_candidato"].fillna(0.0)
        local["pct_despesa_tipo"] = (local["valor_despesa"] / local["despesa_total_candidato"].replace(0, np.nan)).fillna(0.0)
        for variable in ["valor_despesa", "pct_despesa_tipo"]:
            a = pd.to_numeric(local.loc[local[group_column].eq(group_a), variable], errors="coerce").dropna()
            b = pd.to_numeric(local.loc[local[group_column].eq(group_b), variable], errors="coerce").dropna()
            row = {
                "comparacao": label,
                "ANO_ELEICAO_ANALISE": year,
                "ESFERA": sphere,
                "tipo_despesa": expense_type,
                "variavel": variable,
                "grupo_a": str(group_a),
                "grupo_b": str(group_b),
                "n_a": len(a),
                "n_b": len(b),
                "media_a": a.mean() if len(a) else np.nan,
                "media_b": b.mean() if len(b) else np.nan,
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
    return pd.DataFrame(rows)


def compare_anova(base: pd.DataFrame, candidates: pd.DataFrame, group_column: str, label: str) -> pd.DataFrame:
    candidate_totals = base.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], dropna=False)["despesa_total_candidato"].max().reset_index()
    type_totals = base.groupby(["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", "tipo_despesa"], dropna=False)["valor_despesa"].sum().reset_index()
    types = base[["ANO_ELEICAO_ANALISE", "ESFERA", "tipo_despesa"]].drop_duplicates()
    rows = []
    for year, sphere, expense_type in types.itertuples(index=False):
        universe = candidates[candidates["ANO_ELEICAO_ANALISE"].eq(year) & candidates["ESFERA"].eq(sphere)][
            ["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO", group_column]
        ].copy()
        universe = universe[universe[group_column].isin(["direita", "centro_ou_indefinido", "esquerda"])]
        if universe.empty:
            continue
        local = universe.merge(
            type_totals[type_totals["ANO_ELEICAO_ANALISE"].eq(year) & type_totals["tipo_despesa"].eq(expense_type)],
            on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"],
            how="left",
        ).merge(candidate_totals, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")
        local["valor_despesa"] = local["valor_despesa"].fillna(0.0)
        local["despesa_total_candidato"] = local["despesa_total_candidato"].fillna(0.0)
        local["pct_despesa_tipo"] = (local["valor_despesa"] / local["despesa_total_candidato"].replace(0, np.nan)).fillna(0.0)
        for variable in ["valor_despesa", "pct_despesa_tipo"]:
            samples = [part[variable].dropna() for _, part in local.groupby(group_column) if len(part[variable].dropna()) >= 2]
            row = {"comparacao": label, "ANO_ELEICAO_ANALISE": year, "ESFERA": sphere, "tipo_despesa": expense_type, "variavel": variable, "teste": "anova_um_fator", "n_grupos_validos": len(samples)}
            if len(samples) >= 2:
                test = stats.f_oneway(*samples)
                row["estatistica"] = float(test.statistic)
                row["p_valor"] = float(test.pvalue)
            else:
                row["estatistica"] = np.nan
                row["p_valor"] = np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def make_top(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["variavel"].eq("pct_despesa_tipo") & df["p_valor"].lt(0.05) & df["diferenca_media"].notna()].copy()
    out["diferenca_abs"] = out["diferenca_media"].abs()
    return out.sort_values(["comparacao", "ANO_ELEICAO_ANALISE", "ESFERA", "diferenca_abs"], ascending=[True, True, True, False]).groupby(["comparacao", "ANO_ELEICAO_ANALISE", "ESFERA"], dropna=False).head(15).drop(columns="diferenca_abs")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara tipos de despesa entre cristãos/não cristãos e ideologias cristãs.")
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2014, 2016, 2018, 2020, 2022, 2024])
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--expense-kind", choices=["contratadas", "pagas", "todas"], default="contratadas")
    args = parser.parse_args()

    output_dir = ensure_outputs_dir(Path(args.output_dir))
    candidates = load_candidates()
    expenses = pd.concat([extract_year(year, candidates, args.expense_kind) for year in args.years], ignore_index=True)
    base = build_base(expenses, candidates, args.expense_kind)

    bases_dir = output_dir / "bases"
    bases_dir.mkdir(parents=True, exist_ok=True)
    write_csv(base, bases_dir / f"base_despesas_tipos_comparativa_{args.expense_kind}.csv")
    base.to_parquet(PROCESSED_DIR / f"despesas_tipos_comparativa_{args.expense_kind}.parquet", index=False)

    religion_tests = compare_two_groups(base, candidates, "SINAL_CRISTAO", True, False, "cristaos_vs_nao_cristaos")
    christian_candidates = candidates[candidates["SINAL_CRISTAO"]].copy()
    christian_base = base[base["SINAL_CRISTAO"]].copy()
    ideology_tests = pd.concat(
        [
            compare_two_groups(christian_base, christian_candidates, "IDEOLOGIA_PARTIDO", "direita", "esquerda", "cristaos_direita_vs_esquerda"),
            compare_two_groups(christian_base, christian_candidates, "IDEOLOGIA_PARTIDO", "direita", "centro_ou_indefinido", "cristaos_direita_vs_centro"),
            compare_two_groups(christian_base, christian_candidates, "IDEOLOGIA_PARTIDO", "esquerda", "centro_ou_indefinido", "cristaos_esquerda_vs_centro"),
        ],
        ignore_index=True,
    )
    ideology_anova = compare_anova(christian_base, christian_candidates, "IDEOLOGIA_PARTIDO", "cristaos_direita_centro_esquerda")

    write_csv(religion_tests, output_dir / f"testes_despesas_tipos_cristaos_vs_nao_cristaos_{args.expense_kind}.csv")
    write_csv(ideology_tests, output_dir / f"testes_despesas_tipos_cristaos_ideologia_pares_{args.expense_kind}.csv")
    write_csv(ideology_anova, output_dir / f"anova_despesas_tipos_cristaos_ideologia_{args.expense_kind}.csv")
    write_csv(make_top(pd.concat([religion_tests, ideology_tests], ignore_index=True)), output_dir / f"top_diferenciais_despesas_tipos_comparativos_{args.expense_kind}.csv")
    print("Análise comparativa de tipos de despesa concluída.")


if __name__ == "__main__":
    main()
