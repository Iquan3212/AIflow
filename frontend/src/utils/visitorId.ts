// A browser-generated UUID identifying the same anonymous visitor across
// messages, exactly the convention conversation_service.py's own
// docstring describes for the website widget - persisted so refreshing
// the page keeps the same conversation thread.
const KEY = "aiflow.marketplace_visitor_id";

export function getOrCreateVisitorId(): string {
    let id = localStorage.getItem(KEY);
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem(KEY, id);
    }
    return id;
}
