from __future__ import annotations

import time
import zipfile
from pathlib import Path
from unicodedata import normalize

import pandas as pd
import requests
from tqdm import tqdm

from religiao_politica.config import RAW_DIR, TSE_CANDIDATE_URL

TSE_CKAN_PACKAGE_URL = "https://dadosabertos.tse.jus.br/api/3/action/package_show"
TSE_IBGE_CODES_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/municipio_tse_ibge/"
    "municipio_tse_ibge.zip"
)


def is_valid_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    return zipfile.is_zipfile(path)


def download_file(
    url: str,
    destination: Path,
    retries: int = 3,
    validate_zip: bool | None = None,
) -> Path:
    if validate_zip is None:
        validate_zip = destination.suffix.lower() == ".zip"

    destination.parent.mkdir(parents=True, exist_ok=True)
    if validate_zip and is_valid_zip(destination):
        return destination
    if not validate_zip and destination.exists() and destination.stat().st_size > 0:
        return destination
    if destination.exists():
        destination.rename(destination.with_suffix(destination.suffix + ".part"))

    partial = destination.with_suffix(destination.suffix + ".part")

    for attempt in range(1, retries + 1):
        downloaded = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}

        try:
            with requests.get(url, headers=headers, stream=True, timeout=120) as response:
                if response.status_code == 416:
                    partial.rename(destination)
                    if not validate_zip or is_valid_zip(destination):
                        return destination
                    destination.unlink(missing_ok=True)
                    downloaded = 0
                    headers = {}
                    response = requests.get(url, headers=headers, stream=True, timeout=120)

                if downloaded and response.status_code == 200:
                    partial.unlink(missing_ok=True)
                    downloaded = 0

                response.raise_for_status()
                content_length = int(response.headers.get("content-length", 0))
                total = downloaded + content_length if content_length else 0

                with partial.open("ab") as file, tqdm(
                    total=total,
                    initial=downloaded,
                    unit="B",
                    unit_scale=True,
                    desc=destination.name,
                ) as progress:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            file.write(chunk)
                            progress.update(len(chunk))

            partial.rename(destination)
            if not validate_zip or is_valid_zip(destination):
                return destination

            destination.rename(partial)
            raise zipfile.BadZipFile(f"Download incompleto ou ZIP inválido: {destination}")
        except (requests.RequestException, zipfile.BadZipFile) as exc:
            if attempt == retries:
                raise RuntimeError(
                    f"Falha ao baixar {url} após {retries} tentativas. "
                    f"Arquivo parcial preservado em {partial}"
                ) from exc
            wait_seconds = 5 * attempt
            print(f"Tentativa {attempt} falhou. Nova tentativa em {wait_seconds}s...")
            time.sleep(wait_seconds)

    raise RuntimeError(f"Falha inesperada ao baixar {url}")


def normalize_label(value: str) -> str:
    text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.casefold().split())


def get_tse_resource_url(package_id: str, include_terms: list[str]) -> str:
    response = requests.get(TSE_CKAN_PACKAGE_URL, params={"id": package_id}, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"Pacote não encontrado no TSE: {package_id}")

    normalized_terms = [normalize_label(term) for term in include_terms]
    for resource in payload["result"]["resources"]:
        name = normalize_label(resource.get("name", ""))
        if all(term in name for term in normalized_terms):
            return resource["url"]

    available = [resource.get("name", "") for resource in payload["result"]["resources"]]
    raise RuntimeError(
        f"Recurso não encontrado em {package_id} com termos {include_terms}. "
        f"Disponíveis: {available}"
    )


def download_candidate_zip(year: int, raw_dir: Path = RAW_DIR) -> Path:
    url = TSE_CANDIDATE_URL.format(year=year)
    return download_file(url, raw_dir / f"consulta_cand_{year}.zip")


def download_vote_zip(year: int, raw_dir: Path = RAW_DIR) -> Path:
    url = get_tse_resource_url(f"resultados-{year}", ["votação nominal", "município", "zona"])
    return download_file(url, raw_dir / f"votacao_candidato_munzona_{year}.zip")


def download_campaign_finance_zip(year: int, raw_dir: Path = RAW_DIR) -> Path:
    terms = ["candidatos"]
    if year <= 2016:
        terms = ["prestação de contas final"]
    try:
        url = get_tse_resource_url(f"prestacao-de-contas-eleitorais-{year}", terms)
    except requests.HTTPError:
        if year <= 2016:
            url = (
                "https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
                f"prestacao_final_{year}.zip"
            )
        else:
            url = (
                "https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
                f"prestacao_de_contas_eleitorais_candidatos_{year}.zip"
            )
    filename = url.rsplit("/", 1)[-1]
    return download_file(url, raw_dir / filename)


def download_tse_ibge_municipality_codes(raw_dir: Path = RAW_DIR) -> Path:
    return download_file(TSE_IBGE_CODES_URL, raw_dir / "municipio_tse_ibge.zip")


def read_candidate_zip(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"Nenhum CSV encontrado em {zip_path}")
        frames = []
        for name in csv_names:
            with archive.open(name) as file:
                frames.append(
                    pd.read_csv(
                        file,
                        sep=";",
                        encoding="latin1",
                        dtype=str,
                        low_memory=False,
                    )
                )
    return pd.concat(frames, ignore_index=True)


def read_zip_csvs(zip_path: Path, chunksize: int | None = None):
    with zipfile.ZipFile(zip_path) as archive:
        csv_names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".csv", ".txt"))
        ]
        if not csv_names:
            raise FileNotFoundError(f"Nenhum CSV encontrado em {zip_path}")
        for name in csv_names:
            with archive.open(name) as file:
                reader = pd.read_csv(
                    file,
                    sep=";",
                    encoding="latin1",
                    dtype=str,
                    low_memory=False,
                    chunksize=chunksize,
                )
                yield name, reader
