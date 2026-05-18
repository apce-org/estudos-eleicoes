from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import pandas as pd

from religiao_politica.config import INTERIM_DIR, PROCESSED_DIR, PROJECT_ROOT


INITIAL_URL = "https://consultaunificadapje.tse.jus.br/#/public/inicial/index"
RESULT_URL = "https://consultaunificadapje.tse.jus.br/#/public/resultado/{process_number}"
DEFAULT_INPUT = PROCESSED_DIR / "amostra_processos_propaganda_bens_publicos.csv"
DEFAULT_OUTPUT_DIR = INTERIM_DIR / "tse_pje_processos_bens_publicos_selenium"
STATUS_FILE = "status_scraping_processos_pje_selenium.csv"

CAPTCHA_RE = re.compile(
    r"sou humano|hcaptcha|favor clicar abaixo|qual\s+c[oó]digo\s+aparece\s+na\s+imagem|"
    r"visitante\s+humano|support\s+id",
    re.IGNORECASE,
)
CAPTCHA_ERROR_RE = re.compile(r"erro\s+ao\s+validar\s+desafio|tente\s+novamente", re.IGNORECASE)
DOCUMENT_TEXT_RE = re.compile(r"senten[cç]a|decis[aã]o|inteiro\s+teor|documento", re.IGNORECASE)
SENTENCE_TEXT_RE = re.compile(r"senten[cç]a", re.IGNORECASE)


