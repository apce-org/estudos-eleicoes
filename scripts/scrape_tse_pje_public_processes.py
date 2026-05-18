from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import pandas as pd

from religiao_politica.config import INTERIM_DIR, PROCESSED_DIR, PROJECT_ROOT


BASE_URL = "https://consultaunificadapje.tse.jus.br/#/public/resultado/{process_number}"
DEFAULT_INPUT = PROCESSED_DIR / "amostra_processos_propaganda_bens_publicos.csv"
DEFAULT_OUTPUT_DIR = INTERIM_DIR / "tse_pje_processos_bens_publicos"
STATUS_FILE = "status_scraping_processos_pje.csv"
DOCUMENT_TEXT_RE = re.compile(r"senten[cç]a|decis[aã]o|inteiro\s+teor|documento", re.IGNORECASE)
SENTENCE_TEXT_RE = re.compile(r"senten[cç]a", re.IGNORECASE)
CAPTCHA_ERROR_RE = re.compile(r"erro\s+ao\s+validar\s+desafio|tente\s+novamente", re.IGNORECASE)
TEXT_CAPTCHA_RE = re.compile(
    r"qual\s+c[oó]digo\s+aparece\s+na\s+imagem|visitante\s+humano|support\s+id",
    re.IGNORECASE,
)


def safe_process_id(process_number: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", str(process_number)).strip("_")


def require_playwright() -> None:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Playwright não está instalado. Rode:\n"
            ".\\.venv\\Scripts\\python.exe -m pip install playwright\n"
            ".\\.venv\\Scripts\\python.exe -m playwright install chromium"
        ) from exc


def load_process_numbers(input_path: Path, limit: int | None) -> pd.DataFrame:
    df = pd.read_csv(input_path, dtype=str)
    if "NR_PROCESSO" not in df.columns:
        raise ValueError(f"Coluna NR_PROCESSO ausente em {input_path}")

    df = df[df["NR_PROCESSO"].notna()].copy()
    df["NR_PROCESSO"] = df["NR_PROCESSO"].astype(str).str.strip()
    df = df[df["NR_PROCESSO"].ne("")]
    df = df.drop_duplicates(subset=["NR_PROCESSO"], keep="first").reset_index(drop=True)

    if limit:
        df = df.head(limit).copy()
    return df


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def get_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=5_000)
    except Exception:
        return ""


def has_captcha(body_text: str) -> bool:
    markers = [
        "Sou humano",
        "Favor clicar abaixo",
        "hCaptcha",
        "Privacidade - Termos e Condições",
        "Esta pergunta é para testar se você é um visitante humano",
        "Qual código aparece na imagem?",
        "Seu Support ID",
    ]
    text = body_text or ""
    return any(marker.lower() in text.lower() for marker in markers)


def has_captcha_validation_error(body_text: str) -> bool:
    return bool(CAPTCHA_ERROR_RE.search(body_text or ""))


def has_text_captcha(body_text: str) -> bool:
    return bool(TEXT_CAPTCHA_RE.search(body_text or ""))


def dismiss_captcha_validation_error(page) -> bool:
    for locator in [
        page.get_by_role("button", name=re.compile(r"^ok$", re.IGNORECASE)),
        page.locator("button").filter(has_text=re.compile(r"^ok$", re.IGNORECASE)),
    ]:
        try:
            if locator.count():
                locator.first.click(timeout=3_000)
                return True
        except Exception:
            continue
    return False


def wait_for_manual_captcha(page, process_number: str) -> bool:
    body_text = get_body_text(page)
    if not has_captcha(body_text):
        return not has_captcha_validation_error(body_text)

    print()
    print(f"CAPTCHA detectado no processo {process_number}.")
    print("Resolva o CAPTCHA na janela do navegador.")
    print("Se aparecer o CAPTCHA textual, digite o código da imagem no site e clique em submit.")
    answer = input("Depois pressione Enter aqui. Digite 's' para pular este processo: ").strip().lower()
    if answer == "s":
        return False

    body_text = get_body_text(page)
    if has_captcha_validation_error(body_text):
        print("O TSE retornou erro ao validar desafio. Vou fechar o aviso e recarregar o processo.")
        dismiss_captcha_validation_error(page)
        return False

    for _ in range(12):
        time.sleep(2)
        body_text = get_body_text(page)
        if has_captcha_validation_error(body_text):
            print("O TSE retornou erro ao validar desafio. Vou fechar o aviso e recarregar o processo.")
            dismiss_captcha_validation_error(page)
            return False
        if not has_captcha(body_text):
            return True

    print("O CAPTCHA ainda parece estar presente.")
    return False


def collect_document_candidates(page) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    locators = [
        ("a", page.locator("a")),
        ("button", page.locator("button")),
        ("[role='button']", page.locator("[role='button']")),
    ]

    for kind, locator in locators:
        try:
            count = locator.count()
        except Exception:
            continue

        for index in range(count):
            item = locator.nth(index)
            try:
                text = item.inner_text(timeout=1_000).strip()
            except Exception:
                text = ""

            if not text or not DOCUMENT_TEXT_RE.search(text):
                continue

            href = ""
            try:
                href = item.get_attribute("href", timeout=1_000) or ""
            except Exception:
                href = ""

            candidates.append(
                {
                    "elemento": kind,
                    "indice": str(index),
                    "texto": re.sub(r"\s+", " ", text),
                    "href": href,
                }
            )
    return candidates


