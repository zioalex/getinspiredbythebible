# BITB-036: Android Inline Amber Chip for Quoted Scripture — Web Parity

**Status:** 🔄 In PR (PR #PENDING — 2026-05-29)

## User Story

As a user of the Android app, when I receive an AI response that quotes a
Bible verse, I want the quoted text to appear in a visually distinct amber
chip — the same style as the web app — so that scripture stands out from
commentary and I can instantly recognise which words are directly from the
Bible.

## Problem

### Web behaviour (reference implementation)

`ChatMessage.tsx → highlightQuotes()` matches **all** double-quoted text in
the AI response and renders each match as an **inline** amber chip:

```tsx
<span className="bg-amber-50 text-amber-900 px-1 py-0.5 rounded italic font-serif border-l-2 border-amber-400">
  "For God so loved the world…"
</span>
```

The chip is inline — the quoted text stays inside the prose sentence.

### Android behaviour (as of PR #629)

`injectVerseQuoteHighlights()` converts quoted text into a Markdown
**blockquote** (`\n> *"quote"*`). Markwon renders blockquotes as block-level
elements with a **gray** left bar and no background. This means:

1. The quote is pulled out of the prose onto its own line — disrupting the
   sentence flow.
2. No amber colour is applied — the visual distinction the user expects is
   entirely absent.

The root cause is two-fold:

- `compose-markdown:0.5.0` does not expose `beforeSetMarkdown`, so spans
  cannot be injected after Markwon processes the text.
- Even if they could, a Markwon blockquote is a block-level element and
  cannot be made inline after the fact.

## Proposed Solution

### Step 1 — Upgrade `compose-markdown` to 0.7.2

`beforeSetMarkdown: ((TextView, Spanned) -> Unit)?` is required to inject
custom spans after Markwon renders the markdown. It was added after 0.5.0;
the latest stable release is **0.7.2**.

**File:** `android/gradle/libs.versions.toml`

```toml
composeMarkdown = "0.7.2"
```

⚠️ **Breaking change to verify:** The default for `enableSoftBreakAddsNewLine`
changed from `true` (0.5.x) to `false` (0.7.x). Audit existing chat messages
for soft-break rendering differences and pass `enableSoftBreakAddsNewLine = true`
explicitly in the `MarkdownText` call if the current behaviour must be preserved.

The coil3 migration (0.6.0) is transparent — the app does not pass an
`imageLoader`, so no further code changes are needed for that.

---

### Step 2 — Remove the blockquote pre-processing step

`injectVerseQuoteHighlights()` currently emits `\n> *"quote"*`. Replace its
body with a pass-through — detection and highlighting move entirely into the
`beforeSetMarkdown` span layer in Step 4.

```kotlin
// No-op: quote highlighting is now handled via InlineAmberQuoteSpan
// in beforeSetMarkdown, not via markdown blockquote pre-processing.
internal fun injectVerseQuoteHighlights(markdown: String): String = markdown
```

Also delete `VERSE_QUOTE_REGEX` (no longer needed for pre-processing).

Unit tests for `injectVerseQuoteHighlights` that assert blockquote output
(`\n> *`) must be updated to assert the function is a no-op.

---

### Step 3 — Implement `InlineAmberQuoteSpan`

Add a private `ReplacementSpan` in `ChatMessageItem.kt` that draws the
quoted text inside an amber rounded-rect chip — identical to the web's
`<span>`.

```kotlin
private class InlineAmberQuoteSpan(
    private val bgColor: Int,        // 0xFFFFFBEB — amber-50
    private val barColor: Int,       // 0xFFD97706 — amber-600
    private val textColor: Int,      // 0xFF78350F — amber-900
    private val barWidth: Float,     // ~3 dp in pixels
    private val cornerRadius: Float,
    private val paddingH: Float,
    private val paddingV: Float,
) : ReplacementSpan() {

    override fun getSize(
        paint: Paint, text: CharSequence, start: Int, end: Int,
        fm: Paint.FontMetricsInt?,
    ): Int =
        (paint.measureText(text, start, end) + barWidth + paddingH * 2).toInt()

    override fun draw(
        canvas: Canvas, text: CharSequence, start: Int, end: Int,
        x: Float, top: Int, y: Int, bottom: Int, paint: Paint,
    ) {
        val width = paint.measureText(text, start, end) + barWidth + paddingH * 2
        val rect = RectF(x, top + paddingV, x + width, bottom - paddingV)

        // 1. Amber-50 rounded background
        paint.color = bgColor
        paint.style = Paint.Style.FILL
        canvas.drawRoundRect(rect, cornerRadius, cornerRadius, paint)

        // 2. Amber-600 left bar
        paint.color = barColor
        canvas.drawRoundRect(
            RectF(x, rect.top, x + barWidth, rect.bottom),
            cornerRadius, cornerRadius, paint,
        )

        // 3. Amber-900 italic serif text
        paint.color = textColor
        paint.typeface = Typeface.create(Typeface.SERIF, Typeface.ITALIC)
        canvas.drawText(text, start, end, x + barWidth + paddingH, y.toFloat(), paint)
    }
}
```

Additional imports: `android.graphics.RectF`, `android.graphics.Typeface`,
`android.text.style.ReplacementSpan`.

> **Multi-line caveat:** `ReplacementSpan.draw()` is called once per line
> fragment when the span crosses a line break. `start`…`end` will be a
> sub-range of the full span on wrapped lines. The background and left bar
> must extend across the full line width for each fragment to avoid visual
> gaps between lines.

---

### Step 4 — Broaden quote detection to match all quoted text (web parity)

Replace the current verse-link-anchored `VERSE_QUOTE_REGEX` with a simpler
all-quotes pattern that mirrors the web's `/"([^"]+)"/g`:

```kotlin
// Matches any quoted text with supported quote-mark pairs, min 3 content chars.
// Mirrors the web's highlightQuotes() which matches all double-quoted text.
private val QUOTE_HIGHLIGHT_REGEX = Regex(
    """([""«„「《](?:[^""»"」》]{3,})[""»"」》])"""
)
```

---

### Step 5 — Wire up `beforeSetMarkdown`

In the `MarkdownText` call in `ChatMessageItem.kt`:

```kotlin
MarkdownText(
    // injectVerseQuoteHighlights is now a no-op; keep the call for API stability
    markdown = injectVerseQuoteHighlights(injectVerseLinks(message.content, verseRefRegex)),
    style = bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface),
    linkColor = amberColor,
    isTextSelectable = true,
    enableSoftBreakAddsNewLine = true, // preserve 0.5.x behaviour
    onLinkClicked = { url -> … },
    beforeSetMarkdown = { _, spanned ->
        if (spanned is Spannable) {
            QUOTE_HIGHLIGHT_REGEX.findAll(spanned).forEach { match ->
                spanned.setSpan(
                    InlineAmberQuoteSpan(
                        bgColor      = 0xFFFFFBEB.toInt(), // amber-50
                        barColor     = 0xFFD97706.toInt(), // amber-600
                        textColor    = 0xFF78350F.toInt(), // amber-900
                        barWidth     = 6f,
                        cornerRadius = 4f,
                        paddingH     = 8f,
                        paddingV     = 2f,
                    ),
                    match.range.first,
                    match.range.last + 1,
                    Spannable.SPAN_EXCLUSIVE_EXCLUSIVE,
                )
            }
        }
    },
)
```

## Files Affected

| File | Change |
|---|---|
| `android/gradle/libs.versions.toml` | `composeMarkdown` bump to `0.7.2` |
| `android/app/src/main/kotlin/…/ChatMessageItem.kt` | Add `InlineAmberQuoteSpan`, `QUOTE_HIGHLIGHT_REGEX`; wire `beforeSetMarkdown`; `injectVerseQuoteHighlights` → no-op; add imports |
| `android/app/src/test/kotlin/…/VerseRefLinkTest.kt` | Update `injectVerseQuoteHighlights` tests; add tests for `QUOTE_HIGHLIGHT_REGEX` |

## Acceptance Criteria

- [ ] Quoted scripture text in assistant messages renders as an inline amber
      chip (amber-50 background, amber-600 left bar, amber-900 italic serif)
      without breaking the surrounding prose onto a new line
- [ ] All double-quoted text in assistant messages is highlighted, not only
      quotes adjacent to a verse link (matching web behaviour)
- [ ] Verse references remain bold amber links, tappable to open
      `VerseDetailBottomSheet`
- [ ] Soft-break rendering is unchanged from the current 0.5.0 behaviour
- [ ] All existing unit tests pass; new unit tests cover `InlineAmberQuoteSpan`
      and `QUOTE_HIGHLIGHT_REGEX`
- [ ] Android Lint, Unit Tests, Compose UI Tests, and Build Prod APK all pass

## References

- PR #629 — expanded `VERSE_QUOTE_REGEX`; amber styling deferred (this story)
- PR #619 — bold verse reference wrapping and initial blockquote conversion
- `frontend/src/components/ChatMessage.tsx → highlightQuotes()` — web reference
- `compose-markdown` releases: <https://github.com/jeziellago/compose-markdown/releases>
- GitHub issue #631 — created in error (not the project's tracking tool); can be closed
