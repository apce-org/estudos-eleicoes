from __future__ import annotations

import pandas as pd

from religiao_politica.config import PROCESSED_DIR


def main() -> None:
    votes_path = PROCESSED_DIR / "candidatos_cristaos_votos_municipios_populacao.parquet"
    finance_path = PROCESSED_DIR / "candidatos_cristaos_financiamento_resumo.parquet"

    if not votes_path.exists():
        raise FileNotFoundError("Rode build_christian_votes_municipality_panel.py antes.")
    if not finance_path.exists():
        raise FileNotFoundError("Rode build_christian_campaign_finance_summary.py antes.")

    votes = pd.read_parquet(votes_path)
    finance = pd.read_parquet(finance_path)
    finance = finance.drop(
        columns=[
            column
            for column in [
                "NM_CANDIDATO",
                "NM_URNA_CANDIDATO",
                "SG_UF",
                "DS_CARGO",
                "SG_PARTIDO",
                "ELEITO",
                "FORCA_SINAL_CRISTAO",
                "TERMOS_CRISTAOS",
            ]
            if column in finance.columns
        ]
    )

    panel = votes.merge(finance, on=["ANO_ELEICAO_ANALISE", "SQ_CANDIDATO"], how="left")
    output_parquet = PROCESSED_DIR / "painel_candidatos_cristaos_votos_populacao_financiamento.parquet"
    output_csv = PROCESSED_DIR / "painel_candidatos_cristaos_votos_populacao_financiamento.csv"
    panel.to_parquet(output_parquet, index=False)
    panel.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print(output_parquet)
    print(output_csv)
    print(f"Linhas: {len(panel):,}".replace(",", "."))


if __name__ == "__main__":
    main()
