from __future__ import annotations

import re
from dataclasses import dataclass

from unidecode import unidecode


CHRISTIAN_PATTERNS = [
    ("lideranca_evangelica", "forte", "pastor", r"\bpastor(?:a)?\b"),
    ("lideranca_evangelica", "forte", "pr_nome", r"\bpr\.?\s+[a-z]"),
    ("lideranca_evangelica", "forte", "pra_nome", r"\bpra\.?\s+[a-z]"),
    ("lideranca_evangelica", "forte", "bispo", r"\bbispo(?:a)?\b"),
    ("lideranca_evangelica", "forte", "apostolo", r"\bap[oó]stolo(?:a)?\b"),
    ("lideranca_evangelica", "forte", "missionario", r"\bmission[aá]ri[oa]\b"),
    ("lideranca_evangelica", "ampla", "evangelista", r"\bevangelista\b"),
    ("lideranca_evangelica", "forte", "obreiro", r"\bobreir[oa]\b"),
    ("lideranca_evangelica", "forte", "presbitero", r"\bpresb[ií]tero\b"),
    ("lideranca_evangelica", "forte", "presbitero_abrev", r"\bpbr?o\.?\b"),
    ("lideranca_evangelica", "forte", "pb_nome", r"\bpb\.?\s+[a-z]"),
    ("lideranca_evangelica", "forte", "diacono", r"\bdi[aá]cono\b"),
    ("lideranca_evangelica", "forte", "diaconisa", r"\bdiaconisa\b"),
    ("lideranca_catolica", "forte", "padre", r"\bpadre\b"),
    ("lideranca_catolica", "forte", "pe_nome", r"\bpe\.?\s+[a-z]"),
    ("lideranca_catolica", "forte", "frei", r"\bfrei\b"),
    ("lideranca_catolica", "forte", "freira", r"\bfreira\b"),
    ("lideranca_catolica", "forte", "monsenhor", r"\bmonsenhor\b"),
    ("lideranca_catolica", "forte", "irmao_nome", r"\bir[mãa]o\s+[a-z]"),
    ("lideranca_catolica", "forte", "irma_nome", r"\bir[mãa]\s+[a-z]"),
    ("identidade_crista", "media", "cristao", r"\bcrist[aã]o\b"),
    ("identidade_crista", "media", "crista", r"\bcrist[aã]\b"),
    ("identidade_crista", "media", "evangelico", r"\bevang[eé]lic[oa]\b"),
    ("identidade_crista", "media", "gospel", r"\bgospel\b"),
    ("identidade_crista", "media", "catolico", r"\bcat[oó]lic[oa]\b"),
    ("identidade_crista", "media", "paroquia", r"\bpar[oó]quia\b"),
    ("identidade_crista", "media", "assembleia_de_deus", r"\bassembl[eé]ia de deus\b|\bassembleia de deus\b"),
    ("identidade_crista", "media", "igreja", r"\bigreja\b"),
    ("identidade_crista", "ampla", "jesus", r"\bjesus\b"),
    ("identidade_crista", "ampla", "deus", r"\bdeus\b"),
]

SIGNAL_STRENGTH_ORDER = {"ampla": 1, "media": 2, "forte": 3}


@dataclass(frozen=True)
class ReligiousMatch:
    has_religious_signal: bool
    categories: str
    matched_terms: str
    signal_strength: str


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    return unidecode(text).casefold()


def iter_christian_patterns() -> list[tuple[str, str, str, re.Pattern[str]]]:
    patterns = []
    for category, strength, label, regex in CHRISTIAN_PATTERNS:
        normalized_regex = normalize_text(regex)
        patterns.append((category, strength, label, re.compile(normalized_regex)))
    return patterns


def strongest_signal(strengths: list[str]) -> str:
    if not strengths:
        return ""
    return max(strengths, key=lambda value: SIGNAL_STRENGTH_ORDER[value])


def classify_religious_signal(*values: object) -> ReligiousMatch:
    text = " ".join(normalize_text(value) for value in values)
    categories: list[str] = []
    terms: list[str] = []
    strengths: list[str] = []

    for category, strength, label, pattern in iter_christian_patterns():
        if pattern.search(text):
            categories.append(category)
            terms.append(label)
            strengths.append(strength)

    unique_categories = sorted(set(categories))
    unique_terms = sorted(set(terms))
    return ReligiousMatch(
        has_religious_signal=bool(unique_terms),
        categories=";".join(unique_categories),
        matched_terms=";".join(unique_terms),
        signal_strength=strongest_signal(strengths),
    )
