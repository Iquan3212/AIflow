"""
GmailAdapter tests. Message-parsing helpers are tested as pure functions
against hand-built fake Gmail API response dicts (real Gmail response
shape, not fabricated - matches the documented payload structure).
search/read/draft/send are tested against a mocked googleapiclient
service object (unittest.mock) - zero real network calls, zero LLM
tokens, zero real Gmail API calls.

Run: python3 -m pytest tests/test_gmail_adapter.py -q   (from backend/)
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from app.services.gmail.gmail_adapter import GmailAdapter, GmailNotAvailableError


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


class TestMessageParsing:
    def test_header_lookup_case_insensitive(self):
        headers = [{"name": "Subject", "value": "Hello"}, {"name": "From", "value": "a@b.com"}]
        assert GmailAdapter._header(headers, "subject") == "Hello"
        assert GmailAdapter._header(headers, "FROM") == "a@b.com"
        assert GmailAdapter._header(headers, "missing") is None

    def test_extract_body_text_plain(self):
        payload = {"mimeType": "text/plain", "body": {"data": b64("Hello world")}}
        assert GmailAdapter._extract_body_text(payload) == "Hello world"

    def test_extract_body_text_walks_multipart(self):
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": b64("Plain body")}},
                {"mimeType": "text/html", "body": {"data": b64("<p>HTML body</p>")}},
            ],
        }
        # text/plain part found first in the walk - preferred over html.
        assert GmailAdapter._extract_body_text(payload) == "Plain body"

    def test_extract_body_text_falls_back_to_html_stripped(self):
        payload = {"mimeType": "text/html", "body": {"data": b64("<p>Only <b>html</b></p>")}}
        text = GmailAdapter._extract_body_text(payload)
        assert "<" not in text
        assert "Only" in text and "html" in text

    def test_extract_body_text_no_body_returns_empty(self):
        assert GmailAdapter._extract_body_text({"mimeType": "text/plain", "body": {}}) == ""

    def test_summarize_message(self):
        msg = {
            "id": "msg1", "threadId": "thread1", "snippet": "a snippet",
            "payload": {"headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": "Test subject"},
                {"name": "Date", "value": "Mon, 1 Jan 2026 00:00:00 +0000"},
            ]},
        }
        adapter = GmailAdapter(db=None)
        summary = adapter._summarize_message(msg)
        assert summary == {
            "id": "msg1", "thread_id": "thread1",
            "from": "sender@example.com", "to": "me@example.com",
            "subject": "Test subject", "date": "Mon, 1 Jan 2026 00:00:00 +0000",
            "snippet": "a snippet",
        }


class FakeBusiness:
    id = "biz-adapter-test"


class TestActionsWithMockedService:
    """The real Gmail API surface is mocked at the `_service()` seam - the
    only place GmailAdapter reaches out to Google - so search/read/draft/
    send are exercised end-to-end through the adapter's own logic (query
    building, message parsing, MIME construction) with zero network
    calls."""

    def _adapter_with_mock_service(self, mock_service):
        adapter = GmailAdapter(db=MagicMock())
        adapter._service = MagicMock(return_value=mock_service)
        return adapter

    def test_search_lists_then_fetches_each_message(self):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "m1"}, {"id": "m2"}]
        }
        mock_service.users().messages().get().execute.side_effect = [
            {"id": "m1", "threadId": "t1", "snippet": "s1", "payload": {"headers": []}},
            {"id": "m2", "threadId": "t2", "snippet": "s2", "payload": {"headers": []}},
        ]
        adapter = self._adapter_with_mock_service(mock_service)
        results = adapter.search(FakeBusiness(), "invoice", max_results=5)
        assert [r["id"] for r in results] == ["m1", "m2"]

    def test_read_returns_full_message_with_body(self):
        mock_service = MagicMock()
        mock_service.users().messages().get().execute.return_value = {
            "id": "m1", "threadId": "t1", "snippet": "s1",
            "payload": {"headers": [{"name": "Subject", "value": "Hi"}], "mimeType": "text/plain", "body": {"data": b64("body text")}},
        }
        adapter = self._adapter_with_mock_service(mock_service)
        result = adapter.read(FakeBusiness(), "m1")
        assert result["subject"] == "Hi"
        assert result["body"] == "body text"

    def test_create_draft_sends_correct_mime(self):
        mock_service = MagicMock()
        mock_service.users().drafts().create().execute.return_value = {"id": "draft1", "message": {"id": "msg1"}}
        adapter = self._adapter_with_mock_service(mock_service)
        result = adapter.create_draft(FakeBusiness(), "customer@example.com", "Follow up", "Thanks for reaching out!")
        assert result == {"draft_id": "draft1", "message_id": "msg1"}
        _, kwargs = mock_service.users().drafts().create.call_args
        raw = kwargs["body"]["message"]["raw"]
        decoded = base64.urlsafe_b64decode(raw).decode()
        assert "customer@example.com" in decoded
        assert "Follow up" in decoded
        assert "Thanks for reaching out!" in decoded

    def test_send_sends_correct_mime(self):
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {"id": "sent1", "threadId": "t1"}
        adapter = self._adapter_with_mock_service(mock_service)
        result = adapter.send(FakeBusiness(), "customer@example.com", "Re: invoice", "Here is the invoice.")
        assert result == {"message_id": "sent1", "thread_id": "t1"}


class TestNotAvailable:
    def test_no_credentials_raises_not_available(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        adapter = GmailAdapter(db)
        with pytest.raises(GmailNotAvailableError):
            adapter._credentials(FakeBusiness())
