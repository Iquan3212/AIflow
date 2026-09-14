"""
OpenAI-style function-calling schemas for the Phase 10A real-estate tools
(app/tools/realestate_lead_property_tools.py,
app/tools/realestate_visit_followup_tools.py), in the same shape already
used by app/agents/dashboard_tools.py and
app/services/scheduling/tools.py's tool_definitions(). Keyed by tool
name (matching Registry tool names) so a tool-calling-capable employee's
`tools=[...]` list can be turned into the exact schema list to pass to
chat_completion(tools=...).

Deliberately excludes `agency_id`/`agency_slug`/any tenant identifier
from every schema below - the model is never given a way to supply one
(Phase 10A spec Step 5); the tenant is always the authenticated caller's
own Agency, injected by ToolRouter's context.
"""

REALESTATE_TOOL_SCHEMAS: dict[str, dict] = {
    "get_lead": {
        "type": "function",
        "function": {
            "name": "get_lead",
            "description": "Get the real, current CRM record for one lead by id. Use before claiming anything about a lead's contact info or status.",
            "parameters": {
                "type": "object",
                "properties": {"lead_id": {"type": "string", "description": "The lead's id."}},
                "required": ["lead_id"],
            },
        },
    },
    "update_lead_qualification": {
        "type": "function",
        "function": {
            "name": "update_lead_qualification",
            "description": "Update a lead's qualification status (e.g. contacted, qualified, negotiating).",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["new", "contacted", "qualified", "site_visit_scheduled", "visited", "negotiating", "converted", "lost"],
                    },
                },
                "required": ["lead_id", "status"],
            },
        },
    },
    "search_properties": {
        "type": "function",
        "function": {
            "name": "search_properties",
            "description": "Search this agency's own real inventory for units matching filters. Never invents units - only returns what actually exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "status": {"type": "string"},
                    "property_type": {"type": "string"},
                    "bhk": {"type": "integer"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "city": {"type": "string"},
                    "locality": {"type": "string"},
                    "floor": {"type": "integer"},
                    "facing": {"type": "string"},
                },
            },
        },
    },
    "search_projects": {
        "type": "function",
        "function": {
            "name": "search_projects",
            "description": "List this agency's own real projects, optionally filtered by a name/city/locality/developer search term.",
            "parameters": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
            },
        },
    },
    "get_property": {
        "type": "function",
        "function": {
            "name": "get_property",
            "description": "Get the real, current detail for one property/unit by id (price, availability, specs).",
            "parameters": {
                "type": "object",
                "properties": {"property_id": {"type": "string"}},
                "required": ["property_id"],
            },
        },
    },
    "get_available_slots": {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Get this agency's real open site-visit slots for one calendar day.",
            "parameters": {
                "type": "object",
                "properties": {"date_local": {"type": "string", "description": "YYYY-MM-DD"}},
                "required": ["date_local"],
            },
        },
    },
    "propose_visit": {
        "type": "function",
        "function": {
            "name": "propose_visit",
            "description": "Propose scheduling a site visit for a lead at a property/unit and time. Does NOT book anything - creates a pending request for a human to approve.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string"},
                    "property_id": {"type": "string"},
                    "start_local_iso": {"type": "string", "description": "YYYY-MM-DDTHH:MM in the agency's local time"},
                },
                "required": ["lead_id", "property_id", "start_local_iso"],
            },
        },
    },
    "confirm_visit": {
        "type": "function",
        "function": {
            "name": "confirm_visit",
            "description": "Propose confirming an already-scheduled site visit. Does NOT change any status - creates a pending request for a human to approve.",
            "parameters": {
                "type": "object",
                "properties": {"appointment_id": {"type": "string"}},
                "required": ["appointment_id"],
            },
        },
    },
    "create_follow_up": {
        "type": "function",
        "function": {
            "name": "create_follow_up",
            "description": "Propose a follow-up action on a lead (e.g. 'call back next Tuesday'). Creates a pending request for a human to review and act on.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string"},
                    "note": {"type": "string"},
                    "due_local_iso": {"type": "string"},
                },
                "required": ["lead_id", "note"],
            },
        },
    },
    "draft_customer_message": {
        "type": "function",
        "function": {
            "name": "draft_customer_message",
            "description": "Draft a message to a lead for a human to review. Does NOT send anything.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string"},
                    "message_body": {"type": "string"},
                },
                "required": ["lead_id", "message_body"],
            },
        },
    },
}
