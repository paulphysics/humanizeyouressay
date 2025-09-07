/**
 * static/js/script.js
 *
 * Refactored into modules using a Revealing Module Pattern.
 * - SharedComponents: site-wide helpers (alerts, modal top-up actions, utilities)
 * - Playground: playground.html logic (chat, files, conversations, model selector)
 * - Humanizer: humanizer form logic and polling
 * - TaskView: single task view logic (copy output)
 *
 * This is a drop-in replacement for your original script. All original IDs,
 * endpoints and behavior were preserved. Each module initializes only if its
 * root DOM element is present.
 *
 * Notes:
 * - This file intentionally mirrors the original functions / endpoints so
 * behavior remains unchanged.
 * - A global `window.App.showAlert` is exposed for other code to call.
 */

(function () {
  "use strict";

  // -------------------------
  // SharedComponents module
  // -------------------------
  const SharedComponents = (function () {
    const ALERT_DEFAULT_DURATION = 5000;

    // Utility helpers
    const qs = (sel, root = document) => (root || document).querySelector(sel);
    const qsa = (sel, root = document) => Array.from((root || document).querySelectorAll(sel));
    const on = (el, evt, handler, opts) => { if (el) el.addEventListener(evt, handler, opts || false); };
    const ready = (fn) => { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); };

    // Auto Top-Up Logic
    const TOP_UP_REGEX = /(insufficient funds|please top up|insufficient balance)/i;
    let autoClickTimer = null;

    function isModalOpen() {
      const topUpModal = qs("#topUpModal");
      return !!(topUpModal && (topUpModal.classList.contains("show") || topUpModal.getAttribute("aria-hidden") === "false"));
    }

    function clearAutoClickTimer() {
      if (autoClickTimer) {
        clearTimeout(autoClickTimer);
        autoClickTimer = null;
      }
    }

    function scheduleTopUpOpen() {
      if (isModalOpen()) return;
      clearAutoClickTimer();
      autoClickTimer = setTimeout(() => {
        try {
          if (!isModalOpen()) {
            const btn = qs("#topUpBtn");
            if (btn && !btn.disabled) {
              console.log("[AutoTopUp] Opening Top Up modal after 2.5s...");
              btn.click();
            }
          }
        } finally {
          autoClickTimer = null;
        }
      }, 2500);
    }
    
    // Central showAlert - all pages use same container id's: #js-alert-container, #js-alert-message
    function showAlert(message, type = "info", duration = ALERT_DEFAULT_DURATION) {
      try {
        // PATCH: If alert message matches, schedule modal open
        if (TOP_UP_REGEX.test(message)) {
          console.log("[AutoTopUp] Detected wallet top-up alert, scheduling modal open.");
          scheduleTopUpOpen();
        }

        let jsAlertContainer = qs("#js-alert-container");
        
        // ✅ If alert container doesn't exist in the DOM, create it.
        // This makes the alert system work on any page, even if the layout is missing the element.
        if (!jsAlertContainer) {
            jsAlertContainer = document.createElement("div");
            jsAlertContainer.id = "js-alert-container";
            const messageSpan = document.createElement("span");
            messageSpan.id = "js-alert-message";
            jsAlertContainer.appendChild(messageSpan);
            document.body.appendChild(jsAlertContainer);
        }

        const jsAlertMessage = qs("#js-alert-message", jsAlertContainer);
        const emojiMap = { success: "✅", danger: "❌", info: "ℹ️" };

        if (jsAlertMessage) {
            jsAlertMessage.textContent = `${emojiMap[type] || "ℹ️"} ${message}`;
        }
        
        jsAlertContainer.className = "js-alert-container flash-message rounded-lg shadow-md";
        jsAlertContainer.classList.add(`flash-${type}`, "show");
        
        // Clear any previous timeout to ensure the new alert's duration is respected
        if (jsAlertContainer.dataset.alertTimeout) {
            clearTimeout(parseInt(jsAlertContainer.dataset.alertTimeout, 10));
        }

        if (duration > 0) {
          const timeoutId = setTimeout(() => {
            jsAlertContainer?.classList.remove("show");
          }, duration);
          jsAlertContainer.dataset.alertTimeout = timeoutId;
        }
      } catch (err) {
        console.error("showAlert error", err);
      }
    }

    // Top-up / wallet behavior extracted from original initializeSharedComponents
    function initTopUpAndNav() {
      const topUpModal = qs("#topUpModal");
      const topUpBtn = qs("#topUpBtn");
      const mobileTopUpBtn = qs("#mobileTopUpBtn");
      const closeTopUpModalBtn = qs("#closeTopUpModalBtn");
      const submitTopUpBtn = qs("#submitTopUpBtn");
      const walletToggle = qs("#wallet-toggle");
      const hamburgerBtn = qs("#menu-btn");
      const mobileMenu = qs("#mobile-menu");

      const openTopUpModal = () => topUpModal && topUpModal.classList.remove("hidden");
      const closeTopUpModal = () => topUpModal && topUpModal.classList.add("hidden");

      // close by default
      closeTopUpModal();

      if (topUpBtn) {
        on(topUpBtn, "click", openTopUpModal);
        on(topUpBtn, "click", clearAutoClickTimer);
      }
      if (mobileTopUpBtn) on(mobileTopUpBtn, "click", openTopUpModal);
      if (closeTopUpModalBtn) on(closeTopUpModalBtn, "click", closeTopUpModal);

      if (topUpModal) {
        on(topUpModal, "click", (e) => {
          if (e.target === topUpModal) closeTopUpModal();
        });
      }

      async function submitTopUp() {
        if (!submitTopUpBtn) return;
        const originalButtonText = submitTopUpBtn.innerHTML;
        submitTopUpBtn.innerHTML = `<span class="spinner !w-5 !h-5"></span> Processing...`;
        submitTopUpBtn.disabled = true;

        try {
          const amountEl = qs("#top_up_amount");
          const phoneEl = qs("#phone_number_top_up");
          const amount = amountEl ? amountEl.value : null;
          const phone = phoneEl ? phoneEl.value.trim() : "";
          if (!amount || amount <= 0) throw new Error("Please enter a valid amount.");
          if (!/^(0|\+254)7[0-9]{8}$/.test(phone)) throw new Error("Invalid phone number.");

          // ✅ FIX: Show feedback BEFORE closing modal and making the request
          showAlert("Sending top-up request...", "info");
          closeTopUpModal();

          const response = await fetch("/wallet/topup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount: parseFloat(amount), phone_number: phone })
          });

          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "An error occurred.");
          
          // ✅ FIX: Provide clearer success feedback
          showAlert("STK push sent successfully! Please check your phone to complete the payment.", "success");

        } catch (err) {
          showAlert(err.message || "Top up failed", "danger");
        } finally {
          submitTopUpBtn.innerHTML = originalButtonText;
          submitTopUpBtn.disabled = false;
        }
      }

      function toggleWalletBalance() {
        const walletIcon = qs("#wallet-icon");
        const walletBalanceAmount = qs("#wallet-balance-amount");
        if (!walletToggle || !walletIcon || !walletBalanceAmount) return;
        const isHidden = walletToggle.classList.toggle("balance-hidden");
        walletIcon.classList.toggle("text-gray-500", !isHidden);
        walletIcon.classList.toggle("text-green-600", isHidden);
        walletBalanceAmount.classList.toggle("text-green-600", !isHidden);
        walletBalanceAmount.classList.toggle("text-gray-500", isHidden);
        walletBalanceAmount.textContent = isHidden ? "KSh ***" : `KSh ${walletBalanceAmount.dataset.balance}`;
      }

      function toggleMobileMenu() {
        if (mobileMenu) mobileMenu.classList.toggle("hidden");
      }

      if (submitTopUpBtn) on(submitTopUpBtn, "click", (e) => {
        e.preventDefault();
        submitTopUp();
      });
      if (walletToggle) on(walletToggle, "click", toggleWalletBalance);
      if (hamburgerBtn) on(hamburgerBtn, "click", toggleMobileMenu);
    }

    // Small utility for converting markdown to html (uses marked if present)
    function markdownToHtml(text) {
      if (typeof marked !== "undefined") {
        try { return marked.parse(text); } catch (e) { /* fallback below */ }
      }
      // fallback simple renderer (keeps original behavior)
      return String(text || "")
        .replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>")
        .replace(/\n/g, "<br>");
    }

    // syntax highlight fallback using hljs if available
    function highlightCodeBlocks() {
      if (typeof hljs === "undefined") return;
      document.querySelectorAll("#chat-log pre").forEach((preElement) => {
        const block = preElement.querySelector("code");
        if (!block) return;
        if (!block.hasAttribute("data-highlighted")) {
          hljs.highlightElement(block);
          block.setAttribute("data-highlighted", "true");
        }
        if (!preElement.querySelector(".code-copy-btn")) {
          const copyBtn = document.createElement("button");
          copyBtn.className = "code-copy-btn";
          copyBtn.title = "Copy code";
          const clipboardIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>`;
          const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>`;
          copyBtn.innerHTML = clipboardIcon;
          copyBtn.addEventListener("click", () => {
            navigator.clipboard.writeText(block.innerText).then(() => {
              copyBtn.innerHTML = checkIcon;
              setTimeout(() => { copyBtn.innerHTML = clipboardIcon; }, 2000);
            }).catch(err => console.error("Failed to copy text: ", err));
          });
          preElement.prepend(copyBtn);
        }
      });
    }

    function applyCssFixes() {
      const style = document.createElement('style');
      style.textContent = `
            #js-alert-container.show {
                display: block !important;
            }
        `;
      document.head.appendChild(style);
    }
    
    // Monitors chat messages for top-up keywords
    function monitorChatForTopUpMessages() {
      const chatContainer = qs("#chat-log");
      if (chatContainer) {
        const chatObserver = new MutationObserver((mutations) => {
          for (const m of mutations) {
            for (const node of m.addedNodes) {
              if (node.nodeType === Node.ELEMENT_NODE) {
                const text = (node.textContent || "").trim();
                if (TOP_UP_REGEX.test(text)) {
                  console.log("[AutoTopUp] Detected wallet top-up message in chat.");
                  scheduleTopUpOpen();
                  return;
                }
              }
            }
          }
        });
        chatObserver.observe(chatContainer, { childList: true, subtree: true });
      }
    }

    // Public API
    return {
      init: function () {
        applyCssFixes();
        initTopUpAndNav();
        monitorChatForTopUpMessages();
      },
      showAlert,
      utils: { qs, qsa, on, ready, markdownToHtml, highlightCodeBlocks }
    };
  })();

  // Expose showAlert globally
  window.App = window.App || {};
  window.App.showAlert = SharedComponents.showAlert;

  // -------------------------
  // Playground module
  // -------------------------
  const Playground = (function (Shared) {
    const { qs, qsa, on, markdownToHtml, highlightCodeBlocks } = Shared.utils;
    const ROOT_ID = "playground-container";
    const ROOT = qs(`#${ROOT_ID}`);
    if (!ROOT) {
      return { init: function () { /* not on page */ } };
    }

    // State
    let alertTimeout = null;
    const ALERT_DURATION = 5000;
    let isFetchingHistory = false;
    let isChatActive = false;
    let attachedFiles = [];
    const MAX_TOTAL_SIZE = 10 * 1024 * 1024; // 10 MB
    let pollingInterval = null;

    // DOM elements (same as original)
    const DOM = {
      modelSelectionBar: qs("#model-selection-bar"),
      uploadBtn: qs("#upload-btn"),
      fileInput: qs("#file-input"),
      attachmentPreviewContainer: qs("#attachment-preview-container"),
      chatLog: qs("#chat-log"),
      promptInput: qs("#prompt-input"),
      generateBtn: qs("#generate-btn"),
      newChatBtn: qs("#new-chat-btn"),
      conversationList: qs("#conversation-list"),
      modelSelector: qs("#model-selector"),
      modelSelectorBtn: qs("#model-selector-btn"),
      modelSelectorOptions: qs("#model-selector-options"),
      modelSelectorLabel: qs("#model-selector-label"),
      jsAlertContainer: qs("#js-alert-container"),
      jsAlertMessage: qs("#js-alert-message"),
      historySidebar: qs("#history-sidebar"),
      showHistoryBtn: qs("#show-history-btn"),
      searchHistoryInput: qs("#search-history-input"),
      paginationContainer: qs("#history-pagination-container"),
      historyLoadingSpinner: qs("#history-loading-spinner"),
      playgroundWelcomeHeader: qs("#playground-welcome-header"),
      playgroundContainer: qs("#playground-container"),
      dropZone: qs("#drop-zone"),
      conversationIdInput: qs("#conversation-id-storage"),
      clearHistoryBtn: qs("#clear-history-btn"),
      wordCountDisplay: qs("#word-count-display")
    };

    // ensure overlay element exists (original code appended it)
    let sidebarOverlay = document.querySelector(".sidebar-overlay");
    if (!sidebarOverlay) {
      sidebarOverlay = document.createElement("div");
      sidebarOverlay.classList.add("sidebar-overlay");
      document.body.appendChild(sidebarOverlay);
    }

    function localShowAlert(message, type = "info") {
      // Use shared showAlert for consistency; provide module-specific timeout
      Shared.showAlert(message, type, ALERT_DURATION);
    }

    function showProcessing(isProcessing) {
      if (DOM.generateBtn) DOM.generateBtn.disabled = !!isProcessing;
    }

    function addMessageActions(messageContainer, messageText) {
      const actionsContainer = document.createElement("div");
      actionsContainer.className = "flex items-center gap-x-2 mt-2 ml-2";
      const copyBtn = document.createElement("button");
      copyBtn.className = "p-1 rounded-md bg-gray-100 text-gray-600 hover:bg-indigo-200 hover:text-indigo-700";
      copyBtn.title = "Copy";
      const clipboardIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>`;
      const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>`;
      copyBtn.innerHTML = clipboardIcon;
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(messageText).then(() => {
          copyBtn.innerHTML = checkIcon;
          setTimeout(() => copyBtn.innerHTML = clipboardIcon, 2000);
        }).catch(err => console.error("Copy failed", err));
      };

      const humanizeBtn = document.createElement("button");
      humanizeBtn.className = "p-1 rounded-md bg-gray-100 text-gray-600 hover:bg-indigo-200 hover:text-indigo-700";
      humanizeBtn.title = "Humanize";
      humanizeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2Z"/></svg>`;
      humanizeBtn.onclick = () => {
        try {
          localStorage.setItem("textToHumanize", messageText);
          window.open("/humanizer", "_blank");
        } catch (err) {
          console.error("Failed to open humanizer", err);
        }
      };

      actionsContainer.append(copyBtn, humanizeBtn);
      messageContainer.appendChild(actionsContainer);
    }

    function addMessageToLog(sender, content, addActions = false) {
      if (!DOM.chatLog) return { messageContainer: null, messageBubble: null };
      const isUser = sender === "user";
      const messageContainer = document.createElement("div");
      messageContainer.className = `message-container ${isUser ? "user-message-container" : "bot-message-container"}`;
      const messageBubble = document.createElement("div");
      messageBubble.className = `message-bubble ${isUser ? "user-message" : "bot-message"}`;

      if (isUser) {
        // escape
        messageBubble.innerHTML = String(content || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      } else {
        messageBubble.innerHTML = markdownToHtml(content);
      }
      messageContainer.appendChild(messageBubble);

      if (!isUser && addActions) {
        addMessageActions(messageContainer, content);
      }

      DOM.chatLog.appendChild(messageContainer);
      highlightCodeBlocks();
      DOM.chatLog.scrollTop = DOM.chatLog.scrollHeight;
      return { messageContainer, messageBubble };
    }

    // Global registry of active pollers
    const activePollers = {};
    
    // Poll for async task results (playground)
    function pollForTaskResult(taskId, messageContainer, messageBubble, delay = 1500, attempts = 0) {
      // If this taskId was aborted, stop immediately
      if (activePollers[taskId]?.aborted) return;
    
      if (attempts > 60) {
        messageBubble.innerHTML = `<p class="text-red-500">Error: The request timed out. Please try again.</p>`;
        showProcessing(false);
        delete activePollers[taskId];
        return;
      }
    
      const timerId = setTimeout(async () => {
        try {
          const response = await fetch(`/get_playground_task_status/${taskId}`);
          if (!response.ok) {
            if (response.status !== 404 || attempts > 5) {
              throw new Error("Failed to get task status from server.");
            }
            return pollForTaskResult(taskId, messageContainer, messageBubble, delay, attempts + 1);
          }
    
          const data = await response.json();
          if (data.status === "complete") {
            messageBubble.innerHTML = markdownToHtml(data.response);
            showProcessing(false);
    
            addMessageActions(messageContainer, data.response);
    
            if (data.conversation_title && DOM.conversationList) {
              const convItem = DOM.conversationList.querySelector(`[data-conv-id="${data.conversation_id}"]`);
              if (convItem) {
                convItem.querySelector("span").textContent = data.conversation_title;
              }
            }
            highlightCodeBlocks();
    
            delete activePollers[taskId]; // ✅ stop tracking
            return;
          }
    
          if (data.status === "failed") {
            messageBubble.innerHTML = `<p class="text-red-500">Error: ${data.error || "Processing failed."}</p>`;
            showProcessing(false);
            delete activePollers[taskId];
            return;
          }
    
          // Still processing → backoff and retry
          const nextDelay = Math.min(delay * 1.5, 10000);
          pollForTaskResult(taskId, messageContainer, messageBubble, nextDelay, attempts + 1);
    
        } catch (err) {
          messageBubble.innerHTML = `<p class="text-red-500">Error: ${err.message}</p>`;
          showProcessing(false);
          delete activePollers[taskId];
        }
      }, delay);
    
      // Register or update this poller
      activePollers[taskId] = { timerId, aborted: false };
    }
    
    // Utility: abort a poller manually
    function abortPoller(taskId) {
      const poller = activePollers[taskId];
      if (poller) {
        clearTimeout(poller.timerId);
        poller.aborted = true;
        delete activePollers[taskId];
      }
    }
    
    // Utility: abort all pollers (e.g. on page navigation)
    function abortAllPollers() {
      for (const taskId in activePollers) {
        abortPoller(taskId);
      }
    }


    // File handling, extracting text for docs, or encoding images
    async function handleFiles(files) {
      if (!files || files.length === 0) return;
      // show spinner
      showUploadSpinner();
      const fileList = Array.from(files);
      let totalSize = attachedFiles.reduce((acc, f) => acc + (f.size || 0), 0);
      for (const file of fileList) {
        totalSize += file.size || 0;
        if (totalSize > MAX_TOTAL_SIZE) {
          localShowAlert("Total file size cannot exceed 10MB.", "danger");
          hideUploadSpinner();
          return;
        }
      }
      localShowAlert("Processing attachments...", "info");
      for (const file of fileList) {
        const allowedImageTypes = ["image/jpeg", "image/png", "image/gif", "image/webp"];
        const allowedDocTypes = [
          "application/pdf",
          "text/plain",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "application/zip",
          "application/x-zip-compressed"
        ];
        const allowedDocExtensions = ["pdf", "docx", "txt", "zip"];
        const fileExt = (file.name || "").split(".").pop().toLowerCase();
        const fileData = { name: file.name, type: file.type, size: file.size, data: null };

        if (allowedImageTypes.includes(file.type)) {
          // read as data URL
          fileData.data = await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.readAsDataURL(file);
          });
          attachedFiles.push(fileData);
        } else if (allowedDocTypes.includes(file.type) || allowedDocExtensions.includes(fileExt)) {
          const formData = new FormData();
          formData.append("file", file);
          try {
            const response = await fetch("/extract_text_from_file", { method: "POST", body: formData });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Failed to extract file text.");
            fileData.data = data.text;
            attachedFiles.push(fileData);
          } catch (err) {
            localShowAlert(`Failed to process ${file.name}: ${err.message}`, "danger");
          }
        } else {
          localShowAlert(`Unsupported file type: ${file.name}`, "danger");
        }
      }
      renderAttachedFiles();
      hideUploadSpinner();
    }

    function showUploadSpinner() {
      if (!DOM.dropZone) return;
      const spinner = document.createElement("div");
      spinner.className = "spinner";
      spinner.style.position = "absolute";
      spinner.style.top = "50%";
      spinner.style.left = "50%";
      spinner.style.transform = "translate(-50%, -50%)";
      DOM.dropZone.appendChild(spinner);
      if (DOM.promptInput) DOM.promptInput.disabled = true;
    }

    function hideUploadSpinner() {
      if (!DOM.dropZone) return;
      const spinner = DOM.dropZone.querySelector(".spinner");
      if (spinner) spinner.remove();
      if (DOM.promptInput) DOM.promptInput.disabled = false;
    }

    function renderAttachedFiles() {
      if (!DOM.attachmentPreviewContainer) return;
      DOM.attachmentPreviewContainer.innerHTML = "";
      if (attachedFiles.length === 0) return;
      attachedFiles.forEach((file, index) => {
        const fileElement = document.createElement("div");
        fileElement.className = "bg-gray-100 p-2 rounded-lg flex items-center justify-between text-sm";
        let previewContent = `<span class="text-gray-700 truncate">${file.name}</span>`;
        if (file.type && file.type.startsWith("image/")) {
          previewContent = `<img src="${file.data}" class="w-8 h-8 rounded-md object-cover mr-2">` + previewContent;
        }
        fileElement.innerHTML = `<div class="flex items-center gap-x-2">${previewContent}</div><button data-index="${index}" class="remove-attachment-btn p-1 rounded-full text-gray-500 hover:bg-gray-300"><svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg></button>`;
        DOM.attachmentPreviewContainer.appendChild(fileElement);
      });
      qsa(".remove-attachment-btn", DOM.attachmentPreviewContainer).forEach(button => {
        on(button, "click", (e) => {
          const idx = parseInt(button.dataset.index, 10);
          if (!isNaN(idx)) {
            attachedFiles.splice(idx, 1);
            renderAttachedFiles();
          }
        });
      });
    }

    // handle generate (send) button logic
    async function handleGenerate() {
      try {
        if (!DOM.promptInput) return;
        const prompt = DOM.promptInput.value.trim();
        if (!prompt && attachedFiles.length === 0) {
          return localShowAlert("Please enter a prompt or attach a file.", "info");
        }

        const currentConversationId = DOM.conversationIdInput ? DOM.conversationIdInput.value : "";

        if (!currentConversationId && DOM.modelSelectionBar) {
          DOM.modelSelectionBar.style.display = "none";
        }
        if (!isChatActive) {
          isChatActive = true;
          if (DOM.playgroundWelcomeHeader) DOM.playgroundWelcomeHeader.classList.add("chat-active");
          if (DOM.playgroundContainer) DOM.playgroundContainer.classList.add("chat-active");
        }

        let userInputPayload = [{ type: "input_text", text: prompt }];
        let displayMessage = prompt;
        attachedFiles.forEach(file => {
          if (file.type && file.type.startsWith("image/")) {
            userInputPayload.push({ type: "input_image", image_url: { url: file.data } });
          } else {
            userInputPayload.push({ type: "input_text", text: `\n\n--- Document: ${file.name} ---\n${file.data}` });
          }
        });
        if (attachedFiles.length > 0) {
          displayMessage = prompt ? `${prompt} [${attachedFiles.length} file(s) attached]` : `[${attachedFiles.length} file(s) attached]`;
        }
        addMessageToLog("user", displayMessage);

        if (DOM.promptInput) {
          DOM.promptInput.value = "";
          DOM.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
        attachedFiles = [];
        renderAttachedFiles();

        showProcessing(true);
        const thinkingPlaceholder = `<div class="flex items-center gap-x-2"><div class="spinner !w-5 !h-5"></div><span>Thinking...</span></div>`;
        const { messageContainer, messageBubble } = addMessageToLog("bot", thinkingPlaceholder, false);

        if (!DOM.modelSelector) throw new Error("Model selector not found.");
        const selectedModel = DOM.modelSelector.dataset.selectedValue;
        if (!selectedModel) throw new Error("Please select a model.");

        const response = await fetch("/playground_chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: selectedModel,
            input: userInputPayload,
            conversation_id: currentConversationId,
          })
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Failed to start the chat task.");

        if (data.conversation_id) {
          const isNewConversation = !(DOM.conversationIdInput && DOM.conversationIdInput.value);
          if (DOM.conversationIdInput) DOM.conversationIdInput.value = data.conversation_id;
          if (isNewConversation) {
            await fetchConversations();
          }
        }

        if (data.status === "processing_started" && data.task_id) {
          pollForTaskResult(data.task_id, messageContainer, messageBubble);
        } else {
          throw new Error("Invalid response from server when starting task.");
        }
      } catch (err) {
        // put error message into the placeholder bubble if present
        try {
          const lastBubble = DOM.chatLog ? DOM.chatLog.lastElementChild : null;
          if (lastBubble && lastBubble.querySelector(".bot-message")) {
            lastBubble.querySelector(".bot-message").innerHTML = `<p class="text-red-500">Error: ${err.message}</p>`;
          }
        } catch (e) { /* ignore */ }
        showProcessing(false);
      }
    }

    // load conversation from server and render messages
    async function loadConversation(convId) {
      try {
        const response = await fetch(`/conversation/${convId}`);
        if (!response.ok) throw new Error("Failed to load conversation.");
        const data = await response.json();
        const messages = data.messages || [];
        const model_key = data.model_key;

        if (DOM.chatLog) DOM.chatLog.innerHTML = "";
        if (DOM.conversationIdInput) DOM.conversationIdInput.value = convId;

        if (DOM.modelSelector && model_key) {
          DOM.modelSelector.dataset.selectedValue = model_key;
          const modelOption = DOM.modelSelectorOptions ? DOM.modelSelectorOptions.querySelector(`[data-value="${model_key}"]`) : null;
          if (modelOption && DOM.modelSelectorLabel) {
            DOM.modelSelectorLabel.textContent = modelOption.querySelector("span").textContent;
            DOM.modelSelectorOptions.querySelectorAll(".model-option").forEach(opt => opt.classList.remove("bg-gray-200"));
            modelOption.classList.add("bg-gray-200");
          }
        }
        if (DOM.modelSelectionBar) DOM.modelSelectionBar.style.display = "none";

        messages.forEach(msg => {
          let content = msg.content;
          if (msg.role === "user" && typeof msg.content === "string") {
            try { content = JSON.parse(msg.content); } catch (e) { /* not JSON */ }
          }
          if (msg.role === "user") {
            let displayContent = "";
            if (Array.isArray(content)) {
              const textParts = content.filter(part => part.type === "input_text").map(part => part.text).join(" ");
              const hasAttachments = content.some(part => part.type !== "input_text");
              displayContent = textParts + (hasAttachments ? ` [${content.length - 1} file(s) attached]` : "");
            } else {
              displayContent = content;
            }
            addMessageToLog("user", displayContent);
          } else {
            addMessageToLog("bot", content, true);
          }
        });

        if (DOM.chatLog) DOM.chatLog.scrollTop = DOM.chatLog.scrollHeight;
        if (!isChatActive) {
          isChatActive = true;
          if (DOM.playgroundWelcomeHeader) DOM.playgroundWelcomeHeader.classList.add("chat-active");
          if (DOM.playgroundContainer) DOM.playgroundContainer.classList.add("chat-active");
        }

        qsa("#conversation-list > div").forEach(div => div.classList.toggle("bg-gray-200", div.dataset.convId == convId));
        highlightCodeBlocks();

        if (window.innerWidth < 1024 && DOM.historySidebar && !DOM.historySidebar.classList.contains("mobile-hidden")) {
          toggleHistorySidebar();
        }
      } catch (err) {
        localShowAlert(err.message || "Failed to load conversation.", "danger");
      }
    }

    async function deleteConversation(convId) {
      if (!confirm("Are you sure you want to delete this chat?")) return;
      try {
        const response = await fetch(`/conversation/${convId}`, { method: "DELETE" });
        if (!response.ok) throw new Error("Failed to delete.");
        localShowAlert("Conversation deleted.", "success");
        fetchConversations(DOM.searchHistoryInput ? DOM.searchHistoryInput.value : "", 1);
        if (DOM.conversationIdInput && DOM.conversationIdInput.value === convId) startNewChat();
      } catch (err) {
        localShowAlert(err.message || "Failed to delete conversation", "danger");
      }
    }

    async function clearAllConversations() {
      if (!confirm("Are you sure you want to clear all chat history? This action cannot be undone.")) return;
      try {
        const response = await fetch("/conversations/clear_all", { method: "POST" });
        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.error || "Failed to clear history.");
        }
        localShowAlert("All conversations have been cleared.", "success");
        fetchConversations();
        startNewChat();
      } catch (err) {
        localShowAlert(err.message || "Failed to clear conversations", "danger");
      }
    }

    function renderPagination(totalPages, currentPage) {
      if (!DOM.paginationContainer) return;
      DOM.paginationContainer.innerHTML = "";
      if (totalPages <= 1) return;
      const createButton = (text, page, isDisabled = false, isActive = false) => {
        const button = document.createElement("button");
        button.innerHTML = text;
        button.dataset.page = page;
        button.disabled = isDisabled;
        button.className = `px-2 py-0.5 text-xs rounded-md ${isActive ? "bg-indigo-600 text-white" : "bg-white text-gray-700 hover:bg-gray-100 border"}`;
        return button;
      };
      const wrapper = document.createElement("div");
      wrapper.className = "flex items-center justify-center space-x-0.5";
      wrapper.appendChild(createButton("&laquo;", currentPage - 1, currentPage === 1));
      for (let i = 1; i <= totalPages; i++) {
        if (totalPages > 7 && Math.abs(currentPage - i) > 2 && i !== 1 && i !== totalPages) {
          if (i === 2 || i === totalPages - 1) wrapper.insertAdjacentHTML("beforeend", `<span class="px-2 py-0.5 text-xs">...</span>`);
          continue;
        }
        wrapper.appendChild(createButton(i, i, false, i === currentPage));
      }
      wrapper.appendChild(createButton("&raquo;", currentPage + 1, currentPage === totalPages));
      DOM.paginationContainer.appendChild(wrapper);
    }

    function appendConversations(conversations) {
      if (!DOM.conversationList) return;
      DOM.conversationList.innerHTML = "";
      if (!conversations || conversations.length === 0) {
        DOM.conversationList.innerHTML = `<p class="text-xs text-gray-500 p-2">No past conversations.</p>`;
        return;
      }
      conversations.forEach(conv => {
        const convItem = document.createElement("div");
        convItem.className = "flex justify-between items-center p-2 rounded-md hover:bg-gray-100 cursor-pointer";
        convItem.dataset.convId = conv.id;
        const titleSpan = document.createElement("span");
        titleSpan.className = "text-sm text-gray-700 truncate";
        titleSpan.textContent = conv.title;
        const deleteBtn = document.createElement("button");
        deleteBtn.className = "text-gray-400 hover:text-red-500 p-1";
        deleteBtn.innerHTML = `<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>`;
        convItem.append(titleSpan, deleteBtn);
        titleSpan.onclick = () => loadConversation(conv.id);
        deleteBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(conv.id); };
        DOM.conversationList.appendChild(convItem);
      });
    }

    async function fetchConversations(query = "", page = 1) {
      if (isFetchingHistory) return;
      isFetchingHistory = true;
      if (DOM.historyLoadingSpinner) DOM.historyLoadingSpinner.style.display = "block";
      try {
        const response = await fetch(`/get_conversations?q=${encodeURIComponent(query)}&page=${page}`);
        if (!response.ok) throw new Error("Failed to fetch conversations.");
        const data = await response.json();
        appendConversations(data.conversations);
        renderPagination(data.total_pages, data.current_page);
      } catch (err) {
        localShowAlert(err.message || "Failed to fetch conversations", "danger");
      } finally {
        if (DOM.historyLoadingSpinner) DOM.historyLoadingSpinner.style.display = "none";
        isFetchingHistory = false;
      }
    }

    function startNewChat() {
      clearInterval(pollingInterval);
      pollingInterval = null;
      if (DOM.conversationIdInput) DOM.conversationIdInput.value = "";

      attachedFiles = [];
      renderAttachedFiles();
      if (DOM.chatLog) DOM.chatLog.innerHTML = "";
      if (DOM.promptInput) {
        DOM.promptInput.value = "";
        DOM.promptInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (DOM.modelSelectionBar) DOM.modelSelectionBar.style.display = "block";

      addMessageToLog("bot", "Hello! How can I assist you today? Select a model and ask me anything.", false);

      isChatActive = false;
      if (DOM.playgroundWelcomeHeader) DOM.playgroundWelcomeHeader.classList.remove("chat-active");
      if (DOM.playgroundContainer) DOM.playgroundContainer.classList.remove("chat-active");
      if (window.innerWidth < 1024 && DOM.historySidebar && !DOM.historySidebar.classList.contains("mobile-hidden")) toggleHistorySidebar();
      qsa("#conversation-list > div").forEach(div => div.classList.remove("bg-gray-200"));
    }

    async function setupModelSelector() {
      if (!DOM.modelSelector) { console.warn("Model selector element not found."); return; }
      try {
        const response = await fetch("/api/get-models");
        if (!response.ok) throw new Error("Failed to load models.");
        const models = await response.json();
        if (!models || models.length === 0) {
          localShowAlert("Could not load any AI models. Please contact support.", "danger");
          return;
        }
        if (DOM.modelSelectorOptions) DOM.modelSelectorOptions.innerHTML = "";
        const selectedModel = models.find(m => m.selected) || models[0];
        models.forEach(model => {
          const li = document.createElement("li");
          li.className = "model-option p-2 hover:bg-gray-100 cursor-pointer";
          li.dataset.value = model.value;
          li.innerHTML = `<span class="font-semibold">${model.label}</span>`;
          if (model.selected) li.classList.add("bg-gray-200");
          li.onclick = () => {
            if (DOM.modelSelectorOptions) DOM.modelSelectorOptions.querySelectorAll(".model-option").forEach(opt => opt.classList.remove("bg-gray-200"));
            li.classList.add("bg-gray-200");
            DOM.modelSelector.dataset.selectedValue = model.value;
            if (DOM.modelSelectorLabel) DOM.modelSelectorLabel.textContent = model.label;
            if (DOM.modelSelectorOptions) DOM.modelSelectorOptions.classList.remove("options-visible");
          };
          if (DOM.modelSelectorOptions) DOM.modelSelectorOptions.appendChild(li);
        });
        DOM.modelSelector.dataset.selectedValue = selectedModel.value;
        if (DOM.modelSelectorLabel) DOM.modelSelectorLabel.textContent = selectedModel.label;
        if (DOM.modelSelectorBtn) DOM.modelSelectorBtn.onclick = () => DOM.modelSelectorOptions?.classList.toggle("options-visible");
      } catch (err) {
        localShowAlert(err.message || "Failed to load models", "danger");
      }
    }

    function toggleHistorySidebar() {
      if (DOM.historySidebar && sidebarOverlay) {
        DOM.historySidebar.classList.toggle("mobile-hidden");
        sidebarOverlay.classList.toggle("show");
      }
    }

    // Wire events (preserves original interactions)
    function wireEvents() {
      if (DOM.generateBtn) on(DOM.generateBtn, "click", handleGenerate);
      if (DOM.newChatBtn) on(DOM.newChatBtn, "click", startNewChat);
      if (DOM.showHistoryBtn) on(DOM.showHistoryBtn, "click", toggleHistorySidebar);
      if (DOM.clearHistoryBtn) on(DOM.clearHistoryBtn, "click", clearAllConversations);
      if (sidebarOverlay) on(sidebarOverlay, "click", toggleHistorySidebar);

      if (DOM.searchHistoryInput) {
        let searchTimeout = null;
        on(DOM.searchHistoryInput, "input", (e) => {
          clearTimeout(searchTimeout);
          searchTimeout = setTimeout(() => fetchConversations(e.target.value, 1), 300);
        });
      }

      if (DOM.paginationContainer) {
        on(DOM.paginationContainer, "click", (e) => {
          const button = e.target.closest("button");
          if (button && button.dataset.page && !button.disabled) {
            fetchConversations(DOM.searchHistoryInput ? DOM.searchHistoryInput.value : "", parseInt(button.dataset.page, 10));
          }
        });
      }

      if (DOM.promptInput && DOM.generateBtn && DOM.wordCountDisplay) {
        DOM.wordCountDisplay.style.display = "none";
        // ✅ FIX: Hide send and upload buttons by default
        DOM.generateBtn.style.display = "none";
        if (DOM.uploadBtn) DOM.uploadBtn.style.display = "none";

        on(DOM.promptInput, "input", () => {
          const trimmedValue = (DOM.promptInput.value || "").trim();
          const words = trimmedValue ? trimmedValue.split(/\s+/).filter(Boolean) : [];
          const wordCount = words.length;

          // ✅ FIX: Show buttons only when there is text
          const displayStyle = trimmedValue ? 'inline-flex' : 'none';
          DOM.generateBtn.style.display = displayStyle;
          if (DOM.uploadBtn) DOM.uploadBtn.style.display = displayStyle;

          DOM.wordCountDisplay.style.display = trimmedValue ? "block" : "none";
          DOM.wordCountDisplay.textContent = `${wordCount} / 1000 words`;

          if (wordCount > 1000) {
            DOM.wordCountDisplay.classList.add("text-red-500");
            DOM.generateBtn.disabled = true;
          } else {
            DOM.wordCountDisplay.classList.remove("text-red-500");
            DOM.generateBtn.disabled = !trimmedValue && attachedFiles.length === 0;
          }
        });
      }

      if (DOM.promptInput) {
        on(DOM.promptInput, "keydown", (e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleGenerate();
          }
        });
      }

      if (DOM.uploadBtn) on(DOM.uploadBtn, "click", () => DOM.fileInput?.click());
      if (DOM.fileInput) on(DOM.fileInput, "change", (e) => handleFiles(e.target.files));
      if (DOM.dropZone) {
        on(DOM.dropZone, "dragover", (e) => {
          e.preventDefault();
          DOM.dropZone.classList.add("border-indigo-500", "bg-indigo-50");
        });
        on(DOM.dropZone, "dragleave", () => {
          DOM.dropZone.classList.remove("border-indigo-500", "bg-indigo-50");
        });
        on(DOM.dropZone, "drop", (e) => {
          e.preventDefault();
          DOM.dropZone.classList.remove("border-indigo-500", "bg-indigo-50");
          handleFiles(e.dataTransfer.files);
        });
      }
    }

    // Initialize module
    async function init() {
      // Wire up events and initial state
      wireEvents();
      startNewChat();
      await fetchConversations();
      await setupModelSelector();
    }

    // Expose init
    return { init };
  })(SharedComponents);

  // -------------------------
  // Humanizer module
  // -------------------------
  const Humanizer = (function (Shared) {
    const { qs, qsa, on } = Shared.utils;
    const ROOT = qs("#humanizeForm");
    if (!ROOT) return { init: function () { /* not on page */ } };

    // App state and constants (use window-flask values or defaults)
    const AppState = {
      isLoggedIn: !!qs("#wallet-balance-amount"),
      pollingInterval: null,
      isPolling: false,
      alertTimeout: null,
      transactionId: null,
      pollingRetries: 0
    };

    const WORDS_PER_UNIT = window.FLASK_WORDS_PER_UNIT || 275;
    const PRICE_PER_UNIT = window.FLASK_PRICE_PER_UNIT || 49;
    const ESSAY_PRICE_PER_UNIT = window.FLASK_ESSAY_PRICE_PER_UNIT || 49;
    const FORMAT_ONLY_PRICE_PER_UNIT = window.FLASK_FORMAT_ONLY_PRICE_PER_UNIT || 19;
    const MIN_WORDS = 275;
    const MAX_WORDS = 1925;
    const POLLING_RATE = 1000;
    const ALERT_DURATION = 5000;

    // DOM elements (preserve original IDs)
    const DOM = {
      humanizeForm: qs("#humanizeForm"),
      inputText: qs("#input_text"),
      wordCountDisplay: qs("#input_word_count_display"),
      estimatedCostDisplay: qs("#estimated_cost_display"),
      humanizeBtn: qs("#openPaymentModalBtn"),
      paymentModal: qs("#paymentModal"),
      closeMpesaModalBtn: qs("#closeMpesaModalBtn"),
      phoneInput: qs("#phone_number_modal"),
      submitPaymentBtn: qs("#submitPaymentBtn"),
      outputSection: qs("#humanized_output_section"),
      outputDisplay: qs("#humanized_output_display"),
      outputPlaceholder: qs("#output_placeholder"),
      typingText: qs("#typing-text"),
      outputWordCount: qs("#output_word_count_value"),
      copyBtn: qs("#copyButton"),
      resetBtn: qs("#resetBtn"),
      jsAlertContainer: qs("#js-alert-container"),
      jsAlertMessage: qs("#js-alert-message"),
      modeBtn: qs("#modeBtn"),
      formatBtn: qs("#formatBtn"),
      dialectBtn: qs("#dialectBtn"),
      modePopup: qs("#modePopup"),
      formatPopup: qs("#formatPopup"),
      dialectPopup: qs("#dialectPopup"),
      modeDisplay: qs("#mode_display"),
      formatDisplay: qs("#format_display"),
      dialectDisplay: qs("#dialect_display"),
      humanizerModeRadios: qsa('input[name="humanizer_mode"]'),
      outputFormatRadios: qsa('input[name="output_format"]'),
      englishDialectRadios: qsa('input[name="english_dialect"]'),
      bibtexInput: qs("#bibtex_input"),
      toggleReferencesBtn: qs("#toggleReferencesBtn"),
      referencesSection: qs("#references_section"),
    };

    // type animation (keeps original behavior)
    const typeAnimation = {
      element: DOM.typingText,
      text: "Your output/download link will appear here.",
      speed: 75,
      currentIndex: 0,
      intervalId: null,
      start: function () {
        if (!this.element) return;
        this.reset();
        this.intervalId = setInterval(() => {
          if (this.currentIndex < this.text.length) {
            this.element.textContent += this.text.charAt(this.currentIndex);
            this.currentIndex++;
          } else {
            this.stop();
          }
        }, this.speed);
      },
      stop: function () { clearInterval(this.intervalId); },
      reset: function () {
        this.stop();
        if (this.element) this.element.textContent = "";
        this.currentIndex = 0;
      }
    };

    function copyToClipboard(elementId) {
      const element = qs(`#${elementId}`);
      if (!element) return;
      navigator.clipboard.writeText(element.innerText).then(() => Shared.showAlert("Copied!", "success")).catch(err => {
        console.error("Copy failed", err);
        Shared.showAlert("Failed to copy.", "danger");
      });
    }

    const UI = {
      showAlert: (message, type = "info") => Shared.showAlert(message, type, ALERT_DURATION),
      updateWordCountAndCost: () => {
        if (!DOM.inputText) return;
        const words = DOM.inputText.value.trim().split(/\s+/).filter(Boolean).length;
        const humanizerMode = qs('input[name="humanizer_mode"]:checked')?.value || "standard";
        let currentPrice;
        if (humanizerMode === "essay") currentPrice = ESSAY_PRICE_PER_UNIT;
        else if (humanizerMode === "document_formatter") currentPrice = FORMAT_ONLY_PRICE_PER_UNIT;
        else currentPrice = PRICE_PER_UNIT;
        const cost = (words / WORDS_PER_UNIT) * currentPrice;
        if (DOM.wordCountDisplay) DOM.wordCountDisplay.textContent = words;
        if (DOM.estimatedCostDisplay) DOM.estimatedCostDisplay.textContent = `KSh ${cost.toFixed(2)}`;
      },
      updateFormattingOptions: () => {
        const selectedMode = qs('input[name="humanizer_mode"]:checked');
        const selectedFormat = qs('input[name="output_format"]:checked');
        // enable all first
        qsa('input[name="humanizer_mode"], input[name="output_format"]').forEach(radio => {
          radio.disabled = false;
          const label = document.querySelector(`label[for="${radio.id}"]`);
          if (label) label.classList.remove("disabled");
        });

        if (selectedMode) {
          if (selectedMode.value === "standard") {
            qsa('input[name="output_format"]').forEach(radio => {
              if (["apa_7", "mla_9", "harvard"].includes(radio.value)) {
                radio.disabled = true;
                const label = document.querySelector(`label[for="${radio.id}"]`);
                if (label) label.classList.add("disabled");
                if (radio.checked) {
                  radio.checked = false;
                  if (DOM.formatDisplay) DOM.formatDisplay.textContent = "Format";
                }
              }
            });
          } else if (["essay", "document_formatter"].includes(selectedMode.value)) {
            const plainTextRadio = qs('input[value="plain_text"]');
            if (plainTextRadio) {
              plainTextRadio.disabled = true;
              const label = document.querySelector('label[for="plain_text_output"]');
              if (label) label.classList.add("disabled");
              if (plainTextRadio.checked) {
                plainTextRadio.checked = false;
                if (DOM.formatDisplay) DOM.formatDisplay.textContent = "Format";
              }
            }
          }
        }

        if (selectedFormat) {
          if (["apa_7", "mla_9", "harvard"].includes(selectedFormat.value)) {
            const standardRadio = qs('input[value="standard"]');
            if (standardRadio) {
              standardRadio.disabled = true;
              const label = document.querySelector('label[for="mode_standard"]');
              if (label) label.classList.add("disabled");
              if (standardRadio.checked) {
                standardRadio.checked = false;
                if (DOM.modeDisplay) DOM.modeDisplay.textContent = "Mode";
              }
            }
          } else if (selectedFormat.value === "plain_text") {
            qsa('input[name="humanizer_mode"]').forEach(radio => {
              if (["essay", "document_formatter"].includes(radio.value)) {
                radio.disabled = true;
                const label = document.querySelector(`label[for="${radio.id}"]`);
                if (label) label.classList.add("disabled");
                if (radio.checked) {
                  radio.checked = false;
                  if (DOM.modeDisplay) DOM.modeDisplay.textContent = "Mode";
                }
              }
            });
          }
        }

        const isDocx = selectedFormat && selectedFormat.value !== "plain_text";
        if (DOM.toggleReferencesBtn) DOM.toggleReferencesBtn.classList.toggle("hidden", !isDocx);
        if (!isDocx && DOM.referencesSection) DOM.referencesSection.classList.add("hidden");
      },
      resetSelections: () => {
        if (DOM.inputText) DOM.inputText.value = "";
        if (DOM.bibtexInput) DOM.bibtexInput.value = "";
        if (DOM.referencesSection) DOM.referencesSection.classList.add("hidden");
        if (DOM.toggleReferencesBtn) DOM.toggleReferencesBtn.classList.add("hidden");
        if (DOM.outputDisplay) DOM.outputDisplay.innerHTML = "";
        if (DOM.outputWordCount) DOM.outputWordCount.textContent = "0";
        if (DOM.copyBtn) DOM.copyBtn.style.display = "none";
        if (DOM.outputPlaceholder) DOM.outputPlaceholder.style.display = "flex";
        typeAnimation.start();
        if (DOM.outputSection) DOM.outputSection.classList.add("mobile-hidden");
        document.querySelectorAll('input[type="radio"]').forEach(r => r.checked = false);
        if (DOM.modeDisplay) DOM.modeDisplay.textContent = "Mode";
        if (DOM.formatDisplay) DOM.formatDisplay.textContent = "Format";
        if (DOM.dialectDisplay) DOM.dialectDisplay.textContent = "Dialect";
        document.querySelectorAll(".popup-trigger").forEach(btn => btn.classList.add("placeholder"));
        UI.updateFormattingOptions();
        UI.updateWordCountAndCost();
      },
      showProcessing: (message) => {
        if (DOM.outputPlaceholder) DOM.outputPlaceholder.style.display = "none";
        typeAnimation.stop();
        const loadingHtml = `<div id="loading-spinner" class="loading-in-output"><div class="spinner"></div><span class="mt-2">${message || "Processing..."}</span></div>`;
        if (DOM.outputDisplay) DOM.outputDisplay.innerHTML = loadingHtml;
        if (DOM.humanizeBtn) DOM.humanizeBtn.disabled = true;
      },
      hideProcessing: () => { if (DOM.humanizeBtn) DOM.humanizeBtn.disabled = false; },
      renderOutput: (data) => {
        if (data.download_url) {
          if (DOM.outputDisplay) DOM.outputDisplay.innerHTML = `<a href="${data.download_url}" class="download-link text-indigo-600 hover:text-indigo-900 font-semibold">Click here to download your document</a>`;
        } else {
          if (DOM.outputDisplay) DOM.outputDisplay.innerHTML = data.humanized_output;
        }
        if (DOM.outputWordCount) DOM.outputWordCount.textContent = data.output_word_count || 0;
        if (DOM.copyBtn && !data.download_url) DOM.copyBtn.style.display = "block";
      },
      openAnonymousPaymentModal: () => {
        const words = DOM.inputText ? DOM.inputText.value.trim().split(/\s+/).filter(Boolean).length : 0;
        const cost = (words / WORDS_PER_UNIT) * PRICE_PER_UNIT;
        const modalWordCount = qs("#modal_word_count_display");
        const modalEstimated = qs("#modal_estimated_cost_display");
        if (modalWordCount) modalWordCount.textContent = words;
        if (modalEstimated) modalEstimated.textContent = cost.toFixed(2);
        if (DOM.paymentModal) DOM.paymentModal.classList.remove("hidden");
      },
      closeAnonymousPaymentModal: () => { if (DOM.paymentModal) DOM.paymentModal.classList.add("hidden"); }
    };

    // Actions: submitting humanization and polling for status
    const Actions = {
        submitHumanization: async () => {
            const submitBtn = DOM.submitPaymentBtn;
            let originalButtonText = "";
            if (submitBtn) {
                originalButtonText = submitBtn.innerHTML;
                submitBtn.innerHTML = `<span class="spinner !w-5 !h-5"></span> Processing...`;
                submitBtn.disabled = true;
            }
        
            try {
                const selectedMode = qs('input[name="humanizer_mode"]:checked');
                const selectedFormat = qs('input[name="output_format"]:checked');
                const selectedDialect = qs('input[name="english_dialect"]:checked');
        
                if (!selectedMode || !selectedFormat || !selectedDialect) {
                    throw new Error("Please select a Mode, Format, and Dialect before proceeding.");
                }
        
                const formData = new FormData(DOM.humanizeForm);
                const words = DOM.inputText ? DOM.inputText.value.trim().split(/\s+/).filter(Boolean).length : 0;
                if (words < MIN_WORDS) throw new Error(`Input must be at least ${MIN_WORDS} words.`);
        
                if (!AppState.isLoggedIn) {
                    const phone = DOM.phoneInput ? DOM.phoneInput.value.trim() : "";
                    if (!/^(0|\+254)7[0-9]{8}$/.test(phone)) throw new Error("Invalid phone number.");
                    formData.set("phone_number", phone);
                    UI.closeAnonymousPaymentModal();
                    // ✅ FIX: Provide immediate feedback BEFORE making the async request.
                    UI.showAlert("Sending payment request...", "info");
                }
        
                UI.showProcessing("Processing request...");
                const response = await fetch("/submit-humanize-task", { method: "POST", body: formData });
                const data = await response.json();

                if (!response.ok) {
                    // ✅ FIX: Throw an error for non-2xx responses from the server.
                    // This ensures the catch block is always triggered for server-side errors.
                    throw new Error(data.message || "Error submitting your request.");
                }

                // ✅ FIX: Provide specific success feedback after the server confirms.
                if (AppState.isLoggedIn) {
                     UI.showAlert("Task submitted successfully! Your text is being humanized.", "success");
                } else {
                     UI.showAlert("STK push sent! Please complete payment on your phone.", "success");
                }
                
                AppState.transactionId = data.transaction_id;
                Actions.startPolling();

            } catch (err) {
                UI.showAlert(err.message || "Submission failed", "danger");
                UI.hideProcessing();
                // ✅ FIX: Call reset function on error
                UI.resetSelections();
            } finally {
                if (submitBtn) {
                    submitBtn.innerHTML = originalButtonText;
                    submitBtn.disabled = false;
                }
            }
          },

      checkStatus: async () => {
        if (!AppState.transactionId) return;
        try {
          const response = await fetch(`/get_humanization_status/${AppState.transactionId}`);
          if (!response.ok) {
            // ✅ FIX: If the server returns a 404, it might still be processing. Check attempts first.
            if (response.status === 404) {
              AppState.pollingRetries++;
              if (AppState.pollingRetries > 10) {
                Actions.stopPolling();
                UI.showAlert("Task could not be found. Please contact support.", "danger");
                UI.hideProcessing();
                // ✅ FIX: Call reset function on a critical error
                UI.resetSelections();
                return;
              }
              console.warn(`Task not found yet (attempt ${AppState.pollingRetries}), retrying...`);
              return;
            }
            // ✅ FIX: Handle other non-ok responses as a failure.
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || "Server returned an error.");
          }
          AppState.pollingRetries = 0;
          const data = await response.json();
          if (data.status === "complete" || data.status === "download_ready") {
            Actions.stopPolling();
            UI.renderOutput(data);
            if (data.diff_data && data.diff_data.refund_info) {
              UI.showAlert(data.diff_data.refund_info, "info");
            } else {
              UI.showAlert("Task complete!", "success");
            }
          } else if (data.status === "humanization_failed") {
            // ✅ FIX: Stop polling and spinner on a "failed" status from the server
            Actions.stopPolling();
            UI.showAlert(data.message || "An unexpected error occurred. Please try again.", "danger");
            UI.hideProcessing();
            // ✅ FIX: Call reset function on failed status
            UI.resetSelections();
          }
        } catch (err) {
          // ✅ FIX: Stop polling and spinner on any network/server error
          Actions.stopPolling();
          UI.showAlert(err.message || "Error checking status.", "danger");
          UI.hideProcessing();
            // ✅ FIX: Call reset function on any error
          UI.resetSelections();
        }
      },

      startPolling: () => {
        if (AppState.isPolling) return;
        AppState.pollingRetries = 0;
        AppState.pollingInterval = setInterval(Actions.checkStatus, POLLING_RATE);
        AppState.isPolling = true;
      },

      stopPolling: () => {
        clearInterval(AppState.pollingInterval);
        AppState.isPolling = false;
        UI.hideProcessing();
      }
    };

    function setupPopup(button, popup, display, radios) {
      if (!button || !popup || !display || !radios) return;
      on(button, "click", (e) => {
        e.stopPropagation();
        const isHidden = popup.classList.contains("hidden");
        qsa(".popup-menu").forEach(p => p.classList.add("hidden"));
        if (isHidden) {
          popup.classList.remove("hidden");
        }
      });
      radios.forEach(radio => on(radio, "change", () => {
        display.textContent = radio.nextElementSibling.textContent;
        button.classList.remove("placeholder");
        popup.classList.add("hidden");
        UI.updateFormattingOptions();
        UI.updateWordCountAndCost();
        if (radio.name === "humanizer_mode") {
          if (radio.value === "document_formatter") DOM.humanizeBtn.textContent = "Process"; else DOM.humanizeBtn.textContent = "Humanize";
        }
      }));
    }

    // Initialize wiring (event listeners)
    function init() {
      if (!DOM.humanizeForm) return;

      if (DOM.humanizeBtn) DOM.humanizeBtn.disabled = false;
      if (DOM.inputText) on(DOM.inputText, "input", UI.updateWordCountAndCost);
      if (DOM.copyBtn) on(DOM.copyBtn, "click", () => copyToClipboard("humanized_output_display"));
      if (DOM.resetBtn) on(DOM.resetBtn, "click", UI.resetSelections);
      
      if (DOM.humanizeBtn) on(DOM.humanizeBtn, "click", (e) => {
          e.preventDefault();
          AppState.isLoggedIn ? Actions.submitHumanization() : UI.openAnonymousPaymentModal();
      });
      
      if (DOM.submitPaymentBtn) on(DOM.submitPaymentBtn, "click", (e) => {
          e.preventDefault();
          Actions.submitHumanization();
      });

      if (DOM.closeMpesaModalBtn) on(DOM.closeMpesaModalBtn, "click", UI.closeAnonymousPaymentModal);

      if (DOM.toggleReferencesBtn && DOM.referencesSection) {
        on(DOM.toggleReferencesBtn, "click", (e) => { e.preventDefault(); DOM.referencesSection.classList.toggle("hidden"); });
      }

      setupPopup(DOM.modeBtn, DOM.modePopup, DOM.modeDisplay, DOM.humanizerModeRadios);
      setupPopup(DOM.formatBtn, DOM.formatPopup, DOM.formatDisplay, DOM.outputFormatRadios);
      setupPopup(DOM.dialectBtn, DOM.dialectPopup, DOM.dialectDisplay, DOM.englishDialectRadios);

      on(document.body, "click", (e) => { if (!e.target.closest(".popup-control")) qsa(".popup-menu").forEach(p => p.classList.add("hidden")); });

      UI.resetSelections();

      const textToHumanize = localStorage.getItem("textToHumanize");
      if (textToHumanize) {
        if (DOM.inputText) DOM.inputText.value = textToHumanize;
        UI.updateWordCountAndCost();
        localStorage.removeItem("textToHumanize");
      }
    }

    return { init };
  })(SharedComponents);

  // -------------------------
  // TaskView module
  // -------------------------
  const TaskView = (function (Shared) {
    const { qs, on } = Shared.utils;
    const ROOT = qs("#task-view-container");
    if (!ROOT) return { init: function () { /* not on page */ } };

    function init() {
      const copyBtn = qs("#copyTaskOutputBtn");
      const taskOutput = qs("#taskOutput");
      if (copyBtn && taskOutput) {
        on(copyBtn, "click", () => {
          navigator.clipboard.writeText(taskOutput.innerText).then(() => {
            Shared.showAlert("Copied to clipboard!", "success");
          }).catch(err => {
            Shared.showAlert("Failed to copy text.", "danger");
            console.error("Failed to copy text: ", err);
          });
        });
      }
    }

    return { init };
  })(SharedComponents);

  // -------------------------
  // Bootstrapping
  // -------------------------
  document.addEventListener("DOMContentLoaded", () => {
    // always init shared components (modals, top-up, nav, utilities)
    SharedComponents.init && SharedComponents.init();
    // initialize modules conditionally (each module checks for root)
    try { Playground.init && Playground.init(); } catch (err) { console.error("Playground init error", err); }
    try { Humanizer.init && Humanizer.init(); } catch (err) { console.error("Humanizer init error", err); }
    try { TaskView.init && TaskView.init(); } catch (err) { console.error("TaskView init error", err); }
  });

})();
