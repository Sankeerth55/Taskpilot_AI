console.log("[TaskPilot Companion] Content script loaded.");

// --- State Management ---
let isSharingActive = false;
let sharingMode = null;
let avatarState = {
    visible: false,
    speaking: false,
    listening: false,
    mode: 'avatar'
};

// --- Announce Extension is Ready ---
// This lets the webapp know the extension is installed and active
function announceExtension() {
    window.postMessage({
        type: 'TASKPILOT_EXTENSION_READY',
        extensionId: chrome.runtime.id,
        timestamp: Date.now()
    }, '*');
    console.log('[TaskPilot Extension] Announced presence to webpage');
}

// Announce immediately
announceExtension();

// Listen for check requests from webapp and re-announce
window.addEventListener('message', (event) => {
    if (event.source === window && event.data.type === 'TASKPILOT_CHECK_EXTENSION') {
        console.log('[TaskPilot Extension] Received check request, re-announcing...');
        announceExtension();
    }
});

// --- Inject Overlay ---
function ensureOverlay() {
    if (!document.getElementById('taskpilot-overlay')) {
        const overlay = document.createElement('div');
        overlay.id = 'taskpilot-overlay';
        overlay.innerHTML = `
            <div id="taskpilot-badge">
                <span id="taskpilot-badge-icon">🎯</span>
                <span id="taskpilot-badge-text">TaskPilot AI Active</span>
            </div>
            <div id="taskpilot-avatar" class="taskpilot-avatar-hidden" aria-hidden="true">
                <div id="taskpilot-avatar-shell">
                    <div id="taskpilot-avatar-highlight"></div>
                    <div id="taskpilot-avatar-face">
                        <span id="taskpilot-avatar-text">LIVE<br>AI</span>
                        <div id="taskpilot-avatar-glow"></div>
                    </div>
                    <div id="taskpilot-avatar-seam"></div>
                    <div id="taskpilot-avatar-arm-left"></div>
                    <div id="taskpilot-avatar-arm-right"></div>
                </div>
                <div id="taskpilot-avatar-pulse"></div>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }
    return document.getElementById('taskpilot-overlay');
}

function renderAvatarState() {
    const overlay = ensureOverlay();
    const avatar = document.getElementById('taskpilot-avatar');
    if (!avatar || !overlay) return;

    if (!avatarState.visible) {
        avatar.className = 'taskpilot-avatar-hidden';
        overlay.classList.remove('taskpilot-avatar-only');
        if (!isSharingActive) {
            overlay.style.display = 'none';
        }
        return;
    }

    // Avatar should remain visible across shared tabs/windows even when border mode is not toggled.
    overlay.style.display = 'block';
    overlay.classList.add('taskpilot-avatar-only');
    isSharingActive = true;

    if (avatarState.speaking) {
        avatar.className = 'taskpilot-avatar-speaking';
    } else if (avatarState.listening) {
        avatar.className = 'taskpilot-avatar-listening';
    } else {
        avatar.className = 'taskpilot-avatar-idle';
    }
}

// Initial injection
ensureOverlay();

// Sync current sharing/avatar state when content script loads late.
chrome.runtime.sendMessage({ type: 'TASKPILOT_GET_OVERLAY_STATE' }, (response) => {
    if (chrome.runtime.lastError || !response?.success) return;

    if (response.isSharing) {
        actions.toggle_border(true, response.sharingMode || 'Entire Screen');
    }

    if (response.avatarState) {
        actions.avatar_state(response.avatarState);
    }
});

// --- Security: Check if actions are allowed ---
function canPerformAction() {
    if (!isSharingActive) {
        console.warn('[TaskPilot] Action blocked: Screen sharing not active');
        return false;
    }
    return true;
}

// --- Action Handlers ---
const actions = {
    toggle_border: (visible, mode = 'Entire Screen') => {
        const overlay = ensureOverlay();
        const badge = document.getElementById('taskpilot-badge-text');
        
        if (overlay) {
            overlay.style.display = visible ? 'block' : 'none';
            overlay.classList.remove('taskpilot-avatar-only');
            isSharingActive = visible;
            sharingMode = mode;
            
            if (badge) {
                badge.textContent = visible ? `TaskPilot Controlling: ${mode}` : 'TaskPilot AI Active';
            }

            if (!visible) {
                avatarState.visible = false;
                avatarState.speaking = false;
                avatarState.listening = false;
            }
            renderAvatarState();
            
            console.log(`[TaskPilot] Border ${visible ? 'SHOWN' : 'HIDDEN'}, Mode: ${mode}`);
        }
    },

    avatar_state: ({ visible, speaking, listening, mode }) => {
        if (typeof visible === 'boolean') avatarState.visible = visible;
        if (typeof speaking === 'boolean') avatarState.speaking = speaking;
        if (typeof listening === 'boolean') avatarState.listening = listening;
        if (typeof mode === 'string') avatarState.mode = mode;

        renderAvatarState();
        return { success: true, avatarState: { ...avatarState } };
    },

    scroll: ({ direction, amount }) => {
        if (!canPerformAction()) return { success: false, error: 'Not authorized' };
        
        const y = direction === 'up' ? -amount : amount;
        window.scrollBy({ top: y, behavior: 'smooth' });
        return { success: true, scrolled: y };
    },

    type_text: ({ text }) => {
        if (!canPerformAction()) return { success: false, error: 'Not authorized' };
        
        const activeElement = document.activeElement;
        if (activeElement && (activeElement.tagName === 'INPUT' || 
            activeElement.tagName === 'TEXTAREA' || 
            activeElement.isContentEditable)) {
            
            if (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA') {
                const start = activeElement.selectionStart || 0;
                const end = activeElement.selectionEnd || 0;
                const value = activeElement.value;
                activeElement.value = value.substring(0, start) + text + value.substring(end);
                activeElement.selectionStart = activeElement.selectionEnd = start + text.length;
                
                // Trigger input event for React/Vue forms
                activeElement.dispatchEvent(new Event('input', { bubbles: true }));
            } else {
                document.execCommand('insertText', false, text);
            }
            
            console.log(`[TaskPilot] Typed: "${text}"`);
            return { success: true, text };
        } else {
            console.warn("[TaskPilot] No active input field found.");
            return { success: false, error: 'No active input field' };
        }
    },

    focus_element: ({ target }) => {
        if (!canPerformAction()) return { success: false, error: 'Not authorized' };
        
        try {
            // Try as selector first
            let el = document.querySelector(target);
            
            // Try finding by label text
            if (!el) {
                const labels = document.querySelectorAll('label');
                for (let label of labels) {
                    if (label.innerText.toLowerCase().includes(target.toLowerCase())) {
                        const forId = label.getAttribute('for');
                        if (forId) {
                            el = document.getElementById(forId);
                            break;
                        }
                    }
                }
            }
            
            // Try finding input by placeholder
            if (!el) {
                el = document.querySelector(`input[placeholder*="${target}" i], textarea[placeholder*="${target}" i]`);
            }
            
            if (el) {
                el.focus();
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                console.log(`[TaskPilot] Focused: ${target}`);
                return { success: true, target };
            }
            
            return { success: false, error: 'Element not found' };
        } catch (e) {
            console.error('[TaskPilot] Focus error:', e);
            return { success: false, error: e.message };
        }
    },

    click: ({ target }) => {
        if (!canPerformAction()) return { success: false, error: 'Not authorized' };
        
        console.log(`[TaskPilot] Attempting to click: "${target}"`);

        // 1. Try as CSS selector
        try {
            const el = document.querySelector(target);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => {
                    el.click();
                    el.focus();
                }, 300);
                return { success: true, target, method: 'selector' };
            }
        } catch (e) { /* Invalid selector */ }

        // 2. Try by Text Content (Buttons, Links, etc.)
        const clickableElements = document.querySelectorAll(
            'button, a, input[type="button"], input[type="submit"], ' +
            'div[role="button"], span[role="button"], [onclick]'
        );
        
        for (let el of clickableElements) {
            const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').toLowerCase();
            if (text.includes(target.toLowerCase())) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => {
                    el.click();
                    el.focus();
                }, 300);
                return { success: true, target, method: 'text', found: el.innerText || el.value };
            }
        }

        return { success: false, error: 'Element not found' };
    },

    read: () => {
        if (!canPerformAction()) return { success: false, error: 'Not authorized' };
        
        // Extract visible text and metadata
        return {
            success: true,
            data: {
                text: document.body.innerText.substring(0, 10000),
                title: document.title,
                url: window.location.href,
                timestamp: Date.now()
            }
        };
    }
};

// --- Message Listener (From Background or Webpage) ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("[TaskPilot Content] Received action:", request);

    const action = request.action;
    let result;

    switch (action) {
        case "toggle_border":
            actions.toggle_border(request.visible, request.mode);
            sendResponse({ success: true });
            break;
            
        case "scroll":
            result = actions.scroll(request);
            sendResponse(result);
            break;
            
        case "type_text":
            result = actions.type_text(request);
            sendResponse(result);
            break;
            
        case "focus_element":
            result = actions.focus_element(request);
            sendResponse(result);
            break;
            
        case "click":
            result = actions.click(request);
            sendResponse(result);
            break;
            
        case "read":
            result = actions.read();
            sendResponse(result);
            break;

        case "avatar_state":
            result = actions.avatar_state(request);
            sendResponse(result);
            break;
            
        default:
            sendResponse({ success: false, error: `Unknown action: ${action}` });
    }

    return true; // Keep channel open for async responses
});

// --- Message Listener (From Web App via Window) ---
// This allows the React app (localhost) to send messages to this content script,
// which then forwards them to the background script.
window.addEventListener("message", (event) => {
    // Security check: only allow messages from same window
    if (event.source !== window) return;

    if (event.data.type && event.data.type === "TASKPILOT_ACTION") {
        const messageId = event.data.messageId;
        console.log("[TaskPilot Content Relay] Relaying action to background:", event.data.payload);

        // Send to background service worker
        chrome.runtime.sendMessage({
            target: "active_tab",
            actionData: event.data.payload,
            messageId: messageId
        }, (response) => {
            console.log("[TaskPilot Content Relay] Response from background:", response);

            // Relay response back to Window with messageId for proper routing
            window.postMessage({
                type: "TASKPILOT_ACTION_RESPONSE",
                messageId: messageId,
                success: response?.success !== false,
                message: response?.message || '',
                data: response?.response || response?.data || null,
                error: response?.error || null
            }, "*");
        });
    }

    // Relay START_SHARING / STOP_SHARING
    if (event.data.type === "START_SHARING" || event.data.type === "STOP_SHARING" || event.data.type === "TASKPILOT_AVATAR_STATE") {
        console.log(`[TaskPilot Content Relay] Relaying sharing state: ${event.data.type}`);
        chrome.runtime.sendMessage(event.data);
    }
});
