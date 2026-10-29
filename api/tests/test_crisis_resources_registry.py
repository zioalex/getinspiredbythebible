"""BITB-251: schema, provenance and source-host checks for the crisis-resources registry.

A wrong number in a crisis is worse than none, so every entry must carry an official source.
These tests fail the PR gate on structure and provenance; whether `verified_on` is recent
is checked by the weekly job (scripts/check_crisis_resources.py), never here.
"""

import json
import re
from urllib.parse import urlparse

import pytest

from utils.crisis_resources import (
    REGISTRY_PATH,
    SUPPORTED_LANGUAGES,
    CrisisKind,
    StaticRegistryProvider,
    load_registry,
)

# Operator-own or government/regulator hosts only. Adding a new entry whose source host is
# not listed here fails the test and names the host: that friction is deliberate -- review
# that the host really is the operator or an official body before extending this set.
ALLOWED_SOURCE_HOSTS = {
    # crisis-line operators / charities
    "988lifeline.org", "988.ca", "www.samaritans.org", "giveusashout.org", "text50808.ie",
    "www.lifeline.org.au", "www.telefonoamico.it", "www.143.ch", "www.telefonseelsorge.de",
    "www.telefonseelsorge.at", "telefonodelaesperanza.org",
    "www.asistenciaalsuicida.org.ar", "3114.fr", "www.preventionsuicide.be",
    "www.zelfmoord1813.be", "www.cvv.org.br", "www.sosvozamiga.org", "telefon-doveria.ru",
    "www.samaritans.org.hk",
    # government / regulator / ministry sites
    "www.911.gov", "www.nhs.uk", "www.citizensinformation.ie", "www.canada.ca",
    "www.triplezero.gov.au", "www.interno.gov.it", "www.ch.ch", "www.bmi.bund.de",
    "www.oesterreich.gv.at", "www.interior.gob.es", "www.sanidad.gob.es", "www.gob.mx",
    "www.argentina.gob.ar", "www.service-public.fr", "www.belgium.be", "www.gov.br",
    "www.portugal.gov.pt", "www.mchs.gov.ru", "www.nhc.gov.cn", "www.gov.cn",
    "www.mohw.gov.tw", "www.gov.tw", "www.gov.hk", "telemanas.mohfw.gov.in",
    "www.india.gov.in", "www.mohw.go.kr", "www.mois.go.kr", "www.egypt.gov.eg",
    "www.my.gov.sa", "u.ae", "www.pcm.gov.lb", "www.maroc.ma", "www.gov.jo",
}  # fmt: skip

# Aggregators / reference sites are never an acceptable *source* (findahelpline is only
# ever linked as the international fallback, not cited as proof of a number).
FORBIDDEN_SOURCE_HOST_PARTS = (
    "findahelpline", "wikipedia", "iasp.info", "befrienders", "esrot", "wikidata", "112.eu",
)  # fmt: skip

EXPECTED_COUNTRIES = {
    "US", "GB", "IE", "CA", "AU", "IT", "CH", "DE", "AT", "ES", "MX", "AR", "FR", "BE",
    "BR", "PT", "RU", "CN", "TW", "HK", "IN", "KR",
}  # fmt: skip
EMERGENCY_ONLY = {"EG", "SA", "AE", "LB", "MA", "JO"}

_PHONE_RE = re.compile(r"^\+?[0-9]{3,15}$")


def _phone_ok(phone: str) -> bool:
    stripped = phone.replace(" ", "")
    if not _PHONE_RE.match(stripped):
        return False
    digits = stripped.lstrip("+")
    # Anything longer than a short code must carry an explicit country code.
    return stripped.startswith("+") or len(digits) <= 6


def _source_entries(registry):
    for country, entry in registry["emergency"].items():
        yield f"emergency[{country}]", entry
    for country, lines in registry["lines"].items():
        for line in lines:
            yield f"lines[{country}][{line['id']}]", line


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_registry_file_is_valid_json_with_expected_top_level_keys():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    for key in ("international_url", "language_defaults", "emergency", "lines"):
        assert key in data


def test_covers_every_seeded_country(registry):
    assert EXPECTED_COUNTRIES <= set(registry["lines"])
    assert (EXPECTED_COUNTRIES | EMERGENCY_ONLY) <= set(registry["emergency"])
    assert EMERGENCY_ONLY.isdisjoint(registry["lines"]) or all(
        not registry["lines"][c] for c in EMERGENCY_ONLY & set(registry["lines"])
    )


def test_every_line_country_has_an_emergency_entry(registry):
    assert set(registry["lines"]) <= set(registry["emergency"])


