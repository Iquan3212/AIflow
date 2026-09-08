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
TRIGGER_FIELDS = {
    WorkflowTriggerType.lead_created: {
        "lead.status", "lead.service_interested", "lead.name", "lead.phone", "lead.email", "lead.budget",
    },
    WorkflowTriggerType.appointment_created: {
        "appointment.status", "appointment.service", "appointment.customer_name", "appointment.source",
    },
    WorkflowTriggerType.appointment_rescheduled: {
        "appointment.status", "appointment.service", "appointment.customer_name", "appointment.source",
    },
    WorkflowTriggerType.appointment_cancelled: {
        "appointment.status", "appointment.service", "appointment.customer_name", "appointment.source",
    },
    WorkflowTriggerType.support_escalated: {
        "support.priority", "support.status", "support.issue_summary",
    },
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

ACTION_TYPES = frozenset({
    ACTION_SEND_NOTIFICATION, ACTION_CREATE_GMAIL_DRAFT, ACTION_SEND_GMAIL, ACTION_REQUEST_APPROVAL,
})

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
