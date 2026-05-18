from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from unidecode import unidecode

from religiao_politica.config import PROCESSED_DIR


LEGISLATIVE_OFFICES = {
    "VEREADOR",
    "DEPUTADO ESTADUAL",
    "DEPUTADO DISTRITAL",
    "DEPUTADO FEDERAL",
    "SENADOR",
}

MUNICIPAL_OFFICES = {"VEREADOR"}
STATE_OFFICES = {"DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL"}
FEDERAL_OFFICES = {"DEPUTADO FEDERAL", "SENADOR"}

RIGHT_PARTIES = {
    "DEM",
    "NOVO",
    "PATRIOTA",
    "PL",
    "PMB",
    "PODE",
    "PP",
    "PR",
    "PRB",
    "PRD",
    "PRTB",
    "PSC",
    "PSD",
    "PSDB",
    "PSL",
    "PTB",
    "REPUBLICANOS",
    "UNIÃO",
    "UNIAO",
}
LEFT_PARTIES = {
    "PC DO B",
    "PCB",
    "PCO",
    "PDT",
    "PSB",
    "PSOL",
    "PSTU",
    "PT",
    "PV",
    "REDE",
    "SOLIDARIEDADE",
    "UP",
}


def normalize_text(value: Any) -> str:
    return unidecode(str(value or "")).strip().upper()


def classify_government_level(office: Any) -> str:
    office_name = normalize_text(office)
    if office_name in MUNICIPAL_OFFICES:
        return "municipal"
    if office_name in STATE_OFFICES:
        return "estadual"
    if office_name in FEDERAL_OFFICES:
        return "federal"
    return "outro"


def classify_party_ideology(party: Any) -> str:
    party_name = normalize_text(party)
    if party_name in RIGHT_PARTIES:
        return "direita"
    if party_name in LEFT_PARTIES:
        return "esquerda"
    return "centro_ou_indefinido"


def ensure_outputs_dir(path: Path | None = None) -> Path:
    output_dir = path or (PROCESSED_DIR.parent.parent / "outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def add_analysis_dimensions(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    output["DS_CARGO"] = output["DS_CARGO"].astype(str)
    output["ESFERA"] = output["DS_CARGO"].map(classify_government_level)
    output["IDEOLOGIA_PARTIDO"] = output["SG_PARTIDO"].map(classify_party_ideology)
    return output


def dedupe_candidates(df: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in ["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"] if column in df.columns]
    if len(columns) == 2:
        return df.drop_duplicates(columns).copy()
    return df.drop_duplicates().copy()


def safe_rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, np.nan)
    return numerator / denominator


def t_test_rows(
    df: pd.DataFrame,
    value_columns: Iterable[str],
    group_column: str,
    positive_value: Any,
    negative_value: Any,
    by: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in df.groupby(by, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_data = dict(zip(by, keys, strict=False))
        for column in value_columns:
            positive = pd.to_numeric(group.loc[group[group_column].eq(positive_value), column], errors="coerce").dropna()
            negative = pd.to_numeric(group.loc[group[group_column].eq(negative_value), column], errors="coerce").dropna()
            row = {
                **key_data,
                "variavel": column,
                "grupo_a": str(positive_value),
                "grupo_b": str(negative_value),
                "n_a": len(positive),
                "n_b": len(negative),
                "media_a": positive.mean() if len(positive) else np.nan,
                "media_b": negative.mean() if len(negative) else np.nan,
                "diferenca_media": (positive.mean() - negative.mean()) if len(positive) and len(negative) else np.nan,
            }
            if len(positive) >= 2 and len(negative) >= 2:
                test = stats.ttest_ind(positive, negative, equal_var=False, nan_policy="omit")
                row["teste"] = "t_welch"
                row["estatistica"] = float(test.statistic)
                row["p_valor"] = float(test.pvalue)
            else:
                row["teste"] = "t_welch"
                row["estatistica"] = np.nan
                row["p_valor"] = np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def anova_rows(df: pd.DataFrame, value_columns: Iterable[str], group_column: str, by: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in df.groupby(by, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_data = dict(zip(by, keys, strict=False))
        for column in value_columns:
            samples = [
                pd.to_numeric(part[column], errors="coerce").dropna()
                for _, part in group.groupby(group_column, dropna=False)
            ]
            samples = [sample for sample in samples if len(sample) >= 2]
            row = {
                **key_data,
                "variavel": column,
                "grupo": group_column,
                "n_grupos_validos": len(samples),
                "teste": "anova_um_fator",
            }
            if len(samples) >= 2:
                test = stats.f_oneway(*samples)
                row["estatistica"] = float(test.statistic)
                row["p_valor"] = float(test.pvalue)
            else:
                row["estatistica"] = np.nan
                row["p_valor"] = np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
