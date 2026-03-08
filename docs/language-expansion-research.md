# Language Expansion Research for i18n Prioritization

## Introduction

Bible Inspiration Chat currently supports three languages: English (en), Italian (it),
and German (de). To maximize the app's reach and impact, we should prioritize adding
languages based on two key criteria:

1. **Global reach** -- supporting the most widely spoken languages ensures we serve
   the largest possible audience.
2. **Spiritual need** -- supporting languages spoken in countries where Christianity
   is most persecuted ensures we serve people who may have the least access to
   spiritual encouragement and scripture.

This document presents research on both dimensions to guide our i18n expansion roadmap.

---

## 1. Top 10 Most Spoken Languages Worldwide

Ranked by total number of speakers (native + L2), based on Ethnologue (2024 edition)
and other linguistic sources.

| Rank | Language            | ISO 639-1 | Approximate Total Speakers |
|------|---------------------|-----------|---------------------------|
| 1    | English             | en        | 1.5 billion               |
| 2    | Mandarin Chinese    | zh        | 1.1 billion               |
| 3    | Hindi               | hi        | 600 million               |
| 4    | Spanish             | es        | 560 million               |
| 5    | French              | fr        | 310 million               |
| 6    | Arabic (Standard)   | ar        | 310 million               |
| 7    | Bengali             | bn        | 270 million               |
| 8    | Portuguese          | pt        | 260 million               |
| 9    | Russian             | ru        | 255 million               |
| 10   | Urdu                | ur        | 230 million               |

**Notes:**

- Japanese (ja, ~125M) and Korean (ko, ~80M) are also significant but fall outside the
  top 10 by total speakers.
- Indonesian/Malay (id, ~200M) is sometimes ranked in the top 10 depending on the source
  and whether Malay and Indonesian are counted together.

---

## 2. Top 10 Countries Where Christianity Is Most Persecuted

Based on the Open Doors World Watch List (2025), which ranks countries by the severity of
persecution faced by Christians.

| Rank | Country              | Primary Language(s)             | ISO 639-1 Code(s) |
|------|----------------------|---------------------------------|--------------------|
| 1    | North Korea          | Korean                          | ko                 |
| 2    | Somalia              | Somali, Arabic                  | so, ar             |
| 3    | Yemen                | Arabic                          | ar                 |
| 4    | Libya                | Arabic                          | ar                 |
| 5    | Eritrea              | Tigrinya, Arabic                | ti, ar             |
| 6    | Nigeria              | English, Hausa, Yoruba, Igbo   | en, ha, yo, ig     |
| 7    | Pakistan             | Urdu, Punjabi, Sindhi           | ur, pa, sd         |
| 8    | Sudan                | Arabic                          | ar                 |
| 9    | Iran                 | Persian (Farsi)                 | fa                 |
| 10   | Afghanistan          | Dari (Persian), Pashto          | fa, ps             |

**Notes:**

- The exact ranking may shift slightly year to year, but these countries have
  consistently appeared in the top 10 for multiple years.
- Several countries share Arabic as a primary or official language (Somalia, Yemen,
  Libya, Eritrea, Sudan), making Arabic a high-impact addition.
- Iran and Afghanistan both use Persian/Dari (ISO 639-1: fa), reinforcing its priority.

---

## 3. Combined Recommended Languages to Add

The following is a deduplicated list of languages derived from both tables above,
**excluding** the three already supported (en, it, de). Languages are ordered by
a combination of global reach and persecution-region relevance.

