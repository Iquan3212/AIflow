/**
 * AIFlow embeddable widget.
 *
 * Deliberately vanilla JS, not a Next.js/React component: this file has to
 * drop into a CUSTOMER's own website — WordPress, Shopify, a static HTML
 * page, anything — with a single <script> tag, the same way Intercom or
 * Tawk.to embed. The Next.js app in this repo is AIFlow's own dashboard,
 * a separate thing from what ships to customer sites. See ARCHITECTURE.md.
 *
 * Usage:
 *   <script src="https://yourdomain.com/widget.js"
 *           data-business-id="demo-business"
 *           data-api-base="https://api.yourdomain.com"
 *           data-color="#0E6E5C"></script>
 */
(function () {
  const scriptTag = document.currentScript;
  const businessSlug = scriptTag.getAttribute("data-business-id");
  const apiBase = scriptTag.getAttribute("data-api-base") || "http://localhost:8000";
  const brandColor = scriptTag.getAttribute("data-color") || "#0E6E5C";

  if (!businessSlug) {
    console.error("[AIFlow Widget] Missing data-business-id attribute on the script tag.");
    return;
  }

  const VISITOR_KEY = `aiflow_visitor_${businessSlug}`;
  const CONVO_KEY = `aiflow_conversation_${businessSlug}`;

  function getVisitorId() {
    let id = localStorage.getItem(VISITOR_KEY);
    if (!id) {
      id = "visitor_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(VISITOR_KEY, id);
    }
    return id;
  }

  function injectStyles() {
    const style = document.createElement("style");
    style.textContent = `
      #aiflow-bubble {
        position: fixed; bottom: 24px; right: 24px; width: 60px; height: 60px;
        border-radius: 50%; background: ${brandColor}; box-shadow: 0 8px 24px rgba(0,0,0,0.22);
        cursor: pointer; display: flex; align-items: center; justify-content: center;
        z-index: 999998; transition: transform 0.15s ease; border: none;
      }
      #aiflow-bubble:hover { transform: scale(1.06); }
      #aiflow-bubble svg { width: 26px; height: 26px; fill: #fff; }
      #aiflow-panel {
        position: fixed; bottom: 96px; right: 24px; width: 360px; max-width: calc(100vw - 32px);
        height: 520px; max-height: calc(100vh - 140px); background: #fff; border-radius: 16px;
        box-shadow: 0 16px 48px rgba(0,0,0,0.22); display: none; flex-direction: column;
        overflow: hidden; z-index: 999999;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      #aiflow-panel.open { display: flex; }
      #aiflow-header {
        background: ${brandColor}; color: #fff; padding: 16px 18px; font-weight: 600; font-size: 15px;
        display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;
      }
      #aiflow-close { cursor: pointer; opacity: 0.85; font-size: 22px; line-height: 1; background: none; border: none; color: #fff; }
      #aiflow-messages {
        flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px;
        background: #F6F7F6;
      }
      .aiflow-msg { max-width: 80%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; }
      .aiflow-msg.user { align-self: flex-end; background: ${brandColor}; color: #fff; border-bottom-right-radius: 4px; }
      .aiflow-msg.assistant { align-self: flex-start; background: #fff; color: #222; border: 1px solid #e8e8e6; border-bottom-left-radius: 4px; }
      .aiflow-msg.typing { align-self: flex-start; background: #fff; border: 1px solid #e8e8e6; color: #999; font-style: italic; }
      #aiflow-input-row { display: flex; border-top: 1px solid #eee; padding: 10px; gap: 8px; flex-shrink: 0; }
      #aiflow-input {
        flex: 1; border: 1px solid #ddd; border-radius: 20px; padding: 10px 14px;
        font-size: 14px; outline: none; font-family: inherit;
      }
      #aiflow-input:focus { border-color: ${brandColor}; }
      #aiflow-send {
        background: ${brandColor}; color: #fff; border: none; border-radius: 50%;
        width: 38px; height: 38px; cursor: pointer; flex-shrink: 0; font-size: 16px;
      }
      #aiflow-send:disabled { opacity: 0.5; cursor: default; }
    `;
    document.head.appendChild(style);
  }

  function buildDOM() {
    const bubble = document.createElement("button");
    bubble.id = "aiflow-bubble";
    bubble.setAttribute("aria-label", "Open chat");
    bubble.innerHTML =
      '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.03 2 11c0 2.4 1.05 4.57 2.76 6.17-.08.86-.36 2.5-1.1 3.83 0 0 2.1-.36 3.9-1.5.7.2 1.45.3 2.44.3 5.52 0 10-4.03 10-9s-4.48-8.8-10-8.8z"/></svg>';

    const panel = document.createElement("div");
    panel.id = "aiflow-panel";
    panel.innerHTML = `
      <div id="aiflow-header">
        <span id="aiflow-title">Chat with us</span>
        <button id="aiflow-close" aria-label="Close chat">&times;</button>
      </div>
      <div id="aiflow-messages"></div>
      <div id="aiflow-input-row">
        <input id="aiflow-input" type="text" placeholder="Type a message..." />
        <button id="aiflow-send" aria-label="Send message">&#10148;</button>
      </div>
    `;

    document.body.appendChild(bubble);
    document.body.appendChild(panel);
    return { bubble, panel };
  }

  function appendMessage(container, role, text) {
    const el = document.createElement("div");
    el.className = `aiflow-msg ${role}`;
    el.textContent = text;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
    return el;
  }

  async function sendMessage(text, messagesEl, sendBtn) {
    appendMessage(messagesEl, "user", text);
    const typingEl = appendMessage(messagesEl, "typing", "Typing...");
    sendBtn.disabled = true;

    try {
      const res = await fetch(`${apiBase}/conversation/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_slug: businessSlug,
          visitor_id: getVisitorId(),
          message: text,
          conversation_id: sessionStorage.getItem(CONVO_KEY) || null,
        }),
      });
      const data = await res.json();
      typingEl.remove();

      if (!res.ok) {
        appendMessage(messagesEl, "assistant", "Sorry, something went wrong. Please try again in a moment.");
        return;
      }

      sessionStorage.setItem(CONVO_KEY, data.conversation_id);
      appendMessage(messagesEl, "assistant", data.reply);
    } catch (err) {
      typingEl.remove();
      appendMessage(messagesEl, "assistant", "Connection error — please check your internet and try again.");
    } finally {
      sendBtn.disabled = false;
    }
  }

  function init() {
    injectStyles();
    const { bubble, panel } = buildDOM();
    const messagesEl = panel.querySelector("#aiflow-messages");
    const input = panel.querySelector("#aiflow-input");
    const sendBtn = panel.querySelector("#aiflow-send");
    const closeBtn = panel.querySelector("#aiflow-close");

    let opened = false;
    bubble.addEventListener("click", async () => {
      panel.classList.toggle("open");
      if (!opened && panel.classList.contains("open")) {
        opened = true;
        try {
          const res = await fetch(`${apiBase}/conversation/${businessSlug}/welcome`);
          const data = await res.json();
          panel.querySelector("#aiflow-title").textContent = data.business_name || "Chat with us";
          appendMessage(messagesEl, "assistant", data.welcome_message || "Hi! How can I help you today?");
        } catch (e) {
          appendMessage(messagesEl, "assistant", "Hi! How can I help you today?");
        }
        input.focus();
      }
    });

    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      panel.classList.remove("open");
    });

    function handleSend() {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      sendMessage(text, messagesEl, sendBtn);
    }

    sendBtn.addEventListener("click", handleSend);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleSend();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
