/**
 * Traditional-to-Simplified Chinese character normalization (BITB-025).
 *
 * A single-character lookup table, applied before verse-reference matching so
 * that a book name written in Traditional characters (e.g. "約翰福音", as an
 * LLM might produce for John) resolves the same way as the Simplified form
 * already used throughout LOCALIZED_BOOK_TO_ENGLISH ("约翰福音").
 *
 * Deliberately NOT a general-purpose Traditional->Simplified converter (no
 * chinese-conv npm package, no ICU): those do phrase-level conversion and
 * are not guaranteed length-preserving. This table is a strict 1:1 character
 * substitution, so normalizeTraditionalToSimplified(s).length === s.length
 * always holds — callers that track match offsets into the original text
 * (linkifyVerses.ts, ChatMessage.tsx's highlightText) can match against a
 * normalized copy while slicing the *original* string for display, keeping
 * the user's own script on screen.
 *
 * Must stay in sync with tests/fixtures/t2s_char_map.json (the cross-platform
 * source of truth) and its backend counterpart, api/utils/chinese_script.py —
 * verified by a parity test.
 */

// Traditional character -> Simplified character. Two Traditional variants of
// the same character can map to one Simplified target (e.g. both 啟 and 啓 are
// Traditional forms of 启).
export const TRADITIONAL_TO_SIMPLIFIED: Record<string, string> = {
  亞: "亚",
  來: "来",
  傳: "传",
  創: "创",
  啓: "启",
  啟: "启",
  師: "师",
  彌: "弥",
  後: "后",
  數: "数",
  書: "书",
  歷: "历",
  爾: "尔",
  猶: "犹",
  瑪: "玛",
  竇: "窦",
  紀: "纪",
  約: "约",
  結: "结",
  羅: "罗",
  記: "记",
  詩: "诗",
  該: "该",
  賽: "赛",
  達: "达",
  錄: "录",
  門: "门",
  馬: "马",
  鴻: "鸿",
};

const _T2S_CHAR_CLASS = new RegExp(
  `[${Object.keys(TRADITIONAL_TO_SIMPLIFIED).join("")}]`,
  "g",
);

/**
 * Convert Traditional Chinese characters to Simplified, char-by-char.
 *
 * Length-preserving by construction (one-to-one substitution), and a no-op
 * for any text with no table characters — safe to call unconditionally on
 * non-Chinese text. When no match is found, `.replace` returns the original
 * string reference, so the no-op case costs one failed regex scan.
 */
export function normalizeTraditionalToSimplified(text: string): string {
  return text.replace(
    _T2S_CHAR_CLASS,
    (ch) => TRADITIONAL_TO_SIMPLIFIED[ch] ?? ch,
  );
}
