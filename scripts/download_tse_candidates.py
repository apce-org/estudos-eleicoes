from __future__ import annotations

import argparse

from religiao_politica.config import TSE_CANDIDATE_YEARS
from religiao_politica.tse import download_candidate_zip


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa arquivos de candidaturas do TSE.")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=TSE_CANDIDATE_YEARS,
        help="Anos eleitorais a baixar.",
    )
    args = parser.parse_args()

    for year in args.years:
        path = download_candidate_zip(year)
        print(f"{year}: {path}")


if __name__ == "__main__":
    main()