| Language         | ISO 639-1 | Rationale                                                    |
|------------------|-----------|--------------------------------------------------------------|
| Arabic           | ar        | 310M speakers; primary language in 5 of top 10 persecuted countries |
| Spanish          | es        | 560M speakers; large Christian population in Latin America   |
| French           | fr        | 310M speakers; widely spoken in persecuted regions of Africa |
| Portuguese       | pt        | 260M speakers; Brazil is the largest Catholic country        |
| Mandarin Chinese | zh        | 1.1B speakers; growing underground church in China           |
| Hindi            | hi        | 600M speakers; India has rising persecution concerns         |
| Urdu             | ur        | 230M speakers; Pakistan is #7 on persecution list            |
| Persian (Farsi)  | fa        | Spoken in Iran (#9) and Afghanistan (#10); fast-growing underground church |
| Bengali          | bn        | 270M speakers; Bangladesh has minority Christian communities |
| Russian          | ru        | 255M speakers; restrictions on religious minorities increasing |
| Korean           | ko        | North Korea is #1 most persecuted; South Korea has large Christian population |
| Hausa            | ha        | Major language in northern Nigeria (#6 persecuted); 80M+ speakers |
| Tigrinya         | ti        | Primary language in Eritrea (#5 persecuted)                  |
| Somali           | so        | Primary language in Somalia (#2 persecuted)                  |
| Pashto           | ps        | Major language in Afghanistan (#10 persecuted)               |

### Suggested Implementation Phases

**Phase 1 -- High Impact (large speaker base + persecution relevance):**

- Arabic (ar), Spanish (es), French (fr), Portuguese (pt) ✅ **Implemented** (shipped with initial i18n rollout)

**Phase 2 -- Major World Languages:** ✅ **Implemented** (PR #258 merged; PR #261 open for data loading)

- Mandarin Chinese (zh), Hindi (hi), Russian (ru), Korean (ko)

**Phase 3 -- Persecution-Priority Languages:**

- Urdu (ur), Persian/Farsi (fa), Bengali (bn)

**Phase 4 -- Regional Persecution Languages:**

- Hausa (ha), Tigrinya (ti), Somali (so), Pashto (ps)

---

## 4. RTL (Right-to-Left) Language Support

Several of the recommended languages use right-to-left scripts:

| Language       | ISO 639-1 | Script Direction |
|----------------|-----------|------------------|
| Arabic         | ar        | RTL              |
| Urdu           | ur        | RTL (Nastaliq)   |
| Persian (Farsi)| fa        | RTL              |
| Pashto         | ps        | RTL              |

### Technical Requirements for RTL Support

Before adding these languages, the frontend must support RTL rendering:

1. **HTML `dir` attribute**: Set `dir="rtl"` on the `<html>` element when an RTL locale
   is active. This can be done dynamically in `frontend/src/app/[locale]/layout.tsx`.

2. **CSS logical properties**: Replace physical properties (`margin-left`, `padding-right`)
   with logical equivalents (`margin-inline-start`, `padding-inline-end`). Tailwind CSS v3+
   supports this via the `rtl:` and `ltr:` variants.

3. **Component layout mirroring**: Chat bubbles, navigation arrows, and icon positioning
   should flip for RTL layouts.

4. **Font support**: Ensure the selected font stack includes glyphs for Arabic, Urdu
   (Nastaliq style), and Persian scripts. Consider using Google Fonts such as Noto Sans
   Arabic or Amiri.

5. **next-intl configuration**: The `routing.ts` config does not need changes for RTL
   itself, but locale-specific metadata (e.g., `dir` attribute) should be derived from
   a locale-to-direction mapping.

6. **Testing**: Each RTL language should be visually tested across all pages to ensure
   correct text alignment, input field behavior, and overall layout integrity.

---

## 5. LLM Language Support Constraints

The application uses Llama 3.3 70B Instruct as its default LLM (via OpenRouter or Ollama).
This model's officially supported languages must be considered when expanding i18n support.

### Llama 3.3 70B — Officially Supported Languages

| Language   | ISO 639-1 | Supported | In Our App |
|------------|-----------|-----------|------------|
| English    | en        | Yes       | Yes        |
| German     | de        | Yes       | Yes        |
| French     | fr        | Yes       | Yes        |
| Italian    | it        | Yes       | Yes        |
| Portuguese | pt        | Yes       | Yes        |
| Spanish    | es        | Yes       | Yes        |
| Hindi      | hi        | Yes       | No (Phase 2) |
| Thai       | th        | Yes       | No         |

### Languages NOT Officially Supported by Llama 3.3

The following Phase 1-4 languages are **not** in Llama 3.3's official list:

| Language        | ISO 639-1 | Phase | Risk Level |
|-----------------|-----------|-------|------------|
| **Arabic**      | ar        | 1     | Medium — widely present in training data, may work acceptably |
| Mandarin Chinese| zh        | 2     | Medium     |
| Russian         | ru        | 2     | Low-Medium — Cyrillic well-represented in training |
| Korean          | ko        | 2     | Medium     |
| Urdu            | ur        | 3     | High — limited training data |
| Persian (Farsi) | fa        | 3     | High       |
| Bengali         | bn        | 3     | High       |
| Hausa           | ha        | 4     | Very High  |
| Tigrinya        | ti        | 4     | Very High  |
| Somali          | so        | 4     | Very High  |
| Pashto          | ps        | 4     | Very High  |

### Mitigation Strategies

For unsupported languages (especially Arabic in Phase 1):

1. **Model routing**: Route non-supported language requests to a model with
   better coverage (e.g., Claude, GPT-4, Qwen 2.5, or Command R+).
2. **Quality testing**: Before launch, manually evaluate response quality for
   each unsupported language. Accept if quality is sufficient; route otherwise.
3. **User disclosure**: Indicate in the UI that some languages are in "beta"
   quality when the underlying LLM doesn't officially support them.
4. **Future-proofing**: As Llama 4+ or other open models add broader language
   support, revisit this table and remove mitigations.

### Alternative Models with Arabic Support (OpenRouter)

Investigated Feb 2026. Pricing is per 1M tokens on OpenRouter.

| Model | Arabic Support | Input Cost | Output Cost | Free Tier | Recommendation |
|-------|---------------|------------|-------------|-----------|----------------|
| Llama 3.3 70B (current) | Not official | Free | Free | Yes | Keep for es/fr/pt |
| **Qwen 2.5 72B Instruct** | **Official (29+ langs)** | **$0.04** | **$0.10** | No | **Best for Arabic** |
| Mistral Saba 24B | Official (Arabic focus) | Low | Low | No | Smaller, less capable |
| Mistral Large 2 | Official | ~$2.00 | ~$6.00 | No | Expensive |
| Command R+ (Cohere) | Official (10 langs) | $2.50 | $10.00 | No | Very expensive |

**Recommendation**: Use **Qwen 2.5 72B Instruct** (`qwen/qwen-2.5-72b-instruct` on OpenRouter)
for Arabic requests. At $0.04/$0.10 per 1M tokens, it's essentially the same cost as paid
Llama 3.3 but with official Arabic support across 29+ languages. This could be implemented as:

- A per-language model routing config in `config.py`
- Or a simple fallback: use Llama 3.3 for supported languages, Qwen 2.5 for others
- Or replace the default model entirely with Qwen 2.5 (it supports all our languages)

---

## Sources

- Ethnologue: Languages of the World (2024 edition) -- total speaker counts
- Open Doors World Watch List (2025) -- persecution rankings
- ISO 639-1 language codes -- standard two-letter codes
- next-intl documentation -- i18n implementation guidance