def test_language_defaults_cover_all_languages(registry):
    defaults = registry["language_defaults"]
    assert set(defaults) == set(SUPPORTED_LANGUAGES)
    assert defaults["ar"] is None
    expected = {
        "en": "US", "it": "IT", "de": "DE", "es": "ES", "fr": "FR", "pt": "BR",
        "ru": "RU", "zh": "CN", "hi": "IN", "ko": "KR",
    }  # fmt: skip
    for lang, country in expected.items():
        assert defaults[lang] == country
        assert country in registry["emergency"], f"default {country} for {lang} has no numbers"


def test_international_url_is_findahelpline(registry):
    assert registry["international_url"] == "https://findahelpline.com"


def test_every_entry_has_source_and_provenance_fields(registry):
    for label, entry in _source_entries(registry):
        assert entry.get("source_url"), f"{label}: missing source_url"
        for field in ("verified_on", "verified_by"):
            assert field in entry, f"{label}: missing {field} (null until a human verifies)"


def test_source_urls_are_https_official_hosts(registry):
    for label, entry in _source_entries(registry):
        parsed = urlparse(entry["source_url"])
        assert parsed.scheme == "https", f"{label}: source_url must be https"
        host = parsed.hostname or ""
        assert not any(
            bad in host for bad in FORBIDDEN_SOURCE_HOST_PARTS
        ), f"{label}: aggregator host {host!r} is not an acceptable source"
        assert host in ALLOWED_SOURCE_HOSTS, (
            f"{label}: source host {host!r} is not on the official-host allowlist; "
            "if it is the operator's own domain or a government/regulator domain, add it "
            "to ALLOWED_SOURCE_HOSTS in this test"
        )


def test_verified_on_is_null_or_iso_date_and_paired_with_verifier(registry):
    from datetime import date

    for label, entry in _source_entries(registry):
        if entry["verified_on"] is not None:
            date.fromisoformat(entry["verified_on"])
            assert entry["verified_by"], f"{label}: verified_on set without verified_by"


def test_phone_numbers_are_well_formed(registry):
    for country, lines in registry["lines"].items():
        for line in lines:
            label = f"lines[{country}][{line['id']}]"
            assert line.get("phone") or line.get("sms"), f"{label}: needs phone or sms"
            for field in ("phone", "sms"):
                if line.get(field):
                    assert _phone_ok(line[field]), f"{label}: malformed {field} {line[field]!r}"


def test_emergency_numbers_are_short_digit_codes(registry):
    for country, entry in registry["emergency"].items():
        for field in ("number", "threat_to_others_number"):
            value = entry.get(field)
            if value is not None:
                assert re.fullmatch(r"\d{2,4}", value), f"{country}: bad {field} {value!r}"


def test_line_urls_are_https(registry):
    for country, lines in registry["lines"].items():
        for line in lines:
            if line.get("url"):
                assert line["url"].startswith("https://"), f"{country}/{line['id']}"


def test_names_and_hours_have_english_fallback_and_known_languages(registry):
    known = set(SUPPORTED_LANGUAGES)
    for country, lines in registry["lines"].items():
        for line in lines:
            label = f"{country}/{line['id']}"
            assert line["name"].get("en"), f"{label}: name needs an 'en' fallback"
            assert set(line["name"]) <= known, f"{label}: unknown name language"
            if line.get("hours"):
                assert line["hours"].get("en"), f"{label}: hours need an 'en' fallback"
                assert set(line["hours"]) <= known, f"{label}: unknown hours language"


def test_line_ids_are_unique(registry):
    ids = [line["id"] for lines in registry["lines"].values() for line in lines]
    assert len(ids) == len(set(ids))


def test_country_codes_are_upper_alpha2(registry):
    for code in set(registry["lines"]) | set(registry["emergency"]):
        assert re.fullmatch(r"[A-Z]{2}", code), code


def test_threat_number_override_applies_only_to_threat_kind():
    provider = StaticRegistryProvider()
    br = provider.get_emergency("BR")
    assert br is not None
    assert br.number_for(CrisisKind.SELF_HARM) == "192"
    assert br.number_for(CrisisKind.THREAT_TO_OTHERS) == "190"
    us = provider.get_emergency("US")
    assert us is not None
    assert us.number_for(CrisisKind.THREAT_TO_OTHERS) == "911"


def test_available_countries_sorted_and_complete():
    provider = StaticRegistryProvider()
    codes = provider.available_countries()
    assert codes == sorted(codes)
    assert (EXPECTED_COUNTRIES | EMERGENCY_ONLY) <= set(codes)


def test_unverified_entries_report_verified_false_in_payload():
    from utils.crisis_resources import build_crisis_payload

    payload = build_crisis_payload(CrisisKind.SELF_HARM, "US", "ip", "en")
    assert payload["lines"] and all(line["verified"] is False for line in payload["lines"])
