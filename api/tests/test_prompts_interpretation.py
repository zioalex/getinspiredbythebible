"""Prompt-level tests for BITB-177: the interpretation guidance and the surrounding-passage block.

The service-level behaviour (what is fetched, when, through chat() and chat_stream()) is in
``test_passage_context.py``; these tests pin the prompt text itself.
"""

import pytest

from chat.prompts import (
    INTERPRETATION_INTEGRITY_GUIDANCE,
    build_search_context_prompt,
    get_prayer_lookup_prompt,
    get_system_prompt,
    get_verse_lookup_prompt,
)

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
PROMPT_BUILDERS = [get_system_prompt, get_verse_lookup_prompt, get_prayer_lookup_prompt]

# build_search_context_prompt output on main (fd5e45d), before BITB-177 touched it.
_RESULTS = {
    "verses": [{"reference": "Luke 1:79", "text": "To give light to them that sit in darkness."}],
    "passages": [
        {
            "title": "Benedictus",
            "reference": "Luke 1:68-79",
            "text": "Blessed be the Lord God of Israel.",
        }
    ],
}
_MAIN_OUTPUT_WITH_RESULTS = (
    "\n## Scripture Context\nThe following Bible verses were found and are available for you to "
    'reference:\n\n## Relevant Bible Verses\n**Luke 1:79**: "To give light to them that sit in '
    'darkness."\n\n## Relevant Passages\n**Benedictus** (Luke 1:68-79)\n"Blessed be the Lord God '
    'of Israel."\n\nUse these verses to support your response when relevant. These are verified '
    "biblical texts.\n---\n"
)
_MAIN_OUTPUT_EMPTY = (
    "\n## Scripture Context\nNo specific Bible verses were found for this query. You can still "
    "provide helpful spiritual guidance.\nIf the user is asking about a non-biblical prayer or "
    "topic, help them understand it while being clear about its origin.\n---\n"
)


def _entry(carried_over=False):
    return {
        "focus": "Luke 1:79",
        "carried_over": carried_over,
        "verses": [
            {
                "reference": "Luke 1:77",
                "text": "To give knowledge of salvation.",
                "is_focus": False,
            },
            {"reference": "Luke 1:78", "text": "Through the tender mercy.", "is_focus": False},
            {"reference": "Luke 1:79", "text": "To give light.", "is_focus": True},
            {"reference": "Luke 1:80", "text": "And the child grew.", "is_focus": False},
        ],
    }


class TestInterpretationGuidanceInPrompts:
    """AC6: the FR3 guidance is in all three system prompts, in all 11 languages."""

    @pytest.mark.parametrize("language", LANGUAGES)
    @pytest.mark.parametrize("builder", PROMPT_BUILDERS, ids=lambda b: b.__name__)
    def test_guidance_present_exactly_once(self, builder, language):
        prompt = builder(language)
        assert prompt.count(INTERPRETATION_INTEGRITY_GUIDANCE) == 1

    @pytest.mark.parametrize("builder", PROMPT_BUILDERS, ids=lambda b: b.__name__)
    def test_guidance_is_appended_after_the_existing_blocks(self, builder):
        assert builder("en").endswith(INTERPRETATION_INTEGRITY_GUIDANCE)

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_prompt_still_demands_the_users_language(self, language):
        # the guidance is English instruction text; it must not displace the language rule
        prompt = get_system_prompt(language)
        assert "CRITICAL LANGUAGE RULE" in prompt
        assert prompt.index("CRITICAL LANGUAGE RULE") < prompt.index(
            INTERPRETATION_INTEGRITY_GUIDANCE
        )

    def test_guidance_covers_each_requirement(self):
        text = INTERPRETATION_INTEGRITY_GUIDANCE.lower()
        # FR3.1 speaker / addressee / subject kept apart, both readings answered
        assert "speaker" in text and "addressee" in text and "subject" in text
        assert "answer both" in text
        # FR3.2 antecedent from the verses before, name the verse, say when context is missing
        assert "surrounding passage" in text
        assert "name the verse" in text
        assert "context is needed" in text
        assert "faithful readers differ" in text or "readers differ" in text
        # FR3.3 challenged: re-read, decide on the evidence, neither flip nor dig in
        assert "re-read" in text
        assert "never change an answer only because the user doubted it" in text
        assert "never defend an answer only because you gave it" in text
        # FR3.4 no promises about the future
        assert "no promises" in text
        assert "next time" in text


