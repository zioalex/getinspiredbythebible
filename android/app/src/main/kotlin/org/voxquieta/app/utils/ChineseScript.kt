package org.voxquieta.app.utils

/**
 * Traditional-to-Simplified Chinese character normalization (BITB-110, the Android fast-follow
 * to BITB-025).
 *
 * A single-character lookup table, applied before verse-reference matching so that a book name
 * written in Traditional characters (e.g. "約翰福音", as an LLM might produce for John) resolves
 * the same way as the Simplified form already used throughout [LOCALIZED_BOOK_TO_ENGLISH]
 * ("约翰福音").
 *
 * Deliberately NOT a general-purpose Traditional->Simplified converter (no ICU `Transliterator`,
 * no OpenCC): those do phrase-level conversion and are not guaranteed length-preserving. This
 * table is a strict 1:1 character substitution, so
 * `normalizeTraditionalToSimplified(s).length == s.length` always holds — callers that track
 * match offsets into the original text ([org.voxquieta.app.presentation.components.injectVerseLinks])
 * can match against a normalized copy while slicing the *original* string for display, keeping
 * the user's own script on screen.
 *
 * Must stay in sync with `tests/fixtures/t2s_char_map.json` (the cross-platform source of
 * truth), `api/utils/chinese_script.py`, and `frontend/src/lib/chineseScript.ts` — verified by
 * [org.voxquieta.app.utils.ChineseScriptTest]'s parity test.
 */

// Traditional character -> Simplified character. Two Traditional variants of the same character
// can map to one Simplified target (e.g. both 啟 and 啓 are Traditional forms of 启).
val TRADITIONAL_TO_SIMPLIFIED: Map<Char, Char> = mapOf(
    '亞' to '亚',
    '來' to '来',
    '傳' to '传',
    '創' to '创',
    '啓' to '启',
    '啟' to '启',
    '師' to '师',
    '彌' to '弥',
    '後' to '后',
    '數' to '数',
    '書' to '书',
    '歷' to '历',
    '爾' to '尔',
    '猶' to '犹',
    '瑪' to '玛',
    '竇' to '窦',
    '紀' to '纪',
    '約' to '约',
    '結' to '结',
    '羅' to '罗',
    '記' to '记',
    '詩' to '诗',
    '該' to '该',
    '賽' to '赛',
    '達' to '达',
    '錄' to '录',
    '門' to '门',
    '馬' to '马',
    '鴻' to '鸿',
)

/**
 * Convert Traditional Chinese characters to Simplified, char-by-char.
 *
 * Length-preserving by construction (one-to-one substitution), and a no-op for any text with no
 * table characters — safe to call unconditionally on non-Chinese text.
 */
fun normalizeTraditionalToSimplified(text: String): String {
    if (text.isEmpty()) return text
    var changed = false
    val out = StringBuilder(text.length)
    for (ch in text) {
        val mapped = TRADITIONAL_TO_SIMPLIFIED[ch]
        if (mapped != null) {
            out.append(mapped)
            changed = true
        } else {
            out.append(ch)
        }
    }
    return if (changed) out.toString() else text
}
