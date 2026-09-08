"""
gmail_ai_service extraction logic - chat_completion() is mocked (matching
lead_ai_service's existing test convention in this repo) so zero real LLM
tokens are spent verifying the JSON-parsing/fallback behavior.

Run: python3 -m pytest tests/test_gmail_ai_service.py -q   (from backend/)
"""

from unittest.mock import patch

from app.services.gmail import gmail_ai_service
from app.services.llm.base import ChatResult


def _completion(content: str) -> ChatResult:
    return ChatResult(content=content)


class TestExtractSearchRequest:
    def test_parses_valid_json(self):
        with patch("app.services.gmail.gmail_ai_service.chat_completion", return_value=_completion('{"query": "from:john invoice"}')):
            result = gmail_ai_service.extract_search_request("find the invoice email from john")
        assert result == {"query": "from:john invoice"}

    def test_strips_markdown_fences(self):
        with patch("app.services.gmail.gmail_ai_service.chat_completion", return_value=_completion('```json\n{"query": "meeting"}\n```')):
            result = gmail_ai_service.extract_search_request("emails about the meeting")
        assert result == {"query": "meeting"}

    def test_invalid_json_returns_default(self):
        with patch("app.services.gmail.gmail_ai_service.chat_completion", return_value=_completion("not json at all")):
            result = gmail_ai_service.extract_search_request("gibberish")
        assert result == {"query": ""}


class TestExtractSendRequest:
    def test_parses_valid_json(self):
        payload = '{"to": "customer@example.com", "subject": "Thanks", "body": "Thanks for reaching out!"}'
        with patch("app.services.gmail.gmail_ai_service.chat_completion", return_value=_completion(payload)):
            result = gmail_ai_service.extract_send_request("draft a thank you to customer@example.com")
        assert result == {"to": "customer@example.com", "subject": "Thanks", "body": "Thanks for reaching out!"}

    def test_invalid_json_returns_default_with_nulls(self):
        with patch("app.services.gmail.gmail_ai_service.chat_completion", return_value=_completion("garbage")):
            result = gmail_ai_service.extract_send_request("draft something")
        assert result == {"to": None, "subject": None, "body": None}

    def test_non_dict_json_returns_default(self):
        with patch("app.services.gmail.gmail_ai_service.chat_completion", return_value=_completion("[1, 2, 3]")):
            result = gmail_ai_service.extract_send_request("draft something")
        assert result == {"to": None, "subject": None, "body": None}
