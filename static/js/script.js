/**
 * static/js/script.js
 * ------------------------------------------------------------
 * Refactored to a modular, maintainable architecture using
 * the Revealing Module Pattern. Each page-specific feature
 * lives in its own module, while site-wide UI and utilities
 * live in SharedComponents.
 *
 * Drop-in replacement: no external build tools required.
 * Safe to include with a plain <script src="/static/js/script.js"></script>
 *
 * Modules:
 *   - SharedComponents: sitewide utilities (alerts, modals, fetch helpers)
 *   - Playground: logic for playground.html
 *   - Humanizer: logic for the humanizer form page
 *   - TaskView: logic for view_task.html
 *
 * Conditional initialization:
 *   - Each module self-guards and only runs when its root
 *     container is found in the DOM (e.g., #playground-container).
 *
 * Global API:
 *   - window.App.showAlert(type, message, {timeout})
 *     Types: "success" | "info" | "warning" | "error"
 * ------------------------------------------------------------
 */

(function () {
  "use strict";

  // ----------------------------------------------------------
  // SharedComponents (Site-wide)
  // ----------------------------------------------------------
  const SharedComponents = (function () {
    // ------- Private state -------
    const SELECTORS = {
      alertRegion: "#global-alerts", // Optional container; created if missing
      modalOpenBtn: "[data-modal-target]",
      modalCloseBtn: "[data-modal-close]",
      modal: "[data-modal]"
    };

    // Cache created alert region
    let alertRegionEl = null;

    // ------- Utilities -------
    const qs = (sel, root = document) => root.querySelector(sel);
    const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    const on = (el, event, handler, opts) => el && el.addEventListener(event, handler, opts || false);
    const delegate = (root, event, selector, handler) => {
      if (!root) return;
      root.addEventListener(event, (e) => {
        const target = e.target.closest(selector);
        if (target && root.contains(target)) handler(e, target);
      });
    };

    const debounce = (fn, delay = 300) => {
      let t;
      return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(null, args), delay);
      };
    };

    const throttle = (fn, limit = 200) => {
      let inThrottle = false;
      return (...args) => {
        if (inThrottle) return;
        inThrottle = true;
        fn.apply(null, args);
        setTimeout(() => (inThrottle = false), limit);
      };
    };

    const uuid = () =>
      "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0,
          v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      });

    // CSRF: works with either <meta name="csrf-token"> or hidden input in forms
    const getCSRFToken = () => {
      const meta = qs('meta[name="csrf-token"]');
      if (meta && meta.content) return meta.content;
      const input = qs('input[name="csrf_token"]');
      return input ? input.value : null;
    };

    const serializeForm = (form) => {
      const data = new FormData(form);
      // Preserve action attribute; caller decides endpoint
      return data;
    };

    const jsonFetch = async (url, { method = "GET", data = null, headers = {}, signal } = {}) => {
      const csrf = getCSRFToken();
      const finalHeaders = Object.assign(
        { "Accept": "application/json" },
        csrf ? { "X-CSRFToken": csrf } : {},
        headers
      );

      let body;
      if (data && !(data instanceof FormData)) {
        finalHeaders["Content-Type"] = "application/json";
        body = JSON.stringify(data);
      } else {
        // Let browser set correct multipart/form-data boundary if FormData
        body = data || undefined;
      }

      const res = await fetch(url, { method, headers: finalHeaders, body, signal, credentials: "same-origin" });
      const contentType = res.headers.get("Content-Type") || "";
      const isJSON = contentType.includes("application/json");

      if (!res.ok) {
        let errPayload = {};
        try {
          errPayload = isJSON ? await res.json() : { detail: await res.text() };
        } catch (_) {
          // ignore parse error
        }
        const err = new Error(errPayload.message || errPayload.error || res.statusText || "Request failed");
        err.status = res.status;
        err.payload = errPayload;
        throw err;
      }

      return isJSON ? res.json() : res.text();
    };

    // ------- Alert System -------
    const ensureAlertRegion = () => {
      if (alertRegionEl && document.body.contains(alertRegionEl)) return alertRegionEl;

      alertRegionEl = qs(SELECTORS.alertRegion);
      if (!alertRegionEl) {
        alertRegionEl = document.createElement("div");
        alertRegionEl.id = SELECTORS.alertRegion.replace("#", "");
        alertRegionEl.setAttribute("role", "region");
        alertRegionEl.setAttribute("aria-label", "Notifications");
        alertRegionEl.style.position = "fixed";
        alertRegionEl.style.top = "1rem";
        alertRegionEl.style.right = "1rem";
        alertRegionEl.style.zIndex = "2147483647";
        alertRegionEl.style.display = "flex";
        alertRegionEl.style.flexDirection = "column";
        alertRegionEl.style.gap = "0.5rem";
        document.body.appendChild(alertRegionEl);
      }
      return alertRegionEl;
    };

    const showAlert = (type, message, { timeout = 5000 } = {}) => {
      const region = ensureAlertRegion();
      const id = `alert-${uuid()}`;

      const alert = document.createElement("div");
      alert.id = id;
      alert.setAttribute("role", "alert");
      alert.setAttribute("aria-live", "assertive");
      alert.style.padding = "0.75rem 1rem";
      alert.style.borderRadius = "0.5rem";
      alert.style.boxShadow = "0 10px 30px rgba(0,0,0,.15)";
      alert.style.maxWidth = "28rem";
      alert.style.fontSize = "0.95rem";
      alert.style.display = "flex";
      alert.style.alignItems = "flex-start";
      alert.style.gap = "0.75rem";
      alert.style.background = ({
        success: "#ecfdf5",
        info: "#eff6ff",
        warning: "#fffbeb",
        error: "#fef2f2"
      }[type] || "#eff6ff");
      alert.style.border = "1px solid " + ({
        success: "#10b981",
        info: "#3b82f6",
        warning: "#f59e0b",
        error: "#ef4444"
      }[type] || "#3b82f6") + "33"; // subtle border

      const dot = document.createElement("span");
      dot.style.display = "inline-block";
      dot.style.width = "0.6rem";
      dot.style.height = "0.6rem";
      dot.style.marginTop = "0.3rem";
      dot.style.borderRadius = "999px";
      dot.style.flex = "0 0 auto";
      dot.style.background = ({
        success: "#10b981",
        info: "#3b82f6",
        warning: "#f59e0b",
        error: "#ef4444"
      }[type] || "#3b82f6");

      const text = document.createElement("div");
      text.style.flex = "1 1 auto";
      text.style.color = "#0b0b0b";
      text.textContent = message;

      const close = document.createElement("button");
      close.type = "button";
      close.setAttribute("aria-label", "Close notification");
      close.textContent = "×";
      close.style.all = "unset";
      close.style.cursor = "pointer";
      close.style.fontSize = "1.25rem";
      close.style.lineHeight = "1";
      close.style.padding = "0 0.25rem";
      close.style.color = "#111827";
      on(close, "click", () => alert.remove());

      alert.appendChild(dot);
      alert.appendChild(text);
      alert.appendChild(close);
      region.appendChild(alert);

      if (timeout > 0) {
        setTimeout(() => alert.remove(), timeout);
      }

      return id;
    };

    // ------- Modal System -------
    const openModal = (modalEl) => {
      if (!modalEl) return;
      modalEl.setAttribute("aria-hidden", "false");
      modalEl.style.display = "block";
      document.documentElement.classList.add("no-scroll");
      const focusable = modalEl.querySelector("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
      if (focusable) focusable.focus();
    };

    const closeModal = (modalEl) => {
      if (!modalEl) return;
      modalEl.setAttribute("aria-hidden", "true");
      modalEl.style.display = "none";
      document.documentElement.classList.remove("no-scroll");
    };

    const initModals = () => {
      // Open via data-modal-target="#modalId"
      delegate(document, "click", SELECTORS.modalOpenBtn, (e, btn) => {
        e.preventDefault();
        const targetSel = btn.getAttribute("data-modal-target");
        const modal = targetSel ? qs(targetSel) : null;
        openModal(modal);
      });

      // Close when clicking a close button or backdrop
      delegate(document, "click", SELECTORS.modalCloseBtn, (e, btn) => {
        e.preventDefault();
        const modal = btn.closest(SELECTORS.modal);
        closeModal(modal);
      });

      delegate(document, "click", SELECTORS.modal, (e, modal) => {
        // Close if clicked on backdrop area
        if (e.target === modal) closeModal(modal);
      });

      // Escape to close topmost open modal
      on(document, "keydown", (e) => {
        if (e.key === "Escape") {
          const open = qsa(SELECTORS.modal).find((m) => m.getAttribute("aria-hidden") === "false");
          if (open) closeModal(open);
        }
      });
    };

    // ------- Public API -------
    const init = () => {
      initModals();
    };

    return {
      init,
      // Expose utilities to other modules (no global namespace pollution)
      utils: { qs, qsa, on, delegate, debounce, throttle, uuid, serializeForm, jsonFetch, getCSRFToken },
      // Globally accessible alert function as requested
      showAlert
    };
  })();

  // Make showAlert globally reachable via window.App.showAlert
  window.App = window.App || {};
  window.App.showAlert = SharedComponents.showAlert;

  // ----------------------------------------------------------
  // Playground (playground.html)
  // ----------------------------------------------------------
  const Playground = (function (Shared) {
    const { qs, qsa, on, delegate, jsonFetch } = Shared.utils;

    // Root container check to decide initialization
    const ROOT_SELECTOR = "#playground-container";

    // Expected DOM structure (defensive checks guard if absent)
    const SELECTORS = {
      form: "#playground-form",
      inputText: "#playground-input",
      modelSelect: "#model-select",
      fileInput: "#playground-file",
      chatHistory: "#chat-history",
      submitBtn: "#playground-submit",
      clearBtn: "#playground-clear",
      output: "#playground-output"
    };

    let root = null;
    let abortController = null;

    const appendMessage = (role, content) => {
      const list = qs(SELECTORS.chatHistory, root);
      if (!list) return;

      const item = document.createElement("div");
      item.className = `chat-item chat-item--${role}`;
      item.style.padding = "0.5rem 0";
      item.innerHTML = `
        <div class="chat-role" style="font-weight:600; margin-bottom: .25rem;">${role === "user" ? "You" : "Assistant"}</div>
        <div class="chat-content" style="white-space: pre-wrap;">${escapeHTML(content)}</div>
      `;
      list.appendChild(item);
      // Scroll to bottom
      list.scrollTop = list.scrollHeight;
    };

    const escapeHTML = (str) => {
      const div = document.createElement("div");
      div.textContent = String(str || "");
      return div.innerHTML;
    };

    const setBusy = (busy) => {
      const btn = qs(SELECTORS.submitBtn, root);
      if (btn) {
        btn.disabled = !!busy;
        btn.textContent = busy ? "Sending..." : (btn.getAttribute("data-label") || "Send");
      }
    };

    const clearChat = () => {
      const list = qs(SELECTORS.chatHistory, root);
      if (list) list.innerHTML = "";
      const out = qs(SELECTORS.output, root);
      if (out) out.textContent = "";
      Shared.showAlert("info", "Playground cleared.", { timeout: 2500 });
    };

    const handleSubmit = async (e) => {
      e.preventDefault();
      const form = e.currentTarget;
      const textInput = qs(SELECTORS.inputText, root);
      const modelSelect = qs(SELECTORS.modelSelect, root);
      if (!textInput || !textInput.value.trim()) {
        Shared.showAlert("warning", "Please enter a prompt.", { timeout: 3500 });
        return;
      }

      appendMessage("user", textInput.value);

      // Build payload from form; prefer form action or fallback route
      const endpoint = form.getAttribute("action") || "/playground_chat";
      const method = (form.getAttribute("method") || "POST").toUpperCase();

      // If files present, use FormData (keeps it flexible if backend expects it)
      const fd = new FormData(form);
      fd.set("message", textInput.value);
      if (modelSelect && modelSelect.value) fd.set("model", modelSelect.value);

      // Abort any in-flight request
      if (abortController) abortController.abort();
      abortController = new AbortController();

      setBusy(true);
      try {
        const res = await Shared.utils.jsonFetch(endpoint, { method, data: fd, signal: abortController.signal });
        // Expect { reply: "...", ... } from backend. Be defensive:
        const reply = (res && (res.reply || res.response || res.output)) || "[No response payload]";
        appendMessage("assistant", reply);

        const out = qs(SELECTORS.output, root);
        if (out) out.textContent = reply;

      } catch (err) {
        console.error(err);
        Shared.showAlert("error", err.message || "Playground request failed.");
      } finally {
        setBusy(false);
        // Keep input for context or clear it; here we clear for new prompt
        if (textInput) textInput.value = "";
      }
    };

    const wireEvents = () => {
      const form = qs(SELECTORS.form, root);
      if (form) on(form, "submit", handleSubmit);

      const clearBtn = qs(SELECTORS.clearBtn, root);
      if (clearBtn) on(clearBtn, "click", (e) => {
        e.preventDefault();
        clearChat();
      });
    };

    const init = () => {
      root = qs(ROOT_SELECTOR);
      if (!root) return; // Not on this page

      // Optional: stash original button label
      const submit = qs(SELECTORS.submitBtn, root);
      if (submit && !submit.getAttribute("data-label")) {
        submit.setAttribute("data-label", submit.textContent || "Send");
      }

      wireEvents();
    };

    return { init };
  })(SharedComponents);

  // ----------------------------------------------------------
  // Humanizer (humanizer form page)
  // ----------------------------------------------------------
  const Humanizer = (function (Shared) {
    const { qs, on } = Shared.utils;

    const ROOT_SELECTOR = "#humanizer-container";

    const SELECTORS = {
      form: "#humanizer-form",
      inputText: "#humanizer-input",
      fileInput: "#humanizer-file",
      submitBtn: "#humanizer-submit",
      preview: "#humanizer-preview",
      result: "#humanizer-result"
    };

    let root = null;

    const setBusy = (busy) => {
      const btn = qs(SELECTORS.submitBtn, root);
      if (btn) {
        btn.disabled = !!busy;
        btn.textContent = busy ? "Processing..." : (btn.getAttribute("data-label") || "Humanize");
      }
    };

    const handleFilePreview = (e) => {
      const input = e.currentTarget;
      const preview = qs(SELECTORS.preview, root);
      if (!preview) return;

      const files = input.files || [];
      if (!files.length) {
        preview.textContent = "No file selected.";
        return;
      }
      // Preview just the filename(s) and size(s)
      const lines = Array.from(files).map(f => `${f.name} (${Math.round(f.size / 1024)} KB)`);
      preview.textContent = lines.join("\n");
    };

    const handleSubmit = async (e) => {
      e.preventDefault();
      const form = e.currentTarget;

      const textInput = qs(SELECTORS.inputText, root);
      const fileInput = qs(SELECTORS.fileInput, root);

      if ((!textInput || !textInput.value.trim()) && (!fileInput || !(fileInput.files || []).length)) {
        Shared.showAlert("warning", "Provide text or upload a file to humanize.");
        return;
      }

      const endpoint = form.getAttribute("action") || "/humanize";
      const method = (form.getAttribute("method") || "POST").toUpperCase();

      const fd = new FormData(form);
      if (textInput) fd.set("text", textInput.value);

      setBusy(true);
      try {
        const res = await Shared.utils.jsonFetch(endpoint, { method, data: fd });
        // Expect { task_id, result, ... } depending on backend
        const resultBox = qs(SELECTORS.result, root);
        if (res && res.result && resultBox) {
          resultBox.textContent = res.result;
          Shared.showAlert("success", "Humanization complete.");
        } else if (res && res.task_id) {
          // If async task, redirect or notify
          Shared.showAlert("info", "Your request was queued. Opening task view...");
          // Defer a bit in case UI needs to settle
          setTimeout(() => {
            window.location.href = `/task/${encodeURIComponent(res.task_id)}`;
          }, 500);
        } else {
          Shared.showAlert("info", "Submitted. You'll see results shortly.");
        }
      } catch (err) {
        console.error(err);
        Shared.showAlert("error", err.message || "Humanization failed.");
      } finally {
        setBusy(false);
      }
    };

    const wireEvents = () => {
      const form = qs(SELECTORS.form, root);
      if (form) on(form, "submit", handleSubmit);

      const fileInput = qs(SELECTORS.fileInput, root);
      if (fileInput) on(fileInput, "change", handleFilePreview);
    };

    const init = () => {
      root = qs(ROOT_SELECTOR);
      if (!root) return;

      const submit = qs(SELECTORS.submitBtn, root);
      if (submit && !submit.getAttribute("data-label")) {
        submit.setAttribute("data-label", submit.textContent || "Humanize");
      }

      wireEvents();
    };

    return { init };
  })(SharedComponents);

  // ----------------------------------------------------------
  // TaskView (view_task.html)
  // ----------------------------------------------------------
  const TaskView = (function (Shared) {
    const { qs, on, jsonFetch } = Shared.utils;

    const ROOT_SELECTOR = "#task-view-container";

    const SELECTORS = {
      container: ROOT_SELECTOR,
      status: "#task-status",
      result: "#task-result",
      error: "#task-error",
      copyBtn: "#copy-result",
      cancelBtn: "#cancel-task",
      // Where to retrieve the task id (use whichever exists)
      taskIdMeta: 'meta[name="task-id"]',
      taskIdInput: 'input[name="task_id"]',
      taskIdDataAttr: ROOT_SELECTOR // expects data-task-id on container
    };

    let root = null;
    let polling = false;
    let pollTimer = null;

    const getTaskId = () => {
      // Priority 1: data-task-id on container
      if (root && root.dataset && root.dataset.taskId) return root.dataset.taskId;
      // Priority 2: meta tag
      const meta = document.querySelector(SELECTORS.taskIdMeta);
      if (meta && meta.content) return meta.content;
      // Priority 3: hidden input
      const input = document.querySelector(SELECTORS.taskIdInput);
      if (input && input.value) return input.value;
      return null;
    };

    const updateUI = ({ status, result, error }) => {
      const statusEl = qs(SELECTORS.status, root);
      const resultEl = qs(SELECTORS.result, root);
      const errorEl = qs(SELECTORS.error, root);

      if (statusEl) statusEl.textContent = status || "unknown";

      if (resultEl) {
        resultEl.textContent = result || "";
        resultEl.style.display = result ? "block" : "none";
      }

      if (errorEl) {
        errorEl.textContent = error || "";
        errorEl.style.display = error ? "block" : "none";
      }
    };

    const pollStatus = async () => {
      if (polling) return;
      polling = true;

      const taskId = getTaskId();
      if (!taskId) {
        Shared.showAlert("error", "No task id found on this page.");
        return;
      }

      const endpoint = `/task/${encodeURIComponent(taskId)}/status`;

      try {
        const data = await jsonFetch(endpoint, { method: "GET" });
        // Expected shape: { status, result?, error? }
        updateUI(data || {});
        const status = (data && data.status) || "unknown";

        if (["completed", "failed", "revoked", "canceled"].includes(status)) {
          clearInterval(pollTimer);
          pollTimer = null;
          Shared.showAlert(
            status === "completed" ? "success" :
            status === "failed" ? "error" : "warning",
            `Task ${status}.`
          );
        }
      } catch (err) {
        console.error(err);
        Shared.showAlert("error", err.message || "Failed to poll task status.");
        // Backoff: pause polling for one cycle
      } finally {
        polling = false;
      }
    };

    const copyResultToClipboard = async () => {
      const resultEl = qs(SELECTORS.result, root);
      if (!resultEl || !resultEl.textContent) {
        Shared.showAlert("warning", "No result to copy.");
        return;
      }
      try {
        await navigator.clipboard.writeText(resultEl.textContent);
        Shared.showAlert("success", "Result copied to clipboard.");
      } catch (_) {
        // Fallback
        const area = document.createElement("textarea");
        area.value = resultEl.textContent;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
        Shared.showAlert("success", "Result copied to clipboard.");
      }
    };

    const cancelTask = async () => {
      const taskId = getTaskId();
      if (!taskId) return;
      const endpoint = `/task/${encodeURIComponent(taskId)}/cancel`;
      try {
        await jsonFetch(endpoint, { method: "POST" });
        Shared.showAlert("info", "Cancellation requested.");
        // Force a status refresh soon
        setTimeout(pollStatus, 500);
      } catch (err) {
        console.error(err);
        Shared.showAlert("error", err.message || "Failed to cancel task.");
      }
    };

    const wireEvents = () => {
      const copyBtn = qs(SELECTORS.copyBtn, root);
      if (copyBtn) on(copyBtn, "click", copyResultToClipboard);

      const cancelBtn = qs(SELECTORS.cancelBtn, root);
      if (cancelBtn) on(cancelBtn, "click", cancelTask);
    };

    const init = () => {
      root = qs(ROOT_SELECTOR);
      if (!root) return;

      wireEvents();

      // Start polling every 2 seconds
      pollTimer = setInterval(pollStatus, 2000);
      // Kick off immediately once
      pollStatus();
    };

    return { init };
  })(SharedComponents);

  // ----------------------------------------------------------
  // Bootstrapping (runs once on DOMContentLoaded)
  // ----------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    // Always initialize shared site-wide pieces
    SharedComponents.init();

    // Conditionally initialize page modules
    Playground.init();
    Humanizer.init();
    TaskView.init();
  });
})();