def choose_sentence_candidate(candidates: list[dict[str, str]]) -> dict[str, str] | None:
    sentence_candidates = [candidate for candidate in candidates if SENTENCE_TEXT_RE.search(candidate["texto"])]
    if sentence_candidates:
        return sentence_candidates[0]
    return candidates[0] if candidates else None


def click_candidate(page, candidate: dict[str, str]):
    kind = candidate["elemento"]
    index = int(candidate["indice"])
    locator = page.locator(kind).nth(index)

    popup = None
    try:
        with page.expect_popup(timeout=5_000) as popup_info:
            locator.click(timeout=5_000)
        popup = popup_info.value
        popup.wait_for_load_state("networkidle", timeout=30_000)
        return popup
    except Exception:
        try:
            locator.click(timeout=5_000)
            page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception:
            return None
    return page


def scrape_process(
    page,
    process_row: pd.Series,
    output_dir: Path,
    open_sentence: bool,
    captcha_retries: int,
) -> dict[str, object]:
    process_number = process_row["NR_PROCESSO"]
    process_id = safe_process_id(process_number)
    url = BASE_URL.format(process_number=process_number)
    process_dir = output_dir / process_id

    status: dict[str, object] = {
        "nr_processo": process_number,
        "url": url,
        "status": "iniciado",
        "captcha_detectado": False,
        "captcha_textual_detectado": False,
        "captcha_validado": False,
        "candidatos_documento": 0,
        "documento_aberto": False,
        "documento_texto": "",
        "erro": "",
    }

    try:
        captcha_ok = False
        for attempt in range(1, captcha_retries + 1):
            page.goto(url, wait_until="networkidle", timeout=60_000)
            body_text = get_body_text(page)
            status["captcha_detectado"] = status["captcha_detectado"] or has_captcha(body_text)
            status["captcha_textual_detectado"] = status["captcha_textual_detectado"] or has_text_captcha(body_text)
            captcha_ok = wait_for_manual_captcha(page, process_number)
            if captcha_ok:
                break
            if attempt < captcha_retries:
                print(f"Recarregando {process_number} para nova tentativa de CAPTCHA...")

        status["captcha_validado"] = captcha_ok
        if not captcha_ok:
            status["status"] = "captcha_pendente"
            status["erro"] = "CAPTCHA não validado; processo pulado."
            write_text(process_dir / "pagina_captcha_pendente.txt", get_body_text(page))
            return status

        page.wait_for_load_state("networkidle", timeout=30_000)

        html = page.content()
        body_text = get_body_text(page)
        write_text(process_dir / "pagina_principal.html", html)
        write_text(process_dir / "pagina_principal.txt", body_text)

        candidates = collect_document_candidates(page)
        status["candidatos_documento"] = len(candidates)
        pd.DataFrame(candidates).to_csv(
            process_dir / "candidatos_documento.csv",
            index=False,
            encoding="utf-8-sig",
        )

        if open_sentence and candidates:
            candidate = choose_sentence_candidate(candidates)
            status["documento_texto"] = candidate["texto"] if candidate else ""
            document_page = click_candidate(page, candidate) if candidate else None
            if document_page is not None:
                document_page.wait_for_load_state("networkidle", timeout=30_000)
                write_text(process_dir / "documento_aberto.html", document_page.content())
                write_text(process_dir / "documento_aberto.txt", get_body_text(document_page))
                status["documento_aberto"] = True
                if document_page is not page:
                    document_page.close()

        status["status"] = "ok"
    except Exception as exc:
        status["status"] = "erro"
        status["erro"] = repr(exc)

    return status


def main() -> None:
    require_playwright()

    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(
        description=(
            "Abre processos da Consulta Pública Unificada do PJe/TSE com CAPTCHA manual "
            "e salva HTML/texto para análise posterior."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--headful", action="store_true", default=True)
    parser.add_argument("--open-sentence", action="store_true")
    parser.add_argument("--captcha-retries", type=int, default=3)
    parser.add_argument("--slow-mo", type=int, default=150)
    args = parser.parse_args()

    process_df = load_process_numbers(args.input, args.limit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    user_data_dir = PROJECT_ROOT / ".browser_state" / "tse_pje"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    statuses: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            slow_mo=args.slow_mo,
            viewport={"width": 1365, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        for index, row in process_df.iterrows():
            print(f"[{index + 1}/{len(process_df)}] {row['NR_PROCESSO']}")
            status = scrape_process(
                page=page,
                process_row=row,
                output_dir=args.output_dir,
                open_sentence=args.open_sentence,
                captcha_retries=args.captcha_retries,
            )
            statuses.append(status)
            pd.DataFrame(statuses).to_csv(
                args.output_dir / STATUS_FILE,
                index=False,
                encoding="utf-8-sig",
            )

        context.close()

    print(args.output_dir / STATUS_FILE)
    print(f"Processos tentados: {len(statuses)}")


if __name__ == "__main__":
    main()
