document.addEventListener('DOMContentLoaded', () => {

    // --- INITIALIZATION LOGIC ---
    initializeSharedComponents();

    const isPlaygroundPage = document.getElementById('playground-container');
    if (isPlaygroundPage) {
        initializePlayground();
    }

    const isHumanizerPage = document.getElementById('humanizeForm');
    if (isHumanizerPage) {
        initializeHumanizer();
    }

    //======================================================================
    //== SHARED LOGIC
    //======================================================================
    function initializeSharedComponents() {
        const DOMElements = {
            topUpBtn: document.getElementById('topUpBtn'),
            mobileTopUpBtn: document.getElementById('mobileTopUpBtn'),
            topUpModal: document.getElementById('topUpModal'),
            closeTopUpModalBtn: document.getElementById('closeTopUpModalBtn'),
            submitTopUpBtn: document.getElementById('submitTopUpBtn'),
            walletToggle: document.getElementById('wallet-toggle'),
            jsAlertContainer: document.getElementById('js-alert-container'),
            jsAlertMessage: document.getElementById('js-alert-message'),
            hamburgerBtn: document.getElementById('menu-btn'),
            mobileMenu: document.getElementById('mobile-menu')
        };

        const showAlert = (message, type = 'info') => {
            let alertTimeout = null;
            if (alertTimeout) clearTimeout(alertTimeout);
            const emojiMap = { success: '✅', danger: '❌', info: 'ℹ️' };
            if (DOMElements.jsAlertMessage) DOMElements.jsAlertMessage.textContent = `${emojiMap[type] || 'ℹ️'} ${message}`;
            if (DOMElements.jsAlertContainer) {
                DOMElements.jsAlertContainer.className = 'js-alert-container flash-message rounded-lg shadow-md';
                DOMElements.jsAlertContainer.classList.add(`flash-${type}`, 'show');
            }
            alertTimeout = setTimeout(() => DOMElements.jsAlertContainer?.classList.remove('show'), 5000);
        };

        const UI = {
            openTopUpModal: () => DOMElements.topUpModal?.classList.remove('hidden'),
            closeTopUpModal: () => DOMElements.topUpModal?.classList.add('hidden'),
            toggleMobileMenu: () => DOMElements.mobileMenu?.classList.toggle('hidden')
        };

        const Actions = {
            submitTopUp: async () => {
                const amount = document.getElementById('top_up_amount').value;
                const phone = document.getElementById('phone_number_top_up').value.trim();
                if (!amount || amount <= 0) return showAlert('Please enter a valid amount.', 'danger');
                if (!/^(0|\+254)7[0-9]{8}$/.test(phone)) return showAlert('Invalid phone number.', 'danger');
                UI.closeTopUpModal();
                showAlert('Sending top-up request...', 'info');
                try {
                    const response = await fetch('/wallet/topup', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ amount: parseFloat(amount), phone_number: phone })
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || 'An error occurred.');
                    showAlert('STK push sent. Please check your phone to complete payment.', 'success');
                } catch (error) {
                    showAlert(error.message, 'danger');
                }
            },
            toggleWalletBalance: () => {
                const walletIcon = document.getElementById('wallet-icon');
                const walletBalanceAmount = document.getElementById('wallet-balance-amount');
                if (!DOMElements.walletToggle || !walletIcon || !walletBalanceAmount) return;
                const isHidden = DOMElements.walletToggle.classList.toggle('balance-hidden');
                walletIcon.classList.toggle('text-gray-500', !isHidden);
                walletIcon.classList.toggle('text-green-600', isHidden);
                walletBalanceAmount.classList.toggle('text-green-600', !isHidden);
                walletBalanceAmount.classList.toggle('text-gray-500', isHidden);
                walletBalanceAmount.textContent = isHidden ? 'KSh ***' : `KSh ${walletBalanceAmount.dataset.balance}`;
            }
        };

        if (DOMElements.topUpBtn) DOMElements.topUpBtn.addEventListener('click', UI.openTopUpModal);
        if (DOMElements.mobileTopUpBtn) DOMElements.mobileTopUpBtn.addEventListener('click', UI.openTopUpModal);
        if (DOMElements.closeTopUpModalBtn) DOMElements.closeTopUpModalBtn.addEventListener('click', UI.closeTopUpModal);
        if (DOMElements.submitTopUpBtn) DOMElements.submitTopUpBtn.addEventListener('click', Actions.submitTopUp);
        if (DOMElements.walletToggle) DOMElements.walletToggle.addEventListener('click', Actions.toggleWalletBalance);
        if (DOMElements.hamburgerBtn) DOMElements.hamburgerBtn.addEventListener('click', UI.toggleMobileMenu);
        window.addEventListener('click', (e) => {
            if (e.target === DOMElements.topUpModal) UI.closeTopUpModal();
        });
    }

    //======================================================================
    //== PLAYGROUND LOGIC
    //======================================================================
    function initializePlayground() {
        let alertTimeout = null;
        const ALERT_DURATION = 5000;
        let isFetchingHistory = false;
        let isChatActive = false;
        let attachedFiles = [];
        const MAX_TOTAL_SIZE = 10 * 1024 * 1024;
        let pollingInterval = null;

        const DOMElements = {
            modelSelectionBar: document.getElementById('model-selection-bar'),
            uploadBtn: document.getElementById('upload-btn'),
            fileInput: document.getElementById('file-input'),
            attachmentPreviewContainer: document.getElementById('attachment-preview-container'),
            chatLog: document.getElementById('chat-log'),
            promptInput: document.getElementById('prompt-input'),
            generateBtn: document.getElementById('generate-btn'),
            newChatBtn: document.getElementById('new-chat-btn'),
            conversationList: document.getElementById('conversation-list'),
            modelSelector: document.getElementById('model-selector'),
            modelSelectorBtn: document.getElementById('model-selector-btn'),
            modelSelectorOptions: document.getElementById('model-selector-options'),
            modelSelectorLabel: document.getElementById('model-selector-label'),
            jsAlertContainer: document.getElementById('js-alert-container'),
            jsAlertMessage: document.getElementById('js-alert-message'),
            historySidebar: document.getElementById('history-sidebar'),
            showHistoryBtn: document.getElementById('show-history-btn'),
            searchHistoryInput: document.getElementById('search-history-input'),
            paginationContainer: document.getElementById('history-pagination-container'),
            historyLoadingSpinner: document.getElementById('history-loading-spinner'),
            playgroundWelcomeHeader: document.getElementById('playground-welcome-header'),
            playgroundContainer: document.getElementById('playground-container'),
            dropZone: document.getElementById('drop-zone'),
            conversationIdInput: document.getElementById('conversation-id-storage'),
        };

        const sidebarOverlay = document.createElement('div');
        sidebarOverlay.classList.add('sidebar-overlay');
        document.body.appendChild(sidebarOverlay);

        function markdownToHtml(text) {
            if (typeof marked !== 'undefined') {
               return marked.parse(text);
            }
            console.warn("marked.js not loaded. Using fallback markdown renderer.");
            return text
                .replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
                .replace(/\n/g, '<br>');
        }
        
        const highlightCodeBlocks = () => {
           if (typeof hljs === 'undefined') {
               console.warn('highlight.js not loaded, skipping syntax highlighting.');
               return;
           }
        
           document.querySelectorAll('#chat-log pre').forEach((preElement) => {
               const block = preElement.querySelector('code');
               if (!block) return;
        
               if (!block.hasAttribute('data-highlighted')) {
                   hljs.highlightElement(block);
                   block.setAttribute('data-highlighted', 'true');
               }
        
               if (!preElement.querySelector('.code-copy-btn')) {
                   const copyBtn = document.createElement('button');
                   copyBtn.className = 'code-copy-btn';
                   copyBtn.title = 'Copy code';
        
                   const clipboardIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>`;
                   const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>`;
        
                   copyBtn.innerHTML = clipboardIcon;
        
                   copyBtn.addEventListener('click', () => {
                       navigator.clipboard.writeText(block.innerText).then(() => {
                           copyBtn.innerHTML = checkIcon;
                           setTimeout(() => {
                               copyBtn.innerHTML = clipboardIcon;
                           }, 2000);
                       }).catch(err => {
                           console.error('Failed to copy text: ', err);
                       });
                   });
        
                   preElement.prepend(copyBtn);
               }
           });
        };

        const showAlert = (message, type = 'info') => {
            if (alertTimeout) clearTimeout(alertTimeout);
            const emojiMap = { success: '✅', danger: '❌', info: 'ℹ️' };
            if (DOMElements.jsAlertMessage) DOMElements.jsAlertMessage.textContent = `${emojiMap[type] || 'ℹ️'} ${message}`;
            if (DOMElements.jsAlertContainer) {
                DOMElements.jsAlertContainer.className = 'js-alert-container flash-message rounded-lg shadow-md';
                DOMElements.jsAlertContainer.classList.add(`flash-${type}`, 'show');
            }
            alertTimeout = setTimeout(() => DOMElements.jsAlertContainer?.classList.remove('show'), ALERT_DURATION);
        };

        const showProcessing = (isProcessing) => {
            if (DOMElements.generateBtn) DOMElements.generateBtn.disabled = isProcessing;
        };
        
        const toggleHistorySidebar = () => {
            if (DOMElements.historySidebar && sidebarOverlay) {
                DOMElements.historySidebar.classList.toggle('mobile-hidden');
                sidebarOverlay.classList.toggle('show');
            }
        };

        const pollForTaskResult = (taskId, messageContainer, messageBubble) => {
            let attempts = 0;
            pollingInterval = setInterval(async () => {
                attempts++;
                if (attempts > 60) {
                    clearInterval(pollingInterval);
                    messageBubble.innerHTML = `<p class="text-red-500">Error: The request timed out. Please try again.</p>`;
                    showProcessing(false);
                    return;
                }
                try {
                    const response = await fetch(`/get_playground_task_status/${taskId}`);
                    if (!response.ok) {
                        if (response.status !== 404 || attempts > 5) {
                           throw new Error("Failed to get task status from server.");
                        }
                        return;
                    }
                    const data = await response.json();
                    if (data.status === 'complete') {
                        clearInterval(pollingInterval);
                        messageBubble.innerHTML = markdownToHtml(data.response);
                        highlightCodeBlocks();
                        addMessageActions(messageContainer, data.response);
                        showProcessing(false);
                        
                        if (data.conversation_title) {
                            const convItem = DOMElements.conversationList.querySelector(`[data-conv-id="${data.conversation_id}"]`);
                            if (convItem) {
                                const titleSpan = convItem.querySelector('span.truncate');
                                if(titleSpan) titleSpan.textContent = data.conversation_title;
                            }
                        }

                    } else if (data.status === 'failed') {
                        clearInterval(pollingInterval);
                        messageBubble.innerHTML = `<p class="text-red-500">Error: ${data.error || 'Processing failed.'}</p>`;
                        showProcessing(false);
                    }
                } catch (error) {
                    clearInterval(pollingInterval);
                    messageBubble.innerHTML = `<p class="text-red-500">Error: ${error.message}</p>`;
                    showProcessing(false);
                }
            }, 3000);
        };
        
        const handleGenerate = async () => {
            if (!DOMElements.promptInput) return;
            const prompt = DOMElements.promptInput.value.trim();
            if (!prompt && attachedFiles.length === 0) return showAlert('Please enter a prompt or attach a file.', 'info');
            
            const currentConversationId = DOMElements.conversationIdInput.value;

            if (!currentConversationId && DOMElements.modelSelectionBar) {
                DOMElements.modelSelectionBar.style.display = 'none';
            }
            if (!isChatActive) {
                isChatActive = true;
                if (DOMElements.playgroundWelcomeHeader) DOMElements.playgroundWelcomeHeader.classList.add('chat-active');
                if (DOMElements.playgroundContainer) DOMElements.playgroundContainer.classList.add('chat-active');
            }
            let userInputPayload = [{ "type": "input_text", "text": prompt }];
            let displayMessage = prompt;
            attachedFiles.forEach(file => {
                if (file.type.startsWith('image/')) {
                    userInputPayload.push({ "type": "input_image", "image_url": { "url": file.data } });
                } else {
                    userInputPayload.push({ "type": "input_text", "text": `\n\n--- Document: ${file.name} ---\n${file.data}` });
                }
            });
            if (attachedFiles.length > 0) {
                displayMessage = prompt ? `${prompt} [${attachedFiles.length} file(s) attached]` : `[${attachedFiles.length} file(s) attached]`;
            }
            addMessageToLog('user', displayMessage);
            
            DOMElements.promptInput.value = '';
            attachedFiles = [];
            renderAttachedFiles();

            showProcessing(true);
            const thinkingPlaceholder = `<div class="flex items-center gap-x-2"><div class="spinner !w-5 !h-5"></div><span>Thinking...</span></div>`;
            const { messageContainer, messageBubble } = addMessageToLog('bot', thinkingPlaceholder, false);
            try {
                if (!DOMElements.modelSelector) throw new Error("Model selector not found.");
                const selectedModel = DOMElements.modelSelector.dataset.selectedValue;
                if (!selectedModel) throw new Error('Please select a model.');
                const response = await fetch('/playground_chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model: selectedModel,
                        input: userInputPayload,
                        conversation_id: currentConversationId,
                    })
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Failed to start the chat task.');

                if (data.conversation_id) {
                    const isNewConversation = !DOMElements.conversationIdInput.value;
                    DOMElements.conversationIdInput.value = data.conversation_id;
                    if (isNewConversation) {
                        await fetchConversations(); 
                    }
                }

                if (data.status === 'processing_started' && data.task_id) {
                    pollForTaskResult(data.task_id, messageContainer, messageBubble);
                } else {
                    throw new Error("Invalid response from server when starting task.");
                }
            } catch (error) {
                messageBubble.innerHTML = `<p class="text-red-500">Error: ${error.message}</p>`;
                showProcessing(false);
            }
        };

        const renderAttachedFiles = () => {
            if (!DOMElements.attachmentPreviewContainer) return;
            DOMElements.attachmentPreviewContainer.innerHTML = '';
            if (attachedFiles.length === 0) return;
            attachedFiles.forEach((file, index) => {
                const fileElement = document.createElement('div');
                fileElement.className = 'bg-gray-100 p-2 rounded-lg flex items-center justify-between text-sm';
                let previewContent = `<span class="text-gray-700 truncate">${file.name}</span>`;
                if (file.type.startsWith('image/')) {
                    previewContent = `<img src="${file.data}" class="w-8 h-8 rounded-md object-cover mr-2">` + previewContent;
                }
                fileElement.innerHTML = `<div class="flex items-center gap-x-2">${previewContent}</div><button data-index="${index}" class="remove-attachment-btn p-1 rounded-full text-gray-500 hover:bg-gray-300"><svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg></button>`;
                DOMElements.attachmentPreviewContainer.appendChild(fileElement);
            });
            document.querySelectorAll('.remove-attachment-btn').forEach(button => {
                button.addEventListener('click', (e) => {
                    const indexToRemove = parseInt(e.currentTarget.dataset.index, 10);
                    attachedFiles.splice(indexToRemove, 1);
                    renderAttachedFiles();
                });
            });
        };
        
        const handleFiles = async (files) => {
            const fileList = Array.from(files);
            let totalSize = attachedFiles.reduce((acc, f) => acc + f.size, 0);
            for (const file of fileList) {
                totalSize += file.size;
                if (totalSize > MAX_TOTAL_SIZE) {
                    showAlert(`Total file size cannot exceed 10MB.`, 'danger');
                    return;
                }
            }
            showAlert('Processing attachments...', 'info');
            for (const file of fileList) {
                const allowedImageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
                const allowedTextFiles = ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
                let fileData = { name: file.name, type: file.type, size: file.size, data: null };
                if (allowedImageTypes.includes(file.type)) {
                    fileData.data = await new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onload = (event) => resolve(event.target.result);
                        reader.readAsDataURL(file);
                    });
                    attachedFiles.push(fileData);
                } else if (allowedTextFiles.includes(file.type) || file.name.toLowerCase().endsWith('.txt') || file.name.toLowerCase().endsWith('.docx')) {
                    const formData = new FormData();
                    formData.append('file', file);
                    try {
                        const response = await fetch('/extract_text_from_file', { method: 'POST', body: formData });
                        const data = await response.json();
                        if (!response.ok) throw new Error(data.error);
                        fileData.data = data.text;
                        attachedFiles.push(fileData);
                    } catch (error) {
                        showAlert(`Failed to process ${file.name}: ${error.message}`, 'danger');
                    }
                } else {
                    showAlert(`Unsupported file type: ${file.name}`, 'danger');
                }
            }
            renderAttachedFiles();
        };

        const addMessageActions = (messageContainer, messageText) => {
            const actionsContainer = document.createElement('div');
            actionsContainer.className = 'flex items-center gap-x-2 mt-2 ml-2';
            const copyBtn = document.createElement('button');
            copyBtn.className = 'p-1 rounded-md bg-gray-100 text-gray-600 hover:bg-indigo-200 hover:text-indigo-700';
            copyBtn.title = 'Copy';
            const clipboardIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>`;
            const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>`;
            copyBtn.innerHTML = clipboardIcon;
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(messageText);
                copyBtn.innerHTML = checkIcon;
                setTimeout(() => copyBtn.innerHTML = clipboardIcon, 2000);
            };
            const humanizeBtn = document.createElement('button');
            humanizeBtn.className = 'p-1 rounded-md bg-gray-100 text-gray-600 hover:bg-indigo-200 hover:text-indigo-700';
            humanizeBtn.title = 'Humanize';
            humanizeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2Z"/></svg>`;
            humanizeBtn.onclick = () => {
                localStorage.setItem('textToHumanize', messageText);
                window.location.href = '/humanizer';
            };
            actionsContainer.append(copyBtn, humanizeBtn);
            messageContainer.appendChild(actionsContainer);
        };
        
        const addMessageToLog = (sender, content, addActions = false) => {
            if (!DOMElements.chatLog) return;
            const isUser = sender === 'user';
            const messageContainer = document.createElement('div');
            messageContainer.className = `message-container ${isUser ? 'user-message-container' : 'bot-message-container'}`;
            const messageBubble = document.createElement('div');
            messageBubble.className = `message-bubble ${isUser ? 'user-message' : 'bot-message'}`;
            
            messageBubble.innerHTML = isUser ? content.replace(/</g, "&lt;").replace(/>/g, "&gt;") : markdownToHtml(content);
            messageContainer.appendChild(messageBubble);

            if (!isUser && addActions) {
                addMessageActions(messageContainer, content);
            }
            
            DOMElements.chatLog.appendChild(messageContainer);
            highlightCodeBlocks();
            DOMElements.chatLog.scrollTop = DOMElements.chatLog.scrollHeight;
            return { messageContainer, messageBubble };
        };

        const loadConversation = async (convId) => {
            try {
                const response = await fetch(`/conversation/${convId}`);
                if (!response.ok) throw new Error('Failed to load conversation.');
                const messages = await response.json();
                if (DOMElements.chatLog) DOMElements.chatLog.innerHTML = '';
                
                DOMElements.conversationIdInput.value = convId;

                if (DOMElements.modelSelectionBar) DOMElements.modelSelectionBar.style.display = 'none';
                messages.forEach(msg => {
                    let content = msg.content;
                    if (msg.role === 'user' && typeof msg.content === 'string') {
                        try { content = JSON.parse(msg.content); } catch (e) { /* Not JSON */ }
                    }
                    if (msg.role === 'user') {
                        let displayContent = "";
                         if (Array.isArray(content)) {
                             const textParts = content.filter(part => part.type === 'input_text').map(part => part.text).join(' ');
                             const hasAttachments = content.some(part => part.type !== 'input_text');
                             displayContent = textParts + (hasAttachments ? ` [${content.length - 1} file(s) attached]` : '');
                         } else {
                             displayContent = content;
                         }
                        addMessageToLog('user', displayContent);
                    } else {
                        addMessageToLog('bot', content, true);
                    }
                });
                if (DOMElements.chatLog) DOMElements.chatLog.scrollTop = DOMElements.chatLog.scrollHeight;
                if (!isChatActive) {
                    isChatActive = true;
                    if (DOMElements.playgroundWelcomeHeader) DOMElements.playgroundWelcomeHeader.classList.add('chat-active');
                    if (DOMElements.playgroundContainer) DOMElements.playgroundContainer.classList.add('chat-active');
                }
                document.querySelectorAll('#conversation-list > div').forEach(div => div.classList.toggle('bg-gray-200', div.dataset.convId == convId));
                
                // --- CODEBLOCK FIX ---
                highlightCodeBlocks();
                // --- END FIX ---

                if (window.innerWidth < 1024) toggleHistorySidebar();
            } catch (error) {
                showAlert(error.message, 'danger');
            }
        };

        const deleteConversation = async (convId) => {
            if (!confirm('Are you sure you want to delete this chat?')) return;
            try {
                const response = await fetch(`/conversation/${convId}`, { method: 'DELETE' });
                if (!response.ok) throw new Error('Failed to delete.');
                showAlert('Conversation deleted.', 'success');
                fetchConversations(DOMElements.searchHistoryInput.value, 1);
                if (DOMElements.conversationIdInput.value === convId) startNewChat();
            } catch (error) {
                showAlert(error.message, 'danger');
            }
        };

        const renderPagination = (totalPages, currentPage) => {
            if (!DOMElements.paginationContainer) return;
            DOMElements.paginationContainer.innerHTML = '';
            if (totalPages <= 1) return;
            const createButton = (text, page, isDisabled = false, isActive = false) => {
                const button = document.createElement('button');
                button.innerHTML = text;
                button.dataset.page = page;
                button.disabled = isDisabled;
                button.className = `px-2 py-0.5 text-xs rounded-md ${isActive ? 'bg-indigo-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100 border'}`;
                return button;
            };
            const wrapper = document.createElement('div');
            wrapper.className = 'flex items-center justify-center space-x-0.5';
            wrapper.appendChild(createButton('&laquo;', currentPage - 1, currentPage === 1));
            for (let i = 1; i <= totalPages; i++) {
                if (totalPages > 7 && Math.abs(currentPage - i) > 2 && i !== 1 && i !== totalPages) {
                    if (i === 2 || i === totalPages - 1) wrapper.insertAdjacentHTML('beforeend', `<span class="px-2 py-0.5 text-xs">...</span>`);
                    continue;
                }
                wrapper.appendChild(createButton(i, i, false, i === currentPage));
            }
            wrapper.appendChild(createButton('&raquo;', currentPage + 1, currentPage === totalPages));
            DOMElements.paginationContainer.appendChild(wrapper);
        };

        const appendConversations = (conversations) => {
            if (!DOMElements.conversationList) return;
            DOMElements.conversationList.innerHTML = '';
            if (!conversations || conversations.length === 0) {
                DOMElements.conversationList.innerHTML = `<p class="text-xs text-gray-500 p-2">No past conversations.</p>`;
                return;
            }
            conversations.forEach(conv => {
                const convItem = document.createElement('div');
                convItem.className = 'flex justify-between items-center p-2 rounded-md hover:bg-gray-100 cursor-pointer';
                convItem.dataset.convId = conv.id;
                const titleSpan = document.createElement('span');
                titleSpan.className = 'text-sm text-gray-700 truncate';
                titleSpan.textContent = conv.title;
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'text-gray-400 hover:text-red-500 p-1';
                deleteBtn.innerHTML = `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>`;
                convItem.append(titleSpan, deleteBtn);
                titleSpan.onclick = () => loadConversation(conv.id);
                deleteBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(conv.id); };
                DOMElements.conversationList.appendChild(convItem);
            });
        };
        
        const fetchConversations = async (query = '', page = 1) => {
            if (isFetchingHistory) return;
            isFetchingHistory = true;
            if (DOMElements.historyLoadingSpinner) DOMElements.historyLoadingSpinner.style.display = 'block';
            try {
                const response = await fetch(`/get_conversations?q=${encodeURIComponent(query)}&page=${page}`);
                if (!response.ok) throw new Error('Failed to fetch conversations.');
                const data = await response.json();
                appendConversations(data.conversations);
                renderPagination(data.total_pages, data.current_page);
            } catch (error) {
                showAlert(error.message, 'danger');
            } finally {
                if (DOMElements.historyLoadingSpinner) DOMElements.historyLoadingSpinner.style.display = 'none';
                isFetchingHistory = false;
            }
        };

        const startNewChat = () => {
            clearInterval(pollingInterval);
            if (DOMElements.conversationIdInput) DOMElements.conversationIdInput.value = '';
            
            attachedFiles = [];
            renderAttachedFiles();
            if (DOMElements.chatLog) DOMElements.chatLog.innerHTML = '';
            if (DOMElements.promptInput) DOMElements.promptInput.value = '';
            if (DOMElements.modelSelectionBar) DOMElements.modelSelectionBar.style.display = 'block';
            
            addMessageToLog('bot', 'Hello! How can I assist you today? Select a model and ask me anything.', false);

            isChatActive = false;
            if (DOMElements.playgroundWelcomeHeader) DOMElements.playgroundWelcomeHeader.classList.remove('chat-active');
            if (DOMElements.playgroundContainer) DOMElements.playgroundContainer.classList.remove('chat-active');
            if (window.innerWidth < 1024 && DOMElements.historySidebar && !DOMElements.historySidebar.classList.contains('mobile-hidden')) toggleHistorySidebar();
            document.querySelectorAll('#conversation-list > div').forEach(div => div.classList.remove('bg-gray-200'));
        };
        
        const setupModelSelector = async () => {
            if (!DOMElements.modelSelector) {
                console.warn("Model selector element not found.");
                return;
            }
            try {
                const response = await fetch('/api/get-models');
                if (!response.ok) throw new Error('Failed to load models.');
                const models = await response.json();

                if (!models || models.length === 0) {
                    showAlert('Could not load any AI models. Please contact support.', 'danger');
                    return; 
                }

                if (DOMElements.modelSelectorOptions) DOMElements.modelSelectorOptions.innerHTML = '';
                const selectedModel = models.find(m => m.selected) || models[0];
                models.forEach(model => {
                    const li = document.createElement('li');
                    li.className = 'model-option p-2 hover:bg-gray-100 cursor-pointer';
                    li.dataset.value = model.value;
                    li.innerHTML = `<span class="font-semibold">${model.label}</span>`;
                    if (model.selected) li.classList.add('bg-gray-200');
                    li.onclick = () => {
                        if (DOMElements.modelSelectorOptions) {
                            DOMElements.modelSelectorOptions.querySelectorAll('.model-option').forEach(opt => opt.classList.remove('bg-gray-200'));
                        }
                        li.classList.add('bg-gray-200');
                        DOMElements.modelSelector.dataset.selectedValue = model.value;
                        if (DOMElements.modelSelectorLabel) DOMElements.modelSelectorLabel.textContent = model.label;
                        if (DOMElements.modelSelectorOptions) DOMElements.modelSelectorOptions.classList.remove('options-visible');
                    };
                    if (DOMElements.modelSelectorOptions) DOMElements.modelSelectorOptions.appendChild(li);
                });
                DOMElements.modelSelector.dataset.selectedValue = selectedModel.value;
                if (DOMElements.modelSelectorLabel) DOMElements.modelSelectorLabel.textContent = selectedModel.label;
                if (DOMElements.modelSelectorBtn) DOMElements.modelSelectorBtn.onclick = () => DOMElements.modelSelectorOptions?.classList.toggle('options-visible');
            } catch (error) {
                showAlert(error.message, 'danger');
            }
        };

        if (DOMElements.generateBtn) DOMElements.generateBtn.addEventListener('click', handleGenerate);
        if (DOMElements.newChatBtn) DOMElements.newChatBtn.addEventListener('click', startNewChat);
        if (DOMElements.showHistoryBtn) DOMElements.showHistoryBtn.addEventListener('click', toggleHistorySidebar);
        if (sidebarOverlay) sidebarOverlay.addEventListener('click', toggleHistorySidebar);
        if (DOMElements.searchHistoryInput) {
            let searchTimeout;
            DOMElements.searchHistoryInput.oninput = (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => fetchConversations(e.target.value, 1), 300);
            };
        }
        if (DOMElements.paginationContainer) {
            DOMElements.paginationContainer.onclick = (e) => {
                const button = e.target.closest('button');
                if (button && button.dataset.page && !button.disabled) fetchConversations(DOMElements.searchHistoryInput.value, parseInt(button.dataset.page));
            };
        }
        if (DOMElements.promptInput) DOMElements.promptInput.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleGenerate(); } };
        if (DOMElements.uploadBtn) DOMElements.uploadBtn.onclick = () => DOMElements.fileInput?.click();
        if (DOMElements.fileInput) DOMElements.fileInput.onchange = (e) => handleFiles(e.target.files);
        if (DOMElements.dropZone) {
            DOMElements.dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                DOMElements.dropZone.classList.add('border-indigo-500', 'bg-indigo-50');
            });
            DOMElements.dropZone.addEventListener('dragleave', () => {
                DOMElements.dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
            });
            DOMElements.dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                DOMElements.dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
                handleFiles(e.dataTransfer.files);
            });
        }

        startNewChat();
        fetchConversations();
        setupModelSelector();
    }


    //======================================================================
    //== HUMANIZER LOGIC
    //======================================================================
    function initializeHumanizer() {
        const AppState = {
            isLoggedIn: document.getElementById('wallet-balance-amount') !== null,
            pollingInterval: null,
            isPolling: false,
            alertTimeout: null,
            transactionId: null,
            pollingRetries: 0
        };
        const WORDS_PER_UNIT = window.FLASK_WORDS_PER_UNIT || 100;
        const PRICE_PER_UNIT = window.FLASK_PRICE_PER_UNIT || 10;
        const ESSAY_PRICE_PER_UNIT = window.FLASK_ESSAY_PRICE_PER_UNIT || 15;
        const MIN_WORDS = 275;
        const MAX_WORDS = 1925;
        const POLLING_RATE = 3000;
        const ALERT_DURATION = 5000;

        const DOMElements = {
            humanizeForm: document.getElementById('humanizeForm'),
            inputText: document.getElementById('input_text'),
            wordCountDisplay: document.getElementById('input_word_count_display'),
            estimatedCostDisplay: document.getElementById('estimated_cost_display'),
            humanizeBtn: document.getElementById('openPaymentModalBtn'),
            paymentModal: document.getElementById('paymentModal'),
            closeMpesaModalBtn: document.getElementById('closeMpesaModalBtn'),
            phoneInput: document.getElementById('phone_number_modal'),
            submitPaymentBtn: document.getElementById('submitPaymentBtn'),
            outputSection: document.getElementById('humanized_output_section'),
            outputDisplay: document.getElementById('humanized_output_display'),
            outputPlaceholder: document.getElementById('output_placeholder'),
            typingText: document.getElementById('typing-text'),
            outputWordCount: document.getElementById('output_word_count_value'),
            copyBtn: document.getElementById('copyButton'),
            resetBtn: document.getElementById('resetBtn'),
            jsAlertContainer: document.getElementById('js-alert-container'),
            jsAlertMessage: document.getElementById('js-alert-message'),
            modeBtn: document.getElementById('modeBtn'),
            formatBtn: document.getElementById('formatBtn'),
            dialectBtn: document.getElementById('dialectBtn'),
            modePopup: document.getElementById('modePopup'),
            formatPopup: document.getElementById('formatPopup'),
            dialectPopup: document.getElementById('dialectPopup'),
            modeDisplay: document.getElementById('mode_display'),
            formatDisplay: document.getElementById('format_display'),
            dialectDisplay: document.getElementById('dialect_display'),
            humanizerModeRadios: document.querySelectorAll('input[name="humanizer_mode"]'),
            outputFormatRadios: document.querySelectorAll('input[name="output_format"]'),
            englishDialectRadios: document.querySelectorAll('input[name="english_dialect"]'),
            bibtexInput: document.getElementById('bibtex_input'),
            toggleReferencesBtn: document.getElementById('toggleReferencesBtn'),
            referencesSection: document.getElementById('references_section'),
        };

        const typeAnimation = {
            element: DOMElements.typingText,
            text: "Humanized content will appear here!",
            speed: 75,
            currentIndex: 0,
            intervalId: null,
            start: function() {
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
            stop: function() { clearInterval(this.intervalId); },
            reset: function() {
                this.stop();
                if (this.element) this.element.textContent = '';
                this.currentIndex = 0;
            }
        };
        
        function copyToClipboard(elementId) {
            const element = document.getElementById(elementId);
            if (!element) return;
            navigator.clipboard.writeText(element.innerText).then(() => UI.showAlert('Copied!', 'success'));
        }

        const UI = {
            showAlert: (message, type = 'info') => {
                if (AppState.alertTimeout) clearTimeout(AppState.alertTimeout);
                const emojiMap = { success: '✅', danger: '❌', info: 'ℹ️' };
                if (DOMElements.jsAlertMessage) DOMElements.jsAlertMessage.textContent = `${emojiMap[type] || 'ℹ️'} ${message}`;
                if (DOMElements.jsAlertContainer) {
                    DOMElements.jsAlertContainer.className = 'js-alert-container flash-message rounded-lg shadow-md';
                    DOMElements.jsAlertContainer.classList.add(`flash-${type}`, 'show');
                }
                AppState.alertTimeout = setTimeout(() => DOMElements.jsAlertContainer?.classList.remove('show'), ALERT_DURATION);
            },
            updateWordCountAndCost: () => {
                if (!DOMElements.inputText) return;
                const words = DOMElements.inputText.value.trim().split(/\s+/).filter(Boolean).length;
                const humanizerMode = document.querySelector('input[name="humanizer_mode"]:checked')?.value || 'standard';
                const currentPrice = (humanizerMode === 'essay') ? ESSAY_PRICE_PER_UNIT : PRICE_PER_UNIT;
                const cost = (words / WORDS_PER_UNIT) * currentPrice;
                if (DOMElements.wordCountDisplay) DOMElements.wordCountDisplay.textContent = words;
                if (DOMElements.estimatedCostDisplay) DOMElements.estimatedCostDisplay.textContent = `KSh ${cost.toFixed(2)}`;
            },
            updateFormattingOptions: () => {
                const selectedMode = document.querySelector('input[name="humanizer_mode"]:checked');
                const selectedFormat = document.querySelector('input[name="output_format"]:checked');
                document.querySelectorAll('input[name="humanizer_mode"], input[name="output_format"]').forEach(radio => {
                    if (document.querySelector(`label[for="${radio.id}"]`)) {
                        radio.disabled = false;
                        document.querySelector(`label[for="${radio.id}"]`).classList.remove('disabled');
                    }
                });
                if (selectedMode) {
                    if (selectedMode.value === 'standard') {
                        document.querySelectorAll('input[name="output_format"]').forEach(radio => {
                            if (['apa_7', 'mla_9', 'harvard'].includes(radio.value)) {
                                radio.disabled = true;
                                document.querySelector(`label[for="${radio.id}"]`).classList.add('disabled');
                            }
                        });
                    } else if (['essay', 'document_formatter'].includes(selectedMode.value)) {
                        const plainTextRadio = document.querySelector('input[value="plain_text"]');
                        if (plainTextRadio) {
                            plainTextRadio.disabled = true;
                            document.querySelector('label[for="plain_text_output"]').classList.add('disabled');
                        }
                    }
                }
                if (selectedFormat) {
                    if (['apa_7', 'mla_9', 'harvard'].includes(selectedFormat.value)) {
                        const standardRadio = document.querySelector('input[value="standard"]');
                        if (standardRadio) {
                            standardRadio.disabled = true;
                            document.querySelector('label[for="mode_standard"]').classList.add('disabled');
                        }
                    } else if (selectedFormat.value === 'plain_text') {
                        document.querySelectorAll('input[name="humanizer_mode"]').forEach(radio => {
                            if (['essay', 'document_formatter'].includes(radio.value)) {
                                radio.disabled = true;
                                document.querySelector(`label[for="${radio.id}"]`).classList.add('disabled');
                            }
                        });
                    }
                }
                const isDocx = selectedFormat && selectedFormat.value !== 'plain_text';
                DOMElements.toggleReferencesBtn?.classList.toggle('hidden', !isDocx);
                if (!isDocx) DOMElements.referencesSection?.classList.add('hidden');
            },
            resetSelections: () => {
                if (DOMElements.inputText) DOMElements.inputText.value = '';
                if (DOMElements.bibtexInput) DOMElements.bibtexInput.value = '';
                if (DOMElements.referencesSection) DOMElements.referencesSection.classList.add('hidden');
                if (DOMElements.outputDisplay) DOMElements.outputDisplay.innerHTML = '';
                if (DOMElements.outputWordCount) DOMElements.outputWordCount.textContent = '0';
                if (DOMElements.copyBtn) DOMElements.copyBtn.style.display = 'none';
                if (DOMElements.outputPlaceholder) DOMElements.outputPlaceholder.style.display = 'flex';
                typeAnimation.start();
                if (DOMElements.outputSection) DOMElements.outputSection.classList.add('mobile-hidden');
                document.querySelectorAll('input[type="radio"]').forEach(radio => radio.checked = false);
                if(DOMElements.modeDisplay) DOMElements.modeDisplay.textContent = 'Mode';
                if(DOMElements.formatDisplay) DOMElements.formatDisplay.textContent = 'Format';
                if(DOMElements.dialectDisplay) DOMElements.dialectDisplay.textContent = 'Dialect';
                document.querySelectorAll('.popup-trigger').forEach(btn => btn.classList.add('placeholder'));
                UI.updateFormattingOptions();
                UI.updateWordCountAndCost();
            },
            showProcessing: (message) => {
                if (DOMElements.outputPlaceholder) DOMElements.outputPlaceholder.style.display = 'none';
                typeAnimation.stop();
                const loadingHtml = `<div id="loading-spinner" class="loading-in-output"><div class="spinner"></div><span class="mt-2">${message || "Processing..."}</span></div>`;
                if (DOMElements.outputDisplay) DOMElements.outputDisplay.innerHTML = loadingHtml;
                if (DOMElements.humanizeBtn) DOMElements.humanizeBtn.disabled = true;
            },
            hideProcessing: () => { if (DOMElements.humanizeBtn) DOMElements.humanizeBtn.disabled = false; },
            renderOutput: (data) => {
                if (data.download_url) {
                    if (DOMElements.outputDisplay) DOMElements.outputDisplay.innerHTML = `<a href="${data.download_url}" class="download-link">Click here to download your document</a>`;
                } else {
                    if (DOMElements.outputDisplay) DOMElements.outputDisplay.innerHTML = data.humanized_output.replace(/\n/g, '<br>');
                }
                if(DOMElements.outputWordCount) DOMElements.outputWordCount.textContent = data.output_word_count;
                if(DOMElements.copyBtn && !data.download_url) DOMElements.copyBtn.style.display = 'block';
            },
            openAnonymousPaymentModal: () => {
                const words = DOMElements.inputText.value.trim().split(/\s+/).filter(Boolean).length;
                const cost = (words / WORDS_PER_UNIT) * PRICE_PER_UNIT;
                if(document.getElementById('modal_word_count_display')) document.getElementById('modal_word_count_display').textContent = words;
                if(document.getElementById('modal_estimated_cost_display')) document.getElementById('modal_estimated_cost_display').textContent = cost.toFixed(2);
                DOMElements.paymentModal?.classList.remove('hidden');
            },
            closeAnonymousPaymentModal: () => DOMElements.paymentModal?.classList.add('hidden'),
        };

        const Actions = {
            submitHumanization: async () => {
                const formData = new FormData(DOMElements.humanizeForm);
                const words = DOMElements.inputText.value.trim().split(/\s+/).filter(Boolean).length;
                if (words < MIN_WORDS) return UI.showAlert(`Input must be at least ${MIN_WORDS} words.`, 'danger');
                if (!AppState.isLoggedIn) {
                    const phone = DOMElements.phoneInput.value.trim();
                    if (!/^(0|\+254)7[0-9]{8}$/.test(phone)) return UI.showAlert('Invalid phone number.', 'danger');
                    formData.set('phone_number', phone);
                    UI.closeAnonymousPaymentModal();
                }
                UI.showProcessing('Processing request...');
                try {
                    const response = await fetch('/submit-humanize-task', { method: 'POST', body: formData });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.message || 'Error.');
                    AppState.transactionId = data.transaction_id;
                    Actions.startPolling();
                } catch (error) {
                    UI.showAlert(error.message, 'danger');
                    UI.hideProcessing();
                }
            },
            
            // --- SPINNER & CODEBLOCK FIX IS HERE ---
            checkStatus: async () => {
                if (!AppState.transactionId) return;
                try {
                    const response = await fetch(`/get_humanization_status/${AppState.transactionId}`);
                    
                    if (!response.ok) {
                        if (response.status === 404) {
                            AppState.pollingRetries++;
                            if (AppState.pollingRetries > 10) {
                                throw new Error('Task could not be found. Please contact support.');
                            }
                            console.warn(`Task not found yet (attempt ${AppState.pollingRetries}), retrying...`);
                            return;
                        }
                        throw new Error('Server returned an error.');
                    }
                    
                    AppState.pollingRetries = 0;
                    
                    const data = await response.json();

                    if (data.status === 'complete' || data.status === 'download_ready') {
                        Actions.stopPolling();
                        UI.renderOutput(data);
                        if (data.diff_data && data.diff_data.refund_info) {
                            UI.showAlert(data.diff_data.refund_info, 'info');
                        } else {
                            UI.showAlert('Task complete!', 'success');
                        }
                    } else if (data.status === 'humanization_failed') {
                        Actions.stopPolling();
                        UI.resetSelections();
                        UI.showAlert(data.message || 'Processing failed. A full refund has been issued.', 'danger');
                    }
                } catch (error) {
                    Actions.stopPolling();
                    UI.showAlert(error.message || 'Error checking status.', 'danger');
                }
            },
            // --- END OF FIX ---

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
            },
        };

        const setupPopup = (button, popup, display, radios) => {
            if (!button || !popup || !display || !radios) return;
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                document.querySelectorAll('.popup-menu').forEach(p => { if (p !== popup) p.classList.add('hidden'); });
                popup.classList.toggle('hidden');
            });
            radios.forEach(radio => radio.addEventListener('change', () => {
                display.textContent = radio.nextElementSibling.textContent;
                button.classList.remove('placeholder');
                popup.classList.add('hidden');
                UI.updateFormattingOptions();
                UI.updateWordCountAndCost();
            }));
        };

        if (DOMElements.humanizeForm) {
            DOMElements.inputText.oninput = UI.updateWordCountAndCost;
            if (DOMElements.copyBtn) DOMElements.copyBtn.onclick = () => copyToClipboard('humanized_output_display');
            if (DOMElements.resetBtn) DOMElements.resetBtn.onclick = UI.resetSelections;
            if (DOMElements.humanizeBtn) DOMElements.humanizeBtn.onclick = () => AppState.isLoggedIn ? Actions.submitHumanization() : UI.openAnonymousPaymentModal();
            if (DOMElements.submitPaymentBtn) DOMElements.submitPaymentBtn.onclick = Actions.submitHumanization;
            if (DOMElements.closeMpesaModalBtn) DOMElements.closeMpesaModalBtn.onclick = UI.closeAnonymousPaymentModal;
            
            if (DOMElements.toggleReferencesBtn && DOMElements.referencesSection) {
                DOMElements.toggleReferencesBtn.addEventListener('click', function (event) {
                    event.preventDefault();
                    DOMElements.referencesSection.classList.toggle('hidden');
                });
            }

            setupPopup(DOMElements.modeBtn, DOMElements.modePopup, DOMElements.modeDisplay, DOMElements.humanizerModeRadios);
            setupPopup(DOMElements.formatBtn, DOMElements.formatPopup, DOMElements.formatDisplay, DOMElements.outputFormatRadios);
            setupPopup(DOMElements.dialectBtn, DOMElements.dialectPopup, DOMElements.dialectDisplay, DOMElements.englishDialectRadios);
            
            document.body.addEventListener('click', (e) => {
                if (!e.target.closest('.popup-control')) document.querySelectorAll('.popup-menu').forEach(p => p.classList.add('hidden'));
            });

            UI.resetSelections();
            const textToHumanize = localStorage.getItem('textToHumanize');
            if (textToHumanize) {
                DOMElements.inputText.value = textToHumanize;
                UI.updateWordCountAndCost();
                localStorage.removeItem('textToHumanize');
            }
        }
    }
})
