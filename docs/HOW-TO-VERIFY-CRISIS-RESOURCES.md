# How to verify the crisis resources registry (BITB-251)

When someone threatens to hurt themselves or another person, Vox Quieta shows a card with the
emergency number and crisis lines for their country, ahead of any AI text. **A wrong number in a
crisis is worse than none**, so every number is traceable to an official source and re-checked on a
schedule. This page is the procedure.

## Where the data lives

| File | Purpose |
| ---- | ------- |
| `api/utils/crisis_resources.json` | The registry. Single source of truth. |
| `api/utils/crisis_resources.py` | Loader, country resolution, payload, markdown fallback. |
| `scripts/check_crisis_resources.py` | Staleness / reachability check (run weekly by CI). |
| `.github/workflows/crisis-resources-staleness.yml` | Weekly schedule + manual trigger. **Not** a PR gate. |
| `api/tests/test_crisis_resources_registry.py` | PR gate: schema, number format, official-host allowlist. |

Each country has an `emergency` entry and zero or more crisis `lines`. Every entry carries:

- `source_url`: the operator's **own** site, or a government / regulator / ministry site. Never
  findahelpline.com, Wikipedia, IASP, Befrienders or any other aggregator.
- `verified_on`: ISO date (`2026-10-29`) when a person last confirmed the number against
  `source_url`, or `null` if it has never been verified.
- `verified_by`: who verified it (GitHub login or name). Required whenever `verified_on` is set.

An entry with `verified_on: null` is still shown to users (it matches what production showed before
this feature), but it is flagged unverified in the payload (`verified: false`) and the weekly check
stays red until a human verifies it.

## Weekly check

The workflow runs every Monday and on demand (Actions -> **Crisis Resources Staleness** -> Run
workflow). It fails when:

1. any `verified_on` is `null`, malformed, in the future, or older than **180 days**; or
2. any `source_url` does not answer 2xx/3xx (HEAD first, falling back to GET).

Run it locally (standard library only, Python 3.9+):

```bash
python3 scripts/check_crisis_resources.py                  # full check, needs network
python3 scripts/check_crisis_resources.py --skip-urls      # dates only
python3 scripts/check_crisis_resources.py --max-age-days 90 --timeout 20
python3 -m pytest scripts/test_check_crisis_resources.py   # the script's own tests
```

A red run is the reminder to re-verify. It is intentionally not part of the PR checks, so PRs never
fail just because time has passed.

## Re-verifying an entry

1. Open the entry's `source_url` in a browser.
2. Confirm, on that page, the **number**, the **hours** (if listed) and the **name** of the service.
   For SMS lines, confirm the short code. For `emergency` entries, confirm the national number
   (and the police number in `threat_to_others_number` where it differs).
3. If something changed, fix the number, hours, `name` or `url` in `crisis_resources.json`.
   Phone format: international with a leading `+` and country code (`+39 02 2327 2327`); short
   codes stay as-is (`988`, `112`, `3114`). Clients build `tel:` links by stripping spaces.
4. Set `verified_on` to today (ISO) and `verified_by` to your name, even if nothing changed.
5. Open a PR (`fix(api): re-verify crisis resources for <country>`). The PR tests check the format
   and the host allowlist only; they never need network access.

### Adding a country or a line

1. Add the line under `lines.<ISO-2>` and an `emergency.<ISO-2>` entry, with `name` (at least
   `en`; add the local language too: the card uses the user's language when present, else `en`),
   `phone` and/or `sms`, optional `hours` and `url`, a `source_url`, and
   `verified_on: null`, `verified_by: null` until a person verifies it.
2. If `source_url`'s host is the operator's own domain or an official body, add the host to
   `ALLOWED_SOURCE_HOSTS` in `api/tests/test_crisis_resources_registry.py`. That friction is
   deliberate: review the host before extending the list.
3. Update `language_defaults` only if the country should be the default for a UI language.
4. Verify it (steps above) before relying on it.

## How the country is chosen

Emergency numbers only work in the country the caller is in, so the API resolves, in order:

1. the user's explicit pick in the card's "Not in X?" picker (`region` + `region_override`);
2. Cloudflare's `CF-IPCountry` header (`XX` unknown and `T1` Tor are ignored);
3. the client locale region (`region`, e.g. `pt-BR` -> `BR`);
4. the per-language default in `language_defaults` (Arabic has none: international link only);
5. none: only the international link (https://findahelpline.com) and "your local emergency number".

The country is used only to pick numbers: it is never stored, and the only trace is the
`country_source` attribute on the `chat_crisis_card_shown` counter. A country with no registry entry
shows no local numbers (never another country's), only the international link.

**Owner step:** enable Cloudflare -> Network -> **IP Geolocation: On** (see
`deployment/README.md`, "IP Geolocation"). Without it the card falls back to locale, then default.

## Licensed feed later

`StaticRegistryProvider` implements the `CrisisResourceProvider` protocol. A licensed source such as
ThroughLine can replace it in `get_provider()` without touching the chat path; keep this JSON as the
bundled fallback for outages.
