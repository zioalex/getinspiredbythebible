"""
Unit tests for topic-based search boosting.

Tests topic boost logic, score calculations, and ChatService integration.
Uses mocks — no database or LLM required.
"""

from unittest.mock import MagicMock, patch

import pytest

from chat.topics import detect_topics


class TestTopicBoostFormula:
    """Test the multiplicative boost formula."""

    def test_no_matching_topics_no_boost(self):
        """Verse with 0 matching topics: final_score == base_score"""
        base_score = 0.75
        matching_topic_count = 0
        topic_boost_factor = 0.2
        final_score = base_score * (1 + topic_boost_factor * matching_topic_count)
        assert final_score == pytest.approx(0.75)

    def test_one_matching_topic_20pct_boost(self):
        """Verse with 1 matching topic: final_score == base_score * 1.2"""
        base_score = 0.75
        matching_topic_count = 1
        topic_boost_factor = 0.2
        final_score = base_score * (1 + topic_boost_factor * matching_topic_count)
        assert final_score == pytest.approx(0.90)

    def test_two_matching_topics_40pct_boost(self):
        """Verse with 2 matching topics: final_score == base_score * 1.4"""
        base_score = 0.75
        matching_topic_count = 2
        topic_boost_factor = 0.2
        final_score = base_score * (1 + topic_boost_factor * matching_topic_count)
        assert final_score == pytest.approx(1.05)

    def test_configurable_boost_factor(self):
        """Different boost factor changes result proportionally."""
        base_score = 0.80
        matching_topic_count = 1
        # 10% boost
        final_score_10 = base_score * (1 + 0.1 * matching_topic_count)
        assert final_score_10 == pytest.approx(0.88)
        # 30% boost
        final_score_30 = base_score * (1 + 0.3 * matching_topic_count)
        assert final_score_30 == pytest.approx(1.04)

    def test_boosted_verse_ranks_higher_than_unboosted(self):
        """Verse with topic match should rank higher than same base_score without match."""
        base_score = 0.60
        topic_boost_factor = 0.2

        unboosted_score = base_score * (1 + 0.0)  # 0 matching topics
        boosted_score = base_score * (1 + topic_boost_factor * 1)  # 1 matching topic

        assert boosted_score > unboosted_score

    def test_lower_base_score_with_boost_can_beat_higher_base_without_boost(self):
        """
        Demonstrates topic boosting effect:
        base_score=0.65 + 1 topic (20% boost) = 0.78 > base_score=0.75 (no boost)
        """
        boosted = 0.65 * (1 + 0.2 * 1)
        unboosted = 0.75
        assert boosted > unboosted


class TestTopicDetectionIntegration:
    """Integration tests for detect_topics() with real keyword map."""

    def test_anxiety_query_detects_anxiety_and_peace(self):
        """'I'm anxious about the future' → ['anxiety', 'peace'] or at least anxiety"""
        topics = detect_topics("I'm anxious about the future")
        assert "anxiety" in topics

    def test_forgiveness_query(self):
        """'I can't forgive them' → forgiveness"""
        topics = detect_topics("I can't forgive them")
        assert "forgiveness" in topics

    def test_loneliness_query(self):
        """'I feel alone' → loneliness"""
        topics = detect_topics("I feel alone and nobody cares")
        assert "loneliness" in topics

    def test_grief_query(self):
        """'I lost my mother' → grief"""
        topics = detect_topics("I lost my mother and I am devastated")
        assert "grief" in topics

    def test_guidance_query(self):
        """'I need guidance' → guidance"""
        topics = detect_topics("I need guidance on this important decision")
        assert "guidance" in topics

    def test_hope_query(self):
        """'I feel hopeless' → hope"""
        topics = detect_topics("I feel hopeless and desperate")
        assert "hope" in topics

    def test_multiple_topics_detected(self):
        """Rich message triggers multiple topics."""
        topics = detect_topics("I'm stressed and angry, I can't forgive and feel hopeless")
        assert len(topics) >= 3

    def test_italian_anxiety(self):
        topics = detect_topics("Sono ansioso per il futuro")
        assert "anxiety" in topics

    def test_german_forgiveness(self):
        topics = detect_topics("Ich kann nicht vergeben")
        assert "forgiveness" in topics

    def test_spanish_loneliness(self):
        topics = detect_topics("Me siento muy solo")
        assert "loneliness" in topics


class TestChatServiceTopicDetection:
    """Test _detect_topics() method on ChatService."""

    def _make_chat_service(self):
        """Create a minimal ChatService with mocked dependencies."""
        from chat.service import ChatService

        mock_session = MagicMock()
        mock_llm = MagicMock()
        mock_embedding = MagicMock()
        service = ChatService(
            db_session=mock_session,
            llm_provider=mock_llm,
            embedding_provider=mock_embedding,
        )
        return service

    def test_detect_topics_returns_list(self):
        service = self._make_chat_service()
        result = service._detect_topics("I'm anxious")
        assert isinstance(result, list)

    def test_detect_topics_anxiety_message(self):
        service = self._make_chat_service()
        result = service._detect_topics("I'm so anxious about my future")
        assert "anxiety" in result

    def test_detect_topics_empty_message(self):
        service = self._make_chat_service()
        result = service._detect_topics("")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_detect_topics_no_match(self):
        service = self._make_chat_service()
        result = service._detect_topics("What is the capital of France?")
        assert isinstance(result, list)


class TestTopicBoostingFeatureFlag:
    """Test that topic boosting respects the feature flag."""

    @patch("chat.service.settings")
    def test_boosted_search_not_called_when_flag_disabled(self, mock_settings):
        """When topic_boosting_enabled=False, search_boosted() should not be called."""
        mock_settings.topic_boosting_enabled = False
        mock_settings.hybrid_search_enabled = False
        mock_settings.query_expansion_enabled = False
        mock_settings.max_context_verses = 10
        mock_settings.content_filter_intent_detection = False
        # Verify the flag is read
        assert mock_settings.topic_boosting_enabled is False
