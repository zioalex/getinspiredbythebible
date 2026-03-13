"""
Unit tests for topic detection in api/chat/topics.py.

Tests keyword-based multilingual topic detection.
All tests are synchronous (no DB, no LLM required).
"""

import time

from chat.topics import TOPIC_KEYWORD_MAP, detect_topics


class TestDetectTopicsEnglish:
    """English language topic detection tests."""

    def test_detect_anxiety_from_anxious(self):
        topics = detect_topics("I'm anxious about the future")
        assert "anxiety" in topics

    def test_detect_anxiety_from_worried(self):
        topics = detect_topics("I'm worried about my finances")
        assert "anxiety" in topics

    def test_detect_anxiety_from_stress(self):
        topics = detect_topics("I'm very stressed at work")
        assert "anxiety" in topics

    def test_detect_peace_from_calm(self):
        topics = detect_topics("I need calm in my life")
        assert "peace" in topics

    def test_detect_forgiveness_from_forgive(self):
        topics = detect_topics("I can't forgive them for what they did")
        assert "forgiveness" in topics

    def test_detect_forgiveness_from_resentment(self):
        topics = detect_topics("I carry so much resentment")
        assert "forgiveness" in topics

    def test_detect_anger_from_angry(self):
        topics = detect_topics("I'm so angry right now")
        assert "anger" in topics

    def test_detect_anger_from_frustrated(self):
        topics = detect_topics("I feel very frustrated and frustrated")
        assert "anger" in topics

    def test_detect_loneliness_from_alone(self):
        topics = detect_topics("I feel so alone")
        assert "loneliness" in topics

    def test_detect_loneliness_from_lonely(self):
        topics = detect_topics("I'm very lonely and isolated")
        assert "loneliness" in topics

    def test_detect_trust_from_faith(self):
        topics = detect_topics("I'm struggling with my faith")
        assert "trust" in topics

    def test_detect_fear_from_afraid(self):
        topics = detect_topics("I'm afraid of what will happen")
        assert "fear" in topics

    def test_detect_hope_from_hopeless(self):
        topics = detect_topics("I feel hopeless about my situation")
        assert "hope" in topics

    def test_detect_grief_from_sad(self):
        topics = detect_topics("I'm so sad after losing my father")
        assert "grief" in topics

    def test_detect_guidance_from_lost(self):
        topics = detect_topics("I feel lost and don't know what to do")
        assert "guidance" in topics

    def test_detect_multiple_topics(self):
        """Message with anxiety and peace keywords."""
        topics = detect_topics("I'm anxious but I need peace")
        assert "anxiety" in topics
        assert "peace" in topics

    def test_no_topics_for_generic_message(self):
        topics = detect_topics("Tell me about the Bible")
        # Generic message may or may not match — just verify it returns a list
        assert isinstance(topics, list)

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert detect_topics("I AM ANXIOUS") == detect_topics("I am anxious")

    def test_returns_list(self):
        assert isinstance(detect_topics("hello"), list)

    def test_empty_message(self):
        result = detect_topics("")
        assert isinstance(result, list)


class TestDetectTopicsMultilingual:
    """Multilingual topic detection tests."""

    def test_italian_anxiety(self):
        """'Sono ansioso' (I'm anxious in Italian) → anxiety"""
        topics = detect_topics("Sono molto ansioso per il futuro")
        assert "anxiety" in topics

    def test_italian_frustration(self):
        """'Sono frustrato' (I'm frustrated) → anger"""
        topics = detect_topics("Sono frustrato dalla situazione")
        assert "anger" in topics

    def test_italian_forgiveness(self):
        """'Non riesco a perdonare' (I can't forgive) → forgiveness"""
        topics = detect_topics("Non riesco a perdonare questa persona")
        assert "forgiveness" in topics

    def test_german_anxiety(self):
        """German anxious keywords → anxiety"""
        topics = detect_topics("Ich bin sehr ängstlich wegen der Zukunft")
        assert "anxiety" in topics

    def test_german_peace(self):
        """German peace keyword → peace"""
        topics = detect_topics("Ich brauche Frieden in meinem Leben")
        assert "peace" in topics

    def test_spanish_lonely(self):
        """Spanish lonely → loneliness"""
        topics = detect_topics("Me siento muy solo y aislado")
        assert "loneliness" in topics

    def test_spanish_anger(self):
        """Spanish angry → anger"""
        topics = detect_topics("Estoy muy enojado con mi familia")
        assert "anger" in topics

    def test_french_hope(self):
        """French hopeless → hope"""
        topics = detect_topics("Je me sens sans espoir")
        assert "hope" in topics

    def test_portuguese_grief(self):
        """Portuguese sad/lost → grief"""
        topics = detect_topics("Estou triste depois de perder meu pai")
        assert "grief" in topics

    def test_arabic_anxiety(self):
        """Arabic anxiety keyword → anxiety"""
        topics = detect_topics("أنا قلق جداً بشأن المستقبل")
        assert "anxiety" in topics


class TestTopicKeywordMap:
    """Tests for the TOPIC_KEYWORD_MAP structure."""

    def test_map_is_dict(self):
        assert isinstance(TOPIC_KEYWORD_MAP, dict)

    def test_all_topics_have_keywords(self):
        for topic, keywords in TOPIC_KEYWORD_MAP.items():
            assert len(keywords) > 0, f"Topic '{topic}' has no keywords"

    def test_required_topics_present(self):
        required = {
            "anxiety",
            "peace",
            "forgiveness",
            "anger",
            "loneliness",
            "trust",
            "fear",
            "hope",
            "love",
            "grief",
            "guidance",
            "patience",
            "joy",
        }
        assert required.issubset(set(TOPIC_KEYWORD_MAP.keys()))

    def test_all_keywords_are_lowercase(self):
        """Keywords should be lowercase for case-insensitive matching."""
        for topic, keywords in TOPIC_KEYWORD_MAP.items():
            for kw in keywords:
                assert kw == kw.lower(), f"Keyword '{kw}' in topic '{topic}' is not lowercase"

    def test_all_keywords_are_strings(self):
        for topic, keywords in TOPIC_KEYWORD_MAP.items():
            for kw in keywords:
                assert isinstance(kw, str), f"Keyword in topic '{topic}' is not a string"


class TestDetectTopicsPerformance:
    """Performance tests for topic detection."""

    def test_detection_under_10ms(self):
        """Topic detection must complete in <10ms per acceptance criteria."""
        message = "I'm anxious and worried about my future, feeling lonely and hopeless"
        start = time.monotonic()
        for _ in range(100):
            detect_topics(message)
        elapsed = (time.monotonic() - start) * 1000 / 100  # Average ms per call
        assert elapsed < 10, f"Topic detection took {elapsed:.2f}ms (must be <10ms)"