def safe_process_id(process_number: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", str(process_number)).strip("_")


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


def body_text(driver) -> str:
    try:
        return driver.find_element("tag name", "body").text
    except Exception:
        return ""


def is_captcha_page(text: str) -> bool:
    return bool(CAPTCHA_RE.search(text or ""))


def has_captcha_error(text: str) -> bool:
    return bool(CAPTCHA_ERROR_RE.search(text or ""))


def dismiss_captcha_error(driver) -> bool:
    buttons = driver.find_elements("xpath", "//button[normalize-space()='OK']")
    for button in buttons:
        try:
            button.click()
            return True
        except Exception:
            continue
    return False


def wait_for_page(driver, seconds: float = 2.0) -> None:
    time.sleep(seconds)


def create_driver(
    user_data_dir: Path,
    detach: bool,
    profile_directory: str | None,
    debugger_address: str | None,
):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    if debugger_address:
        options.debugger_address = debugger_address
    else:
        options.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            options.add_argument(f"--profile-directory={profile_directory}")
        options.add_argument("--window-size=1365,900")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if detach:
            options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def fill_process_number_from_initial(driver, process_number: str, manual_search: bool) -> bool:
    driver.get(INITIAL_URL)
    wait_for_page(driver, 4)

    script = """
    const wanted = arguments[0];

    function visible(el) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    }

    function setValue(input, value) {
      input.focus();
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.blur();
    }

    const labels = Array.from(document.querySelectorAll('label, mat-label, span, div'));
    let input = null;
    for (const label of labels) {
      const text = (label.textContent || '').trim().toLowerCase();
      if (!text.includes('número do processo') && !text.includes('numero do processo')) continue;
      const container = label.closest('mat-form-field') || label.parentElement;
      if (!container) continue;
      input = container.querySelector('input');
      if (input && visible(input)) break;
    }

    if (!input) {
      input = Array.from(document.querySelectorAll('input')).find(visible);
    }
    if (!input) return { ok: false, reason: 'input não encontrado' };

    setValue(input, wanted);

    if (arguments[1]) return { ok: true, reason: 'número preenchido; pesquisa manual' };

    const buttons = Array.from(document.querySelectorAll('button'));
    const searchButton = buttons.find(btn => {
      const text = (btn.textContent || '').trim().toLowerCase();
      return text.includes('pesquisar') && visible(btn);
    });
    if (!searchButton) return { ok: false, reason: 'botão pesquisar não encontrado' };

    searchButton.click();
    return { ok: true, reason: 'pesquisa submetida' };
    """
    result = driver.execute_script(script, process_number, manual_search)
    if manual_search and result and result.get("ok"):
        print()
        print(f"Número do processo preenchido: {process_number}")
        print("Clique em Pesquisar no navegador e resolva qualquer desafio que aparecer.")
        answer = input("Quando a página carregar ou o CAPTCHA aparecer, pressione Enter aqui. Digite 's' para pular: ")
        if answer.strip().lower() == "s":
            return False

    wait_for_page(driver, 5)
    return bool(result and result.get("ok"))


def wait_for_manual_captcha(driver, process_number: str, captcha_retries: int) -> bool:
    for attempt in range(1, captcha_retries + 1):
        text = body_text(driver)
        if has_captcha_error(text):
            print("O TSE retornou erro ao validar desafio. Vou fechar o aviso.")
            dismiss_captcha_error(driver)
            wait_for_page(driver, 1)
            text = body_text(driver)

        if not is_captcha_page(text):
            return True

        print()
        print(f"CAPTCHA detectado no processo {process_number}.")
        print(f"Tentativa {attempt} de {captcha_retries}.")
        print("Resolva o CAPTCHA na janela do navegador.")
        print("Se aparecer o CAPTCHA textual, digite o código da imagem no site e clique em submit.")
        answer = input("Depois pressione Enter aqui. Digite 's' para pular este processo: ").strip().lower()
        if answer == "s":
            return False

        wait_for_page(driver, 3)
        text = body_text(driver)
        if has_captcha_error(text):
            print("O TSE retornou erro ao validar desafio. Vou tentar novamente pelo fluxo inicial.")
            dismiss_captcha_error(driver)
            return False
        if not is_captcha_page(text):
            return True

    return False


def collect_document_candidates(driver) -> list[dict[str, str]]:
    script = """
    const re = /(senten[cç]a|decis[aã]o|inteiro\\s+teor|documento)/i;
    const elements = Array.from(document.querySelectorAll('a, button, [role="button"]'));
    return elements.map((el, index) => ({
      indice: index,
      tag: el.tagName.toLowerCase(),
      texto: (el.textContent || '').replace(/\\s+/g, ' ').trim(),
      href: el.getAttribute('href') || ''
    })).filter(item => item.texto && re.test(item.texto));
    """
    try:
        return list(driver.execute_script(script) or [])
    except Exception:
        return []


def open_best_document_candidate(driver, candidates: list[dict[str, str]]) -> str:
    if not candidates:
        return ""

    sentence_candidates = [candidate for candidate in candidates if SENTENCE_TEXT_RE.search(candidate["texto"])]
    chosen = sentence_candidates[0] if sentence_candidates else candidates[0]
    index = int(chosen["indice"])

    script = """
    const index = arguments[0];
    const elements = Array.from(document.querySelectorAll('a, button, [role="button"]'));
    const el = elements[index];
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.click();
    return true;
    """
    try:
        driver.execute_script(script, index)
        wait_for_page(driver, 5)
        return chosen["texto"]
    except Exception:
        return ""


def scrape_process(
    driver,
    row: pd.Series,
    output_dir: Path,
    captcha_retries: int,
    open_sentence: bool,
    manual_search: bool,
) -> dict[str, object]:
    process_number = row["NR_PROCESSO"]
    process_id = safe_process_id(process_number)
    process_dir = output_dir / process_id
    status: dict[str, object] = {
        "nr_processo": process_number,
        "status": "iniciado",
        "fluxo": "inicial_selenium",
        "captcha_detectado": False,
        "captcha_validado": False,
        "pesquisa_submetida": False,
        "candidatos_documento": 0,
        "documento_aberto": False,
        "documento_texto": "",
        "url_final": "",
        "erro": "",
    }

    try:
        submitted = fill_process_number_from_initial(driver, process_number, manual_search=manual_search)
        status["pesquisa_submetida"] = submitted
        if not submitted:
            driver.get(RESULT_URL.format(process_number=process_number))
            wait_for_page(driver, 4)

        text = body_text(driver)
        status["captcha_detectado"] = is_captcha_page(text)
        captcha_ok = wait_for_manual_captcha(driver, process_number, captcha_retries)
        status["captcha_validado"] = captcha_ok
        if not captcha_ok:
            status["status"] = "captcha_pendente"
            status["erro"] = "CAPTCHA não validado; processo pulado."
            write_text(process_dir / "pagina_captcha_pendente.html", driver.page_source)
            write_text(process_dir / "pagina_captcha_pendente.txt", body_text(driver))
            return status

        wait_for_page(driver, 3)
        write_text(process_dir / "pagina_principal.html", driver.page_source)
        write_text(process_dir / "pagina_principal.txt", body_text(driver))
        status["url_final"] = driver.current_url

        candidates = collect_document_candidates(driver)
        status["candidatos_documento"] = len(candidates)
        pd.DataFrame(candidates).to_csv(
            process_dir / "candidatos_documento.csv",
            index=False,
            encoding="utf-8-sig",
        )

        if open_sentence and candidates:
            status["documento_texto"] = open_best_document_candidate(driver, candidates)
            if status["documento_texto"]:
                write_text(process_dir / "documento_aberto.html", driver.page_source)
                write_text(process_dir / "documento_aberto.txt", body_text(driver))
                status["documento_aberto"] = True

        status["status"] = "ok"
    except Exception as exc:
        status["status"] = "erro"
        status["erro"] = repr(exc)

    return status


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Raspa processos públicos do PJe/TSE via Selenium, começando pela página inicial "
            "para preservar tokens/cookies do fluxo normal."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--captcha-retries", type=int, default=3)
    parser.add_argument("--open-sentence", action="store_true")
    parser.add_argument(
        "--manual-search",
        action="store_true",
        help="Preenche o número do processo e deixa o usuário clicar em Pesquisar manualmente.",
    )
    parser.add_argument("--detach", action="store_true")
    parser.add_argument(
        "--chrome-user-data-dir",
        type=Path,
        default=None,
        help="Pasta User Data do Chrome a usar. Ex.: C:\\Users\\usuario\\AppData\\Local\\Google\\Chrome\\User Data",
    )
    parser.add_argument(
        "--profile-directory",
        default=None,
        help="Nome do perfil dentro do User Data. Ex.: Default, Profile 1, Profile 2.",
    )
    parser.add_argument(
        "--pause-before-start",
        action="store_true",
        help="Abre o navegador e pausa antes do primeiro processo para login manual ou ajustes.",
    )
    parser.add_argument(
        "--debugger-address",
        default=None,
        help="Conecta a um Chrome já aberto com remote debugging. Ex.: 127.0.0.1:9222.",
    )
    args = parser.parse_args()

    process_df = load_process_numbers(args.input, args.limit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    user_data_dir = args.chrome_user_data_dir or PROJECT_ROOT / ".browser_state" / "selenium_tse_pje"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    statuses: list[dict[str, object]] = []
    driver = create_driver(
        user_data_dir=user_data_dir,
        detach=args.detach,
        profile_directory=args.profile_directory,
        debugger_address=args.debugger_address,
    )
    try:
        if args.pause_before_start:
            print()
            print("Navegador aberto. Faça login ou ajuste o perfil, se necessário.")
            input("Quando estiver pronto para iniciar a raspagem, pressione Enter aqui: ")

        for index, row in process_df.iterrows():
            print(f"[{index + 1}/{len(process_df)}] {row['NR_PROCESSO']}")
            status = scrape_process(
                driver=driver,
                row=row,
                output_dir=args.output_dir,
                captcha_retries=args.captcha_retries,
                open_sentence=args.open_sentence,
                manual_search=args.manual_search,
            )
            statuses.append(status)
            pd.DataFrame(statuses).to_csv(
                args.output_dir / STATUS_FILE,
                index=False,
                encoding="utf-8-sig",
            )
    finally:
        if not args.detach:
            driver.quit()

    print(args.output_dir / STATUS_FILE)
    print(f"Processos tentados: {len(statuses)}")


if __name__ == "__main__":
    main()