class TestBuildSearchContextPromptUnchanged:
    """AC4 (prompt side): without passage context the output is exactly what main produced."""

    @pytest.mark.parametrize("passage_context", [None, [], ()])
    def test_falsy_passage_context_is_byte_identical_to_main(self, passage_context):
        assert build_search_context_prompt(_RESULTS, passage_context) == _MAIN_OUTPUT_WITH_RESULTS

    def test_default_argument_is_byte_identical_to_main(self):
        assert build_search_context_prompt(_RESULTS) == _MAIN_OUTPUT_WITH_RESULTS

    def test_empty_results_without_passage_context_is_byte_identical_to_main(self):
        empty = {"verses": [], "passages": []}
        assert build_search_context_prompt(empty) == _MAIN_OUTPUT_EMPTY
        assert build_search_context_prompt(empty, []) == _MAIN_OUTPUT_EMPTY

    def test_an_entry_without_verses_adds_nothing(self):
        empty_entry = {"focus": "Luke 1:79", "carried_over": False, "verses": []}
        assert build_search_context_prompt(_RESULTS, [empty_entry]) == _MAIN_OUTPUT_WITH_RESULTS
        assert (
            build_search_context_prompt({"verses": [], "passages": []}, [empty_entry])
            == _MAIN_OUTPUT_EMPTY
        )


class TestSurroundingPassageBlock:
    def test_block_is_inside_the_scripture_context_after_verses_and_passages(self):
        prompt = build_search_context_prompt(_RESULTS, [_entry()])
        assert prompt.startswith("\n## Scripture Context")
        assert (
            prompt.index("## Relevant Bible Verses")
            < prompt.index("## Relevant Passages")
            < prompt.index("### Surrounding Passage")
            < prompt.index("Use these verses to support your response")
        )
        assert prompt.rstrip().endswith("---")

    def test_focus_verse_is_marked_and_context_verses_are_not(self):
        prompt = build_search_context_prompt(_RESULTS, [_entry()])
        assert '**Luke 1:79** [VERSE UNDER DISCUSSION]: "To give light."' in prompt
        assert '**Luke 1:78**: "Through the tender mercy."' in prompt
        assert prompt.count("[VERSE UNDER DISCUSSION]") == 1

    def test_verses_are_listed_in_the_order_given(self):
        prompt = build_search_context_prompt(_RESULTS, [_entry()])
        block = prompt[prompt.index("### Surrounding Passage") :]
        order = [block.index(f"**Luke 1:{n}**") for n in (77, 78, 79, 80)]
        assert order == sorted(order)

    def test_heading_names_the_focus_and_instruction_is_present(self):
        prompt = build_search_context_prompt(_RESULTS, [_entry()])
        assert "### Surrounding Passage — Luke 1:79" in prompt
        assert (
            "Read these verses before explaining what or whom the marked verse refers to" in prompt
        )
        assert "discussed earlier in the conversation" not in prompt

    def test_carried_over_entry_says_it_is_the_earlier_passage(self):
        prompt = build_search_context_prompt(_RESULTS, [_entry(carried_over=True)])
        assert "### Surrounding Passage — Luke 1:79" in prompt
        assert "passage discussed earlier in the conversation" in prompt
        assert "Read these verses before explaining" not in prompt

    def test_block_is_still_rendered_when_there_are_no_verses_or_passages(self):
        prompt = build_search_context_prompt({"verses": [], "passages": []}, [_entry(True)])
        assert "### Surrounding Passage" in prompt
        assert "**Luke 1:78**" in prompt
        assert "No specific Bible verses were found" not in prompt

    def test_two_entries_get_two_blocks_in_order(self):
        second = {
            "focus": "John 1:8",
            "carried_over": False,
            "verses": [
                {"reference": "John 1:8", "text": "He was not that Light.", "is_focus": True}
            ],
        }
        prompt = build_search_context_prompt(_RESULTS, [_entry(), second])
        assert prompt.count("### Surrounding Passage") == 2
        assert prompt.index("Luke 1:79\n") < prompt.index("John 1:8\n")

    @pytest.mark.parametrize(
        "text",
        ["He said “there”", "他说：「光」", "النور", "प्रकाश"],
    )
    def test_non_latin_and_quoted_text_is_carried_verbatim(self, text):
        entry = _entry()
        entry["verses"][1]["text"] = text
        assert f'**Luke 1:78**: "{text}"' in build_search_context_prompt(_RESULTS, [entry])
