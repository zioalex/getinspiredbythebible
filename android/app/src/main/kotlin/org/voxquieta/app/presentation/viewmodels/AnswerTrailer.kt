package org.voxquieta.app.presentation.viewmodels

// Shared trailer rule (identical on backend `_UNTERMINATED_TRAILER` and web `stripTrailer`):
// (a) remove complete `<!-- VERSES|FOLLOWUPS: ... -->` comments; (b) remove an unterminated
// `<!--...` tail to the end of the text whatever follows the opener; (c) remove a dangling
// `<!-`, `<!` or `<` at the very end; then right-trim.
private val COMPLETE_TRAILER =
    Regex("""<!--\s*(?:VERSES|FOLLOWUPS)\s*:(?:(?!-->)[\s\S])*-->""", RegexOption.IGNORE_CASE)
private val UNTERMINATED_TRAILER = Regex("""\s*(?:<!--(?:(?!-->)[\s\S])*|<(?:!-?)?)\z""")

/**
 * BITB-320: removes a machine trailer the model wrote at the end of a reply
 * (`<!-- VERSES: ... -->`, `<!-- FOLLOWUPS: a|b -->`, including a half-received one) so it is
 * never shown. Used when `chat/finalize` failed and the server could not strip it for us.
 */
fun stripAnswerTrailer(text: String): String =
    text.replace(COMPLETE_TRAILER, "").replace(UNTERMINATED_TRAILER, "").trimEnd()
