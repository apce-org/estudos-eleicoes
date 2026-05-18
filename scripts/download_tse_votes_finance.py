from __future__ import annotations

import argparse

from religiao_politica.tse import (
    download_campaign_finance_zip,
    download_tse_ibge_municipality_codes,
    download_vote_zip,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa votação nominal, prestação de contas e correspondência TSE-IBGE."
    )
    parser.add_argument("--years", nargs="+", type=int, default=[2012, 2014, 2016, 2018, 2020, 2022, 2024])
    parser.add_argument("--skip-votes", action="store_true")
    parser.add_argument("--skip-finance", action="store_true")
    args = parser.parse_args()

    print(download_tse_ibge_municipality_codes())

    for year in args.years:
        if not args.skip_votes:
            print(f"{year} votos: {download_vote_zip(year)}")
        if not args.skip_finance:
            print(f"{year} prestação: {download_campaign_finance_zip(year)}")


if __name__ == "__main__":
    main()
