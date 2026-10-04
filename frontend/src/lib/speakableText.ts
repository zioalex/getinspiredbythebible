/**
 * BITB-119: turn an assistant answer (markdown) into text a speech synthesizer can read.
 *
 * The rules are specified once in tests/fixtures/speakable_text.json and implemented
 * twice: here and in android/.../tts/SpeakableText.kt. Both are verified against that
 * fixture, so the two clients cannot drift apart.
 *
 * Verse references are detected with the existing web verse parser
 * (createVersePatternGlobal + isKnownBook) — no new verse regex family. The parser only
 * matches chapter:verse(-end) shapes, so a chapter-only reference ("Psalm 23") is left
 * exactly as written.
 */

import { createVersePatternGlobal } from "./versePatterns";
import { isKnownBook, normalizeDigits } from "./verseExtraction";
import { normalizeTraditionalToSimplified } from "./chineseScript";

/** Maximum characters per utterance chunk (several engines truncate long utterances). */
export const MAX_CHUNK_CHARS = 200;

export interface VerseSpeechTemplate {
  verse: string;
  range: string;
}

/**
 * Spoken form of a verse reference per language. Placeholders: {book} {c} {v} {e}.
 * Mirrors `verseTemplates` in tests/fixtures/speakable_text.json (parity-tested).
 */
export const VERSE_SPEECH_TEMPLATES: Record<string, VerseSpeechTemplate> = {
  en: {
    verse: "{book} chapter {c}, verse {v}",
    range: "{book} chapter {c}, verses {v} to {e}",
  },
  it: {
    verse: "{book} capitolo {c}, versetto {v}",
    range: "{book} capitolo {c}, versetti da {v} a {e}",
  },
  de: {
    verse: "{book} Kapitel {c}, Vers {v}",
    range: "{book} Kapitel {c}, Verse {v} bis {e}",
  },
  es: {
    verse: "{book} capítulo {c}, versículo {v}",
    range: "{book} capítulo {c}, versículos {v} al {e}",
  },
  fr: {
    verse: "{book} chapitre {c}, verset {v}",
    range: "{book} chapitre {c}, versets {v} à {e}",
  },
  pt: {
    verse: "{book} capítulo {c}, versículo {v}",
    range: "{book} capítulo {c}, versículos {v} a {e}",
  },
  ar: {
    verse: "{book} الإصحاح {c}، الآية {v}",
    range: "{book} الإصحاح {c}، الآيات {v} إلى {e}",
  },
  ru: {
    verse: "{book}, глава {c}, стих {v}",
    range: "{book}, глава {c}, стихи с {v} по {e}",
  },
  zh: {
    verse: "{book}第{c}章第{v}节",
    range: "{book}第{c}章第{v}至{e}节",
  },
  hi: {
    verse: "{book} अध्याय {c}, पद {v}",
    range: "{book} अध्याय {c}, पद {v} से {e}",
  },
  ko: {
    verse: "{book} {c}장 {v}절",
    range: "{book} {c}장 {v}절부터 {e}절까지",
  },
};

function templatesFor(locale: string): VerseSpeechTemplate {
  const primary = locale.toLowerCase().split(/[-_]/)[0];
  return VERSE_SPEECH_TEMPLATES[primary] ?? VERSE_SPEECH_TEMPLATES.en;
}

function fill(
  template: string,
  book: string,
  c: string,
  v: string,
  e: string,
): string {
  // Function replacers so "$" in a book name can never be read as a pattern.
  return template
    .replace("{book}", () => book)
    .replace("{c}", () => c)
    .replace("{v}", () => v)
    .replace("{e}", () => e);
}

/** Replace every recognised verse reference with its spoken form. */
function speakVerseReferences(text: string, locale: string): string {
  const tpl = templatesFor(locale);
  // Match against a Simplified-Chinese shadow copy (length-preserving) so Traditional
  // book names are recognised, but slice the book from the ORIGINAL text.
  const search = normalizeTraditionalToSimplified(text);
  const pattern = createVersePatternGlobal();

  let out = "";
  let copiedUpTo = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(search)) !== null) {
    const shadowBook = match[1].trim();
    if (!isKnownBook(shadowBook)) {
      // Rewind so a valid reference hidden inside a greedy over-match is recovered.
      pattern.lastIndex = match.index + 1;
      continue;
    }
    const bookStart = match.index + match[0].indexOf(match[1]);
    const book = text.slice(bookStart, bookStart + match[1].length).trim();
    const chapter = normalizeDigits(match[2]);
    const verse = normalizeDigits(match[3]);
    const end = match[4] ? normalizeDigits(match[4]) : "";

    out += text.slice(copiedUpTo, match.index);
    out += fill(end ? tpl.range : tpl.verse, book, chapter, verse, end);
    copiedUpTo = match.index + match[0].length;
  }
  return out + text.slice(copiedUpTo);
}

/**
 * Normalize assistant markdown into plain speakable text (FR5).
 * Lines are joined with "\n"; blank lines collapse (each line is a sentence break).
 */
