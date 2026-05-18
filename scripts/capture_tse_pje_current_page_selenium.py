from __future__ import annotations

import argparse
import re
from pathlib import Path

from religiao_politica.config import INTERIM_DIR


DEFAULT_OUTPUT_DIR = INTERIM_DIR / "tse_pje_processos_bens_publicos_manual"


def safe_process_id(process_number: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", str(process_number)).strip("_")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def create_attached_driver(debugger_address: str):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.debugger_address = debugger_address
    return webdriver.Chrome(options=options)


def body_text(driver) -> str:
    try:
        return driver.find_element("tag name", "body").text
    except Exception:
        return ""


def infer_process_number(driver) -> str:
    text = body_text(driver)
    match = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", text)
    if match:
        return match.group(0)

    url_match = re.search(r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})", driver.current_url)
    if url_match:
        return url_match.group(1)

    return "pagina_atual"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Conecta a um Chrome já aberto via remote debugging e salva a página atual do PJe/TSE. "
            "Use depois de navegar manualmente e passar pelo CAPTCHA."
        )
    )
    parser.add_argument("--debugger-address", default="127.0.0.1:9222")
    parser.add_argument("--process-number", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    driver = create_attached_driver(args.debugger_address)
    try:
        process_number = args.process_number or infer_process_number(driver)
        process_id = safe_process_id(process_number)
        process_dir = args.output_dir / process_id

        write_text(process_dir / "pagina_principal.html", driver.page_source)
        write_text(process_dir / "pagina_principal.txt", body_text(driver))
        write_text(process_dir / "url.txt", driver.current_url)

        print(process_dir)
        print(driver.current_url)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
