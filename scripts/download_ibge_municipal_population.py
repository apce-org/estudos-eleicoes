from __future__ import annotations

import argparse

import pandas as pd
import sidrapy

from religiao_politica.config import RAW_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa população municipal do IBGE/SIDRA para anos informados."
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2010, 2022],
        help="Anos de referência.",
    )
    args = parser.parse_args()

    frames = []
    for year in args.years:
        df = sidrapy.get_table(
            table_code="6579",
            territorial_level="6",
            ibge_territorial_code="all",
            period=str(year),
            variable="9324",
        )
        df = df.iloc[1:].copy()
        df["ano"] = year
        frames.append(df)

    output = RAW_DIR / "ibge_populacao_municipios_sidra.csv"
    pd.concat(frames, ignore_index=True).to_csv(output, index=False, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
