"""
Regression coverage for a real bug report: a customer's lead is captured
correctly on the first turn of a conversation (e.g. just a name), but
information given in LATER turns (property requirement, budget) never
shows up on the same lead - the Leads page keeps showing the original,
incomplete record.

This drives the REAL, full customer-conversation pipeline
(conversation_service.process_message_for_agency(), the same function the
website widget/WhatsApp/Instagram all go through) across MULTIPLE
separate calls - one per "turn" - exactly as separate HTTP requests would,
threading `visitor_id`/`conversation_id` forward the same way the real
frontend does. Only `chat_completion` is mocked (to return a scripted
tool call each turn); everything else - conversation/lead lookup,
ToolDispatcher._save_lead_info, the DB - is real. Zero LLM tokens.

Canonical Lead fields (app/models.py): name, phone, email,
service_interested, budget - all plain strings. This is the actual,
current real-estate lead model; no budget_min/budget_max or bhk/
property_type split exists anywhere in the schema, so none is invented
here.

Run: python3 -m pytest tests/test_lead_enrichment_across_turns.py -q   (from backend/)
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app import models
from app.services.shared import conversation_service


def _make_agency(suffix: str):
    db = SessionLocal()
    agency = models.Agency(
        name=f"Lead Enrichment Test {suffix}",
        slug=f"lead-enrich-test-{suffix}-{uuid.uuid4().hex[:10]}",
        contact_email=f"owner-{suffix}@leadenrichtest.example",
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    db.add(models.ChatbotConfig(
        agency_id=agency.id,
        business_description="UrbanNest Realty sells real estate.",
        services=["Apartments"],
        faqs=[],
    ))
    db.commit()
    db.refresh(agency)
    return db, agency


def _cleanup(db, agency):
    db.query(models.Message).filter(
        models.Message.conversation_id.in_(
            db.query(models.Conversation.id).filter(models.Conversation.agency_id == agency.id)
        )
    ).delete(synchronize_session=False)
    db.query(models.Lead).filter(models.Lead.agency_id == agency.id).delete()
    db.query(models.Conversation).filter(models.Conversation.agency_id == agency.id).delete()
    db.query(models.ChatbotConfig).filter(models.ChatbotConfig.agency_id == agency.id).delete()
    db.query(models.Agency).filter(models.Agency.id == agency.id).delete()
    db.commit()
    db.close()


@pytest.fixture
def agency():
    db, biz = _make_agency("a")
    try:
        yield db, biz
    finally:
        _cleanup(db, biz)


@pytest.fixture
def two_agencies():
    db1, biz1 = _make_agency("x")
    db2, biz2 = _make_agency("y")
    try:
        yield (db1, biz1), (db2, biz2)
    finally:
        _cleanup(db1, biz1)
        _cleanup(db2, biz2)


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tool_call(args_json: str, call_id="call_1", name="save_lead_info"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=args_json))


def _send_turn(db, agency, message, tool_args_json, visitor_id="test-visitor", conversation_id=None):
    """One real customer-conversation turn: chat_completion first returns a
    save_lead_info tool call with the given args, then a plain-text reply
    (mirroring exactly what _run_tool_loop expects: a tool-call round,
    then a follow-up completion to phrase the reply)."""
    with patch("app.services.shared.conversation_service.chat_completion") as mock_chat:
        mock_chat.side_effect = [
            _msg(content="", tool_calls=[_tool_call(tool_args_json)]),
            _msg(content="Got it, thanks!"),
        ]
        result = conversation_service.process_message_for_agency(
            db, agency=agency, visitor_id=visitor_id, conversation_id=conversation_id,
            message=message, channel="website",
        )
    return result


def _get_lead(db, agency_id):
    return db.query(models.Lead).filter(models.Lead.agency_id == agency_id).all()


class TestProgressiveLeadEnrichmentAcrossTurns:
    def test_name_then_service_then_budget_enrich_the_same_lead(self, agency):
        db, biz = agency

        r1 = _send_turn(db, biz, "My name is Rahul.", '{"name": "Rahul"}')
        conv_id = r1["conversation_id"]

        leads = _get_lead(db, biz.id)
        assert len(leads) == 1, "expected exactly one lead after turn 1"
        assert leads[0].name == "Rahul"
        assert leads[0].service_interested is None
        assert leads[0].budget is None

        _send_turn(db, biz, "I'm looking for a 3 BHK property.",
                   '{"service_interested": "3 BHK"}', conversation_id=conv_id)

        leads = _get_lead(db, biz.id)
        assert len(leads) == 1, "a second turn must enrich the same lead, never create a new one"
        assert leads[0].name == "Rahul", "the name captured in turn 1 must survive turn 2's update"
        assert leads[0].service_interested == "3 BHK"
        assert leads[0].budget is None

        _send_turn(db, biz, "My budget is ₹1.5 crore.",
                   '{"budget": "₹1.5 crore"}', conversation_id=conv_id)

        leads = _get_lead(db, biz.id)
        assert len(leads) == 1, "a third turn must still enrich the same single lead"
        final = leads[0]
        assert final.name == "Rahul"
        assert final.service_interested == "3 BHK"
        assert final.budget == "₹1.5 crore"

    def test_a_turn_with_no_new_information_does_not_erase_existing_fields(self, agency):
        db, biz = agency
        r1 = _send_turn(db, biz, "My name is Rahul, looking for a 3 BHK, budget 1.5 crore.",
                         '{"name": "Rahul", "service_interested": "3 BHK", "budget": "₹1.5 crore"}')
        conv_id = r1["conversation_id"]

        # A later turn's extraction returns nothing new for any field
        # (e.g. the model correctly determined there was nothing to save,
        # or - the actual case this guards - it passes empty strings for
        # fields it has no new value for rather than omitting them).
        _send_turn(db, biz, "Can I get a site visit?",
                   '{"name": "", "service_interested": "", "budget": ""}', conversation_id=conv_id)

        leads = _get_lead(db, biz.id)
        assert len(leads) == 1
        assert leads[0].name == "Rahul"
        assert leads[0].service_interested == "3 BHK"
        assert leads[0].budget == "₹1.5 crore"

    def test_out_of_order_single_field_updates_never_duplicate_the_lead(self, agency):
        """Same scenario as the bug report, but budget arrives before the
        property requirement - order must not matter."""
        db, biz = agency
        r1 = _send_turn(db, biz, "My budget is 1.5 crore.", '{"budget": "1.5 crore"}')
        conv_id = r1["conversation_id"]
        _send_turn(db, biz, "I want a 3 BHK in Whitefield.",
                   '{"service_interested": "3 BHK in Whitefield"}', conversation_id=conv_id)
        _send_turn(db, biz, "My name is Rahul.", '{"name": "Rahul"}', conversation_id=conv_id)

        leads = _get_lead(db, biz.id)
        assert len(leads) == 1
        assert leads[0].name == "Rahul"
        assert leads[0].service_interested == "3 BHK in Whitefield"
        assert leads[0].budget == "1.5 crore"


class TestConversationContinuityDrivesLeadIdentity:
    def test_a_different_conversation_id_correctly_creates_a_separate_lead(self, agency):
        """Not a bug: two genuinely different conversations (e.g. two
        different visitors) must get two different leads - enrichment
        should only merge turns that are actually the same conversation."""
        db, biz = agency
        _send_turn(db, biz, "My name is Rahul.", '{"name": "Rahul"}', visitor_id="visitor-1")
        _send_turn(db, biz, "My name is Priya.", '{"name": "Priya"}', visitor_id="visitor-2")

        leads = _get_lead(db, biz.id)
        names = sorted(l.name for l in leads)
        assert names == ["Priya", "Rahul"]

    def test_missing_conversation_id_falls_back_to_the_visitors_own_thread_not_a_new_one(self, agency):
        """Mirrors the real widget/frontend behavior (services/conversation.ts,
        widget/widget.js): if the caller doesn't pass conversation_id back
        (e.g. first render after a page reload before it's been persisted
        client-side), the same visitor_id on the same channel must still
        resolve to their existing conversation and lead, not fork a new one."""
        db, biz = agency
        _send_turn(db, biz, "My name is Rahul.", '{"name": "Rahul"}', visitor_id="visitor-1", conversation_id=None)
        # conversation_id intentionally omitted again, exactly like a client
        # that hasn't (yet) echoed back the id from the first response.
        _send_turn(db, biz, "3 BHK please.", '{"service_interested": "3 BHK"}',
                   visitor_id="visitor-1", conversation_id=None)

        leads = _get_lead(db, biz.id)
        assert len(leads) == 1
        assert leads[0].name == "Rahul"
        assert leads[0].service_interested == "3 BHK"


class TestTenantIsolation:
    def test_lead_id_is_correctly_scoped_to_its_own_agency(self, two_agencies):
        (db1, biz1), (db2, biz2) = two_agencies
        _send_turn(db1, biz1, "My name is Rahul.", '{"name": "Rahul"}', visitor_id="same-visitor-id")
        _send_turn(db2, biz2, "My name is Priya.", '{"name": "Priya"}', visitor_id="same-visitor-id")

        leads1 = _get_lead(db1, biz1.id)
        leads2 = _get_lead(db2, biz2.id)
        assert len(leads1) == 1 and leads1[0].name == "Rahul"
        assert len(leads2) == 1 and leads2[0].name == "Priya"
        # Neither agency's lead list contains the other agency's lead.
        assert biz2.id not in [l.agency_id for l in leads1]
        assert biz1.id not in [l.agency_id for l in leads2]
