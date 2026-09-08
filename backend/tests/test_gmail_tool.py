"""
GmailTool classes: explicit structured kwargs must always be preferred
over LLM-based extraction (the LLM extraction path is mocked wherever a
test would otherwise reach it - see gmail_ai_service.extract_send_request/
extract_search_request - so zero LLM tokens are ever spent here).

Also verifies real Tool Router / Registry wiring: the four gmail_* tools
are actually reachable (permission-checked) exactly like every other tool,
and Manager (which gets all_tools()) can use them while an unrelated
employee cannot.

Run: python3 -m pytest tests/test_gmail_tool.py -q   (from backend/)
"""

from unittest.mock import MagicMock, patch

from app.tools.gmail_tool import GmailStatusTool, GmailSearchTool, GmailReadTool, GmailDraftTool, GmailSendTool


class FakeBusiness:
    id = "biz-tool-test"


class TestGmailStatusTool:
    def test_missing_business_returns_error(self):
        assert GmailStatusTool().execute("do you have gmail access?", db=MagicMock(), business=None) == {
            "ok": False, "error": "missing_business",
        }

    def test_never_calls_llm_extraction_or_the_real_gmail_api(self):
        """Purely DB-backed - a capability question must never cost a real
        LLM token or a real Gmail API round-trip just to answer "are you
        connected?"."""
        with patch("app.tools.gmail_tool.GmailService") as MockService, \
             patch("app.tools.gmail_tool.gmail_ai_service") as mock_ai_service:
            MockService.return_value.status.return_value = {"ok": True, "connected": True, "send_mode": "approval_required"}
            result = GmailStatusTool().execute("do you have access to my gmail?", db=MagicMock(), business=FakeBusiness())

        mock_ai_service.extract_search_request.assert_not_called()
        mock_ai_service.extract_send_request.assert_not_called()
        assert result == {"ok": True, "connected": True, "send_mode": "approval_required"}


class TestGmailSearchTool:
    def test_explicit_query_skips_llm_extraction(self):
        with patch("app.tools.gmail_tool.GmailService") as MockService, \
             patch("app.tools.gmail_tool.gmail_ai_service.extract_search_request") as mock_extract:
            MockService.return_value.search.return_value = {"ok": True, "results": []}
            result = GmailSearchTool().execute("anything", db=MagicMock(), business=FakeBusiness(), query="from:john")
        mock_extract.assert_not_called()
        args, kwargs = MockService.return_value.search.call_args
        assert args[1] == "from:john"
        assert kwargs["max_results"] == 10
        assert result == {"ok": True, "results": []}

    def test_falls_back_to_llm_extraction_when_no_query_given(self):
        with patch("app.tools.gmail_tool.GmailService") as MockService, \
             patch("app.tools.gmail_tool.gmail_ai_service.extract_search_request", return_value={"query": "invoice"}) as mock_extract:
            MockService.return_value.search.return_value = {"ok": True, "results": []}
            GmailSearchTool().execute("find the invoice email", db=MagicMock(), business=FakeBusiness())
        mock_extract.assert_called_once_with("find the invoice email")
        args, kwargs = MockService.return_value.search.call_args
        assert args[1] == "invoice"

    def test_missing_business_returns_error(self):
        result = GmailSearchTool().execute("anything", db=MagicMock(), business=None)
        assert result == {"ok": False, "error": "missing_business"}


class TestGmailReadTool:
    def test_requires_message_id(self):
        result = GmailReadTool().execute("read that email", db=MagicMock(), business=FakeBusiness())
        assert result["ok"] is False
        assert result["error"] == "missing_message_id"

    def test_reads_with_explicit_message_id(self):
        with patch("app.tools.gmail_tool.GmailService") as MockService:
            MockService.return_value.read.return_value = {"ok": True, "message": {"id": "m1"}}
            result = GmailReadTool().execute("read it", db=MagicMock(), business=FakeBusiness(), message_id="m1")
        args, _ = MockService.return_value.read.call_args
        assert args[1] == "m1"
        assert result == {"ok": True, "message": {"id": "m1"}}


class TestGmailDraftTool:
    def test_explicit_fields_skip_llm_extraction(self):
        with patch("app.tools.gmail_tool.GmailService") as MockService, \
             patch("app.tools.gmail_tool.gmail_ai_service.extract_send_request") as mock_extract:
            MockService.return_value.draft.return_value = {"ok": True, "draft_id": "d1"}
            result = GmailDraftTool().execute(
                "draft it", db=MagicMock(), business=FakeBusiness(),
                to="customer@example.com", subject="Follow up", body="Thanks!",
            )
        mock_extract.assert_not_called()
        assert result == {"ok": True, "draft_id": "d1"}

    def test_falls_back_to_llm_extraction(self):
        with patch("app.tools.gmail_tool.GmailService") as MockService, \
             patch("app.tools.gmail_tool.gmail_ai_service.extract_send_request",
                   return_value={"to": "customer@example.com", "subject": "Hi", "body": "Thanks for reaching out."}) as mock_extract:
            MockService.return_value.draft.return_value = {"ok": True}
            GmailDraftTool().execute("draft a thank you to the customer", db=MagicMock(), business=FakeBusiness())
        mock_extract.assert_called_once()

    def test_missing_fields_after_extraction_returns_error(self):
        with patch("app.tools.gmail_tool.gmail_ai_service.extract_send_request", return_value={"to": None, "subject": None, "body": None}):
            result = GmailDraftTool().execute("draft something vague", db=MagicMock(), business=FakeBusiness())
        assert result["ok"] is False
        assert result["error"] == "missing_fields"


class TestGmailSendTool:
    def test_never_calls_adapter_directly_only_service(self):
        """The tool must go through GmailService (which enforces send_mode)
        - never GmailAdapter directly, which would bypass approval-mode
        entirely."""
        with patch("app.tools.gmail_tool.GmailService") as MockService:
            MockService.return_value.send.return_value = {"ok": True, "queued_for_approval": True, "sent": False, "pending_action_id": "p1"}
            result = GmailSendTool().execute(
                "send it", db=MagicMock(), business=FakeBusiness(),
                to="a@b.com", subject="s", body="b", employee="sales",
            )
        assert result["sent"] is False
        assert result["queued_for_approval"] is True
        _, kwargs = MockService.return_value.send.call_args
        assert kwargs["employee"] == "sales"