export function normalizeForSpeech(markdown: string, locale: string): string {
  let text = markdown.replace(/\r\n?/g, "\n");

  // Markdown images -> alt text; links -> link text; bare URLs removed.
  text = text.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
  text = text.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
  // Leading blanks go with the URL; trailing sentence punctuation / ")" stays in place.
  // URL characters are printable ASCII only (CJK text has no spaces, so \S would swallow the
  // sentence); parentheses are kept only when balanced, e.g. Wikipedia ".../Foo_(bar)".
  text = text.replace(
    /[ \t]*https?:\/\/(?:[!-'*-~]|\([!-'*-~]*\))*(?<![.,;:!?])/g,
    "",
  );
  text = text.replace(/[ \t]*(?:\(\)|（）)/g, "");

  // Guillemets around a book name: <<Book>> / 《Book》 -> Book.
  text = text.replace(/<<\s*([^<>]*?)\s*>>/g, "$1");
  text = text.replace(/《\s*([^《》]*?)\s*》/g, "$1");

  const lines = text.split("\n").map((raw) => {
    let line = raw;
    // Horizontal rules, then block-level markers.
    if (/^\s*([-*_]\s*){3,}$/.test(line)) return "";
    line = line.replace(/^\s*```.*$/, "");
    line = line.replace(/^\s{0,3}#{1,6}\s+/, "");
    line = line.replace(/^\s*>+\s?/, "");
    line = line.replace(/^\s*[-*+]\s+/, "");
    // Inline emphasis / code markers.
    line = line.replace(/[*`]/g, "").replace(/~~/g, "");
    line = line
      .replace(/(^|[\s(])_+/g, "$1")
      .replace(/_+(?=$|[\s).,;:!?])/g, "");
    return line;
  });

  text = lines.join("\n");
  text = speakVerseReferences(text, locale);

  return text
    .split("\n")
    .map((l) => l.replace(/[ \t ]+/g, " ").trim())
    .filter((l) => l.length > 0)
    .join("\n");
}

// Terminators that always end a sentence, and ASCII ones that only do so before
// whitespace/end (so "1.5" or "e.g.x" stays intact).
const ALWAYS_TERMINATORS = "。！？।॥؟";
const SPACE_TERMINATORS = ".!?";
const CLOSERS = "\"'”’»)]」』》";

/** Split one line of text into sentences at terminators. */
function splitSentences(text: string): string[] {
  const sentences: string[] = [];
  let current = "";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    current += ch;
    const always = ALWAYS_TERMINATORS.includes(ch);
    const spaced =
      SPACE_TERMINATORS.includes(ch) &&
      (i + 1 >= text.length ||
        /\s/.test(text[i + 1]) ||
        CLOSERS.includes(text[i + 1]));
    if (always || spaced) {
      // Swallow trailing terminators / closing quotes into this sentence.
      while (
        i + 1 < text.length &&
        (ALWAYS_TERMINATORS.includes(text[i + 1]) ||
          SPACE_TERMINATORS.includes(text[i + 1]) ||
          CLOSERS.includes(text[i + 1]))
      ) {
        current += text[++i];
      }
      if (current.trim()) sentences.push(current.trim());
      current = "";
    }
  }
  if (current.trim()) sentences.push(current.trim());
  return sentences;
}

function isHighSurrogate(code: number): boolean {
  return code >= 0xd800 && code <= 0xdbff;
}

/** Hard-split an over-long sentence into pieces of at most `max` characters. */
function hardSplit(sentence: string, max: number): string[] {
  const parts: string[] = [];
  let rest = sentence;
  while (rest.length > max) {
    let cut = rest[max] === " " ? max : rest.lastIndexOf(" ", max - 1);
    if (cut <= 0) {
      cut = max;
      // Never cut a surrogate pair in half.
      if (isHighSurrogate(rest.charCodeAt(cut - 1))) cut -= 1;
    }
    parts.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) parts.push(rest);
  return parts;
}

/** Joiner between two packed sentences: none after a CJK full stop, else a space. */
function joiner(previous: string): string {
  const last = previous[previous.length - 1];
  return "。！？".includes(last) ? "" : " ";
}

/**
 * Split normalized text into chunks of at most `max` characters, at sentence
 * and line boundaries, so the whole answer can be queued as separate utterances (FR6).
 */
export function chunkForSpeech(
  text: string,
  max: number = MAX_CHUNK_CHARS,
): string[] {
  const chunks: string[] = [];
  let current = "";
  const flush = () => {
    if (current) chunks.push(current);
    current = "";
  };

  // A newline always ends the current chunk (a paragraph / list item is its own
  // utterance, giving a natural pause); sentences within a line are packed together.
  for (const line of text.split("\n")) {
    for (const sentence of splitSentences(line)) {
      if (sentence.length > max) {
        flush();
        const parts = hardSplit(sentence, max);
        current = parts.pop() ?? "";
        chunks.push(...parts);
        continue;
      }
      if (!current) {
        current = sentence;
      } else if (
        current.length + joiner(current).length + sentence.length <=
        max
      ) {
        current += joiner(current) + sentence;
      } else {
        flush();
        current = sentence;
      }
    }
    flush();
  }
  return chunks;
}

/** Convenience: markdown -> speakable chunks. */
export function speakableChunks(markdown: string, locale: string): string[] {
  return chunkForSpeech(normalizeForSpeech(markdown, locale));
}
