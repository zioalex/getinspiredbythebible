package org.voxquieta.app.presentation.viewmodels

// A complete or unterminated `<!-- VERSES: ... -->` / `<!-- FOLLOWUPS: ... -->` marker and
// everything after it, or a trailing unterminated `<!--...` / partial `<!-`, `<!` opener
// (the connection can drop in the middle of the trailer).
private val TRAILER_START = Regex("""<!--\s*(?:VERSES|FOLLOWUPS)\b""")
private val UNTERMINATED_COMMENT = Regex("""<!--(?:(?!-->)[\s\S])*$""")
private val PARTIAL_OPENER = Regex("""<!-?$""")

/**
 * BITB-320: removes a machine trailer the model wrote at the end of a reply
 * (`<!-- VERSES: ... -->`, `<!-- FOLLOWUPS: a|b -->`, including a half-received one) so it is
 * never shown. Used when `chat/finalize` failed and the server could not strip it for us.
 * Text without a trailer is returned unchanged (apart from trailing whitespace after a strip).
 */
fun stripAnswerTrailer(text: String): String {
    var out = text
    TRAILER_START.find(out)?.let { out = out.substring(0, it.range.first) }
    out = out.replace(UNTERMINATED_COMMENT, "").replace(PARTIAL_OPENER, "")
    return if (out.length == text.length) text else out.trimEnd()
}
