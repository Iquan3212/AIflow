"""
Centralized, single-source-of-truth constants for the Controlled Workflow
Automation pipeline (Phase 5) - the trigger/condition/action vocabulary a
Workflow's `conditions`/`actions` JSON is validated against at save time
(see service.py), so an unrecognized type is a real validation error when
a workflow is created/edited, never a silent no-op discovered only when
it fails to fire.
"""

from app.models import WorkflowTriggerType

# ---- trigger -> structured field vocabulary --------------------------
# What `condition.field` values are valid for each trigger type, and what
# top-level keys retrieve_trigger_data() guarantees will be present (see
# triggers.py). Conditions only ever read from this structured data -
# never from an LLM, never from free text (Step 6/7).
_LEAD_FIELDS = {
    "lead.status", "lead.service_interested", "lead.name", "lead.phone", "lead.email", "lead.budget",
    # Phase 11, additive: buyer_id/property_id let a workflow scope
    # itself to marketplace-sourced leads (e.g. `lead.buyer_id` is_set)
    # without a separate "marketplace_inquiry" trigger type; the
    # qualification fields let a workflow react to the Lead
    # Qualification AI employee's own assessment (Phase 10B).
    "lead.buyer_id", "lead.property_id", "lead.qualification_score", "lead.qualification_notes",
}

_APPOINTMENT_FIELDS = {
    "appointment.status", "appointment.service", "appointment.customer_name", "appointment.source",
    # Phase 11, additive: lets a workflow condition on whether this
    # appointment is a marketplace site visit (buyer_id/property_id set)
    # vs. a non-marketplace one (both null, exactly as before).
    "appointment.buyer_id", "appointment.property_id", "appointment.lead_id",
}

_BOOKING_FIELDS = {
    "booking.status", "booking.property_id", "booking.buyer_id", "booking.lead_id", "booking.appointment_id",
}

TRIGGER_FIELDS = {
    WorkflowTriggerType.lead_created: _LEAD_FIELDS,
    WorkflowTriggerType.appointment_created: _APPOINTMENT_FIELDS,
    WorkflowTriggerType.appointment_rescheduled: _APPOINTMENT_FIELDS,
    WorkflowTriggerType.appointment_cancelled: _APPOINTMENT_FIELDS,
    WorkflowTriggerType.support_escalated: {
        "support.priority", "support.status", "support.issue_summary",
    },
    # ---- Phase 11: real-estate workflow triggers -----------------------
    WorkflowTriggerType.lead_status_changed: _LEAD_FIELDS,
    WorkflowTriggerType.lead_qualified: _LEAD_FIELDS,
    WorkflowTriggerType.appointment_confirmed: _APPOINTMENT_FIELDS,
    WorkflowTriggerType.appointment_completed: _APPOINTMENT_FIELDS,
    WorkflowTriggerType.appointment_no_show: _APPOINTMENT_FIELDS,
    WorkflowTriggerType.booking_initiated: _BOOKING_FIELDS,
    WorkflowTriggerType.booking_confirmed: _BOOKING_FIELDS,
    WorkflowTriggerType.booking_cancelled: _BOOKING_FIELDS,
    WorkflowTriggerType.booking_completed: _BOOKING_FIELDS,
}

# ---- condition operators ----------------------------------------------
OPERATOR_EQ = "eq"
OPERATOR_NEQ = "neq"
OPERATOR_IS_SET = "is_set"
OPERATOR_IS_NOT_SET = "is_not_set"
OPERATOR_CONTAINS = "contains"

CONDITION_OPERATORS = frozenset({OPERATOR_EQ, OPERATOR_NEQ, OPERATOR_IS_SET, OPERATOR_IS_NOT_SET, OPERATOR_CONTAINS})

# ---- action types -------------------------------------------------------
# Every action type here maps to exactly one real, existing, registered
# executor in actions.py - never arbitrary code, never a string the
# engine "interprets" some other way (Step 22: only registered, validated
# actions may execute).
ACTION_SEND_NOTIFICATION = "send_notification"
ACTION_CREATE_GMAIL_DRAFT = "create_gmail_draft"
ACTION_SEND_GMAIL = "send_gmail"
ACTION_REQUEST_APPROVAL = "request_approval"
# Phase 11: the AI-workforce action type - runs exactly ONE existing,
# bounded, tool-calling real-estate specialist (see actions.py's
# _action_run_ai_specialist) through the SAME ManagerAgent/Registry/
# ToolRouter pipeline every other AI Workforce call already goes
# through. Never a second AI brain, never a chain/loop - one specialist,
# one turn, per workflow-run action, exactly as configured.
ACTION_RUN_AI_SPECIALIST = "run_ai_specialist"

ACTION_TYPES = frozenset({
    ACTION_SEND_NOTIFICATION, ACTION_CREATE_GMAIL_DRAFT, ACTION_SEND_GMAIL, ACTION_REQUEST_APPROVAL,
    ACTION_RUN_AI_SPECIALIST,
})

# Which specialist names run_ai_specialist may target is validated at RUN
# time in actions.py, against app.agents.manager_agent.SPECIALIST_ORDER
# directly (the single source of truth for the real-estate specialist
# roster) - not duplicated here, matching this module's own existing
# pattern of leaving action-type-specific config (e.g.
# send_notification's event_type) to the executor, not save-time
# validation (see service.py's validate_workflow_config(), which only
# checks the action `type` itself against ACTION_TYPES above).

# A workflow may have at most this many actions - a controlled automation
# layer, not a general-purpose scripting surface (see ARCHITECTURE.md's
# "not an autonomous AI agent" framing).
MAX_ACTIONS_PER_WORKFLOW = 10
MAX_CONDITIONS_PER_WORKFLOW = 10

# ---- retry / failure (Step 13) -----------------------------------------
# Only transient, explicitly-classified provider errors are retried (see
# actions.py's use of LLMProviderError-style classification is NOT used
# here - Gmail/notification failures already return a real ok=False with
# a reason, not a raised exception in the common case). Bounded and small
# - a workflow action is a real side effect (an email, a notification);
# this is not a background job queue with exponential backoff infra.
MAX_ACTION_RETRIES = 2
