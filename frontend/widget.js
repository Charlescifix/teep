/*
 * TEEP chat widget - embeddable launcher for the RAG assistant.
 *
 * Drop one tag on any page:
 *   <script src="https://YOUR-SERVICE.up.railway.app/widget.js" defer></script>
 *
 * The API origin is taken from this script's own src, so the host page never
 * has to name it twice. Override with data-api-base when the API lives
 * somewhere other than where the script is served from.
 *
 * Everything renders inside a shadow root. teep.africa is a Tailwind SPA, and
 * without that isolation its resets and the widget's rules would fight.
 */
(function () {
  "use strict";

  // Netlify snippet injection and a hard-coded tag can both end up on a page.
  if (window.__teepChatWidget) return;
  window.__teepChatWidget = true;

  var script =
    document.currentScript ||
    (function () {
      var all = document.getElementsByTagName("script");
      return all[all.length - 1];
    })();

  function attr(name, fallback) {
    var v = script && script.getAttribute(name);
    return v === null || v === undefined || v === "" ? fallback : v;
  }

  // ---- Configuration -------------------------------------------------------

  var apiBase = attr("data-api-base", "");
  if (!apiBase && script && script.src) {
    try {
      apiBase = new URL(script.src, window.location.href).origin;
    } catch (e) {
      apiBase = "";
    }
  }
  apiBase = String(apiBase).replace(/\/+$/, "");

  var ENDPOINT = apiBase + "/api/chat";
  var BRAND = attr("data-brand", "#00325e");
  var ACCENT = attr("data-accent", "#fbc410");
  var TITLE = attr("data-title", "TEEP Assistant");
  var SUBTITLE = attr("data-subtitle", "Ask about payments, refunds and more");
  var GREETING = attr(
    "data-greeting",
    "Hi! I'm TEEP's assistant. Ask me about bill payments, refunds, our referral programme, or anything else about TEEP."
  );
  var TIMEOUT_MS = parseInt(attr("data-timeout", "45000"), 10) || 45000;

  var SUGGESTIONS = [
    "How do I create an account?",
    "How long do refunds take?",
    "What bills can I pay?"
  ];

  // ---- Shadow root ---------------------------------------------------------

  var host = document.createElement("div");
  host.id = "teep-chat-widget";
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  var style = document.createElement("style");
  style.textContent = [
    ":host,*{box-sizing:border-box;}",
    ".wrap{position:fixed;right:20px;bottom:20px;z-index:2147483000;",
    "font-family:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}",

    ".launcher{width:58px;height:58px;border:0;border-radius:50%;cursor:pointer;",
    "background:" + BRAND + ";color:" + ACCENT + ";display:flex;align-items:center;justify-content:center;",
    "box-shadow:0 8px 24px rgba(0,50,94,.32);transition:transform .18s ease,box-shadow .18s ease;}",
    ".launcher:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(0,50,94,.4);}",
    ".launcher:focus-visible{outline:3px solid " + ACCENT + ";outline-offset:3px;}",
    ".launcher svg{width:27px;height:27px;}",
    ".launcher[hidden]{display:none;}",

    ".panel{position:fixed;right:20px;bottom:20px;width:384px;height:min(600px,calc(100vh - 40px));",
    "background:#fff;border-radius:16px;overflow:hidden;display:flex;flex-direction:column;",
    "box-shadow:0 24px 60px rgba(15,23,42,.24),0 0 0 1px rgba(15,23,42,.06);",
    "opacity:0;transform:translateY(12px) scale(.98);pointer-events:none;",
    "transition:opacity .2s ease,transform .2s ease;}",
    ".panel.open{opacity:1;transform:none;pointer-events:auto;}",

    ".head{background:" + BRAND + ";color:#fff;padding:16px 18px;display:flex;align-items:center;gap:12px;flex:0 0 auto;}",
    ".mark{width:38px;height:38px;border-radius:50%;background:" + ACCENT + ";color:" + BRAND + ";",
    "display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;letter-spacing:.5px;flex:0 0 auto;}",
    ".ht{flex:1 1 auto;min-width:0;}",
    ".head h2{margin:0;font-size:15px;font-weight:650;line-height:1.25;}",
    ".head p{margin:2px 0 0;font-size:12px;line-height:1.3;color:rgba(255,255,255,.75);}",
    ".x{margin-left:auto;background:transparent;border:0;color:rgba(255,255,255,.8);cursor:pointer;",
    "padding:6px;border-radius:8px;display:flex;flex:0 0 auto;}",
    ".x:hover{background:rgba(255,255,255,.14);color:#fff;}",
    ".x:focus-visible{outline:2px solid " + ACCENT + ";outline-offset:1px;}",

    ".log{flex:1 1 auto;overflow-y:auto;padding:16px;background:#f8fafc;",
    "display:flex;flex-direction:column;gap:10px;scrollbar-width:thin;}",
    ".log::-webkit-scrollbar{width:6px;}",
    ".log::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px;}",
    ".msg{max-width:84%;padding:10px 13px;font-size:14px;line-height:1.5;white-space:pre-wrap;",
    "overflow-wrap:anywhere;border-radius:14px;}",
    ".bot{align-self:flex-start;background:#fff;color:#0f172a;border:1px solid #e2e8f0;border-bottom-left-radius:4px;}",
    ".me{align-self:flex-end;background:" + BRAND + ";color:#fff;border-bottom-right-radius:4px;}",
    ".err{align-self:flex-start;background:#fef2f2;color:#991b1b;border:1px solid #fecaca;border-bottom-left-radius:4px;}",

    ".chips{display:flex;flex-wrap:wrap;gap:7px;padding:2px 0 4px;}",
    ".chip{background:#fff;border:1px solid " + BRAND + "33;color:" + BRAND + ";border-radius:999px;",
    "padding:7px 12px;font-size:12.5px;font-family:inherit;cursor:pointer;transition:background .15s ease,border-color .15s ease;}",
    ".chip:hover{background:" + ACCENT + "1f;border-color:" + ACCENT + ";}",
    ".chip:focus-visible{outline:2px solid " + BRAND + ";outline-offset:1px;}",

    ".dots{align-self:flex-start;background:#fff;border:1px solid #e2e8f0;border-radius:14px;",
    "border-bottom-left-radius:4px;padding:13px;display:flex;gap:4px;}",
    ".dots i{width:7px;height:7px;border-radius:50%;background:#94a3b8;animation:b 1.3s infinite ease-in-out;}",
    ".dots i:nth-child(2){animation-delay:.18s;}",
    ".dots i:nth-child(3){animation-delay:.36s;}",
    "@keyframes b{0%,60%,100%{opacity:.3;transform:translateY(0);}30%{opacity:1;transform:translateY(-3px);}}",

    ".bar{flex:0 0 auto;border-top:1px solid #e2e8f0;background:#fff;padding:10px 12px;display:flex;gap:8px;align-items:flex-end;}",
    "textarea{flex:1 1 auto;resize:none;border:1px solid #e2e8f0;border-radius:11px;padding:10px 12px;",
    "font-family:inherit;font-size:14px;line-height:1.45;color:#0f172a;max-height:112px;background:#fff;}",
    "textarea:focus{outline:0;border-color:" + BRAND + ";box-shadow:0 0 0 3px " + BRAND + "1a;}",
    "textarea::placeholder{color:#94a3b8;}",
    ".send{flex:0 0 auto;width:40px;height:40px;border:0;border-radius:11px;cursor:pointer;",
    "background:" + ACCENT + ";color:" + BRAND + ";display:flex;align-items:center;justify-content:center;transition:filter .15s ease;}",
    ".send:hover:not(:disabled){filter:brightness(.94);}",
    ".send:disabled{opacity:.45;cursor:not-allowed;}",
    ".send:focus-visible{outline:2px solid " + BRAND + ";outline-offset:2px;}",
    ".send svg{width:18px;height:18px;}",

    ".sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}",

    "@media (max-width:480px){",
    ".panel{right:0;bottom:0;width:100vw;height:100dvh;max-height:100dvh;border-radius:0;}",
    ".wrap{right:14px;bottom:14px;}",
    ".msg{max-width:88%;}}",

    "@media (prefers-reduced-motion:reduce){",
    ".panel,.launcher{transition:none;}.dots i{animation:none;}}"
  ].join("");

  var wrap = document.createElement("div");
  wrap.className = "wrap";
  wrap.innerHTML = [
    '<button class="launcher" type="button" aria-label="Open the TEEP chat assistant" aria-expanded="false">',
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3C6.98 3 3 6.58 3 11c0 2.28 1.06 4.33 2.79 5.78-.12 1.2-.5 2.53-1.32 3.63 1.83-.23 3.3-.93 4.38-1.66 1 .3 2.06.46 3.15.46 5.02 0 9-3.58 9-8s-3.98-8-9-8Z"/></svg>',
    "</button>",
    '<section class="panel" role="dialog" aria-label="TEEP chat assistant" aria-hidden="true">',
    '<header class="head">',
    '<span class="mark" aria-hidden="true">TP</span>',
    '<span class="ht"><h2></h2><p></p></span>',
    '<button class="x" type="button" aria-label="Close chat">',
    '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    "</button></header>",
    '<div class="log" role="log" aria-live="polite" aria-atomic="false"></div>',
    '<form class="bar">',
    '<label class="sr" for="teep-q">Your question</label>',
    '<textarea id="teep-q" rows="1" placeholder="Ask about TEEP…"></textarea>',
    '<button class="send" type="submit" aria-label="Send message">',
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3.4 20.4 21 12 3.4 3.6 3.39 10.1 15.5 12 3.39 13.9z"/></svg>',
    "</button></form></section>"
  ].join("");

  root.appendChild(style);
  root.appendChild(wrap);

  var launcher = wrap.querySelector(".launcher");
  var panel = wrap.querySelector(".panel");
  var log = wrap.querySelector(".log");
  var form = wrap.querySelector("form");
  var input = wrap.querySelector("textarea");
  var sendBtn = wrap.querySelector(".send");

  wrap.querySelector(".head h2").textContent = TITLE;
  wrap.querySelector(".head p").textContent = SUBTITLE;

  // ---- Rendering -----------------------------------------------------------

  var busy = false;
  var typingEl = null;

  function scroll() {
    log.scrollTop = log.scrollHeight;
  }

  function bubble(text, kind) {
    var el = document.createElement("div");
    el.className = "msg " + kind;
    el.textContent = text; // never innerHTML: this is model output
    log.appendChild(el);
    scroll();
    return el;
  }

  function showSuggestions() {
    var box = document.createElement("div");
    box.className = "chips";
    SUGGESTIONS.forEach(function (q) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = q;
      b.addEventListener("click", function () {
        box.remove();
        ask(q);
      });
      box.appendChild(b);
    });
    log.appendChild(box);
    scroll();
  }

  function typing(on) {
    if (on) {
      typingEl = document.createElement("div");
      typingEl.className = "dots";
      typingEl.setAttribute("aria-label", "Assistant is typing");
      typingEl.innerHTML = "<i></i><i></i><i></i>";
      log.appendChild(typingEl);
      scroll();
    } else if (typingEl) {
      typingEl.remove();
      typingEl = null;
    }
  }

  function setBusy(v) {
    busy = v;
    sendBtn.disabled = v;
    input.disabled = v;
  }

  // ---- Network -------------------------------------------------------------

  function ask(query) {
    if (busy) return;
    bubble(query, "me");
    setBusy(true);
    typing(true);

    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = setTimeout(function () {
      if (ctrl) ctrl.abort();
    }, TIMEOUT_MS);

    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_query: query }),
      signal: ctrl ? ctrl.signal : undefined
    })
      .then(function (res) {
        var ct = res.headers.get("content-type") || "";
        // A response that isn't JSON means the request never reached the API -
        // most likely the static host answered with its SPA shell.
        if (ct.indexOf("application/json") === -1) {
          throw new Error(
            "Expected JSON from " + ENDPOINT + " but got '" + ct + "' (HTTP " +
            res.status + "). Check the API base points at the chat API, not the website."
          );
        }
        return res.json().then(function (data) {
          // 429 is the one error the customer can act on, and the API words it
          // for them - show it as sent instead of the generic failure line.
          if (res.status === 429) {
            var e = new Error("rate limited");
            e.userMessage =
              typeof data.detail === "string"
                ? data.detail
                : "You're sending messages too quickly. Please wait a moment.";
            throw e;
          }
          if (!res.ok) {
            throw new Error(
              "HTTP " + res.status + ": " +
              (data && data.detail ? JSON.stringify(data.detail) : "")
            );
          }
          return data;
        });
      })
      .then(function (data) {
        typing(false);
        var answer = data && data.answer;
        bubble(
          answer && String(answer).trim()
            ? answer
            : "Sorry, I couldn't put an answer together. Please email support@teep.africa.",
          "bot"
        );
      })
      .catch(function (err) {
        typing(false);
        var aborted = err && (err.name === "AbortError" || /abort/i.test(err.message || ""));
        if (err && err.userMessage) {
          bubble(err.userMessage, "err");
        } else {
          bubble(
            aborted
              ? "That took longer than expected. Please try again, or email support@teep.africa."
              : "Sorry, I can't reach the assistant right now. Please try again shortly, or email support@teep.africa.",
            "err"
          );
          console.error("[TEEP widget]", err);
        }
      })
      .then(function () {
        clearTimeout(timer);
        setBusy(false);
        if (panel.classList.contains("open")) input.focus();
      });
  }

  // ---- Interaction ---------------------------------------------------------

  var started = false;

  function open() {
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    launcher.hidden = true;
    launcher.setAttribute("aria-expanded", "true");
    if (!started) {
      started = true;
      bubble(GREETING, "bot");
      showSuggestions();
    }
    input.focus();
  }

  function close() {
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    launcher.hidden = false;
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  }

  launcher.addEventListener("click", open);
  wrap.querySelector(".x").addEventListener("click", close);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q || busy) return;
    input.value = "";
    input.style.height = "auto";
    ask(q);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

  // Grow the box with the question, up to the max-height set in CSS.
  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 112) + "px";
  });

  wrap.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && panel.classList.contains("open")) close();
  });

  // A hook so the site can open the chat from its own "Talk to us" CTA.
  window.TeepChat = { open: open, close: close, ask: ask, endpoint: ENDPOINT };

  function mount() {
    document.body.appendChild(host);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
