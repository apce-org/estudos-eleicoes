from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from religiao_politica.config import PROCESSED_DIR, PROJECT_ROOT, RAW_DIR


DEFAULT_SUBJECT = "Propaganda Política - Propaganda Eleitoral - Bem Público"
OUTPUT_NAME = "amostra_processos_propaganda_bens_publicos.csv"
SUMMARY_NAME = "resumo_amostra_processos_propaganda_bens_publicos.csv"


def parse_year(path: Path) -> int:
    match = re.search(r"processo_eleitoral_(\d{4})\.csv$", path.name)
    if not match:
        raise ValueError(f"Não foi possível identificar o ano em {path.name}")
    return int(match.group(1))


def read_process_file(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        sep=";",
        encoding="latin1",
        dtype=str,
        low_memory=False,
    )


def sample_year(
    path: Path,
    subject: str,
    sample_size: int,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, object]]:
    year = parse_year(path)
    df = read_process_file(path)

    if "DS_ASSUNTO_PRINCIPAL" not in df.columns:
        raise ValueError(f"Coluna DS_ASSUNTO_PRINCIPAL ausente em {path}")

    filtered = df[df["DS_ASSUNTO_PRINCIPAL"].fillna("").eq(subject)].copy()
    population_size = len(filtered)
    selected_size = min(sample_size, population_size)

    if selected_size:
        sample = filtered.sample(
            n=selected_size,
            replace=False,
            random_state=seed + year,
        ).copy()
    else:
        sample = filtered.copy()

    sample.insert(0, "ANO_AMOSTRA", year)
    sample.insert(1, "FONTE_ARQUIVO", path.name)
    sample.insert(2, "ASSUNTO_FILTRO", subject)
    sample.insert(3, "TAMANHO_POPULACAO_ANO", population_size)
    sample.insert(4, "TAMANHO_AMOSTRA_PLANEJADO", sample_size)
    sample.insert(5, "AMOSTRA_CENSITARIA_ANO", population_size < sample_size)
    sample.insert(6, "SEED_BASE", seed)

    sample = sample.reset_index(drop=True)
    sample.insert(7, "ORDEM_ALEATORIA_ANO", sample.index + 1)

    summary = {
        "ano": year,
        "arquivo": path.name,
        "assunto_filtro": subject,
        "processos_no_assunto": population_size,
        "amostra_planejada": sample_size,
        "processos_amostrados": selected_size,
        "amostra_censitaria": population_size < sample_size,
        "seed_base": seed,
        "seed_ano": seed + year,
    }
    return sample, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cria amostra reprodutível de processos sobre propaganda eleitoral "
            "em bem público, a partir dos arquivos processo_eleitoral_[ano].csv."
        )
    )
    parser.add_argument("--years", nargs="+", type=int, default=None)
    parser.add_argument("--sample-size", type=int, default=385)
    parser.add_argument("--seed", type=int, default=20260511)
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    args = parser.parse_args()

    files = sorted(RAW_DIR.glob("processo_eleitoral_*.csv"))
    if args.years:
        wanted = set(args.years)
        files = [path for path in files if parse_year(path) in wanted]

    if not files:
        raise FileNotFoundError("Nenhum arquivo processo_eleitoral_[ano].csv encontrado em data/raw.")

    samples: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []

    for path in files:
        print(f"Lendo {path.name}...")
        sample, summary = sample_year(
            path=path,
            subject=args.subject,
            sample_size=args.sample_size,
            seed=args.seed,
        )
        samples.append(sample)
        summaries.append(summary)
        print(
            f"{summary['ano']}: {summary['processos_amostrados']} de "
            f"{summary['processos_no_assunto']} processos no assunto"
        )

    output = pd.concat(samples, ignore_index=True)
    summary_df = pd.DataFrame(summaries).sort_values("ano")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    outputs_bases_dir = PROJECT_ROOT / "outputs" / "bases"
    outputs_bases_dir.mkdir(parents=True, exist_ok=True)

    processed_output = PROCESSED_DIR / OUTPUT_NAME
    bases_output = outputs_bases_dir / OUTPUT_NAME
    summary_output = PROJECT_ROOT / "outputs" / SUMMARY_NAME

    output.to_csv(processed_output, index=False, encoding="utf-8-sig")
    output.to_csv(bases_output, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_output, index=False, encoding="utf-8-sig")

    print(processed_output)
    print(bases_output)
    print(summary_output)
    print(f"Linhas: {len(output)}")


if __name__ == "__main__":
    main()
