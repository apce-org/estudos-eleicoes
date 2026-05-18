from __future__ import annotations

import argparse

from religiao_politica.config import PROCESSED_DIR
from religiao_politica.ibge_population import build_municipal_population_panel


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa população municipal TCU/IBGE e, opcionalmente, PNAD municipal disponível."
    )
    parser.add_argument(
        "--tcu-years",
        nargs="+",
        default=["2012", "2014", "2016", "2018", "2020", "2021", "2022", "2024"],
        help="Anos da tabela 6579 do SIDRA. Para 2022, o script usa a tabela 4714 do Censo.",
    )
    parser.add_argument(
        "--pnad-periods",
        nargs="*",
        default=None,
        help="Trimestres PNAD no formato AAAATT, por exemplo 202403. Use 'last' para o último.",
    )
    args = parser.parse_args()

    pnad_periods = args.pnad_periods
    if pnad_periods == []:
        pnad_periods = "last"

    df = build_municipal_population_panel(args.tcu_years, pnad_periods)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    parquet_path = PROCESSED_DIR / "populacao_municipios_ibge_tcu_pnad.parquet"
    csv_path = PROCESSED_DIR / "populacao_municipios_ibge_tcu_pnad.csv"
    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(parquet_path)
    print(csv_path)
    print(f"Linhas: {len(df):,}".replace(",", "."))


if __name__ == "__main__":
    main()
