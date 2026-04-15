console.log("[TaskPilot Companion] Background service worker started.");

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STATE MANAGEMENT & SECURITY
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
let isSharing = false;
let sharedTabId = null; // ⭐ The SPECIFIC tab being shared (with green border)
let sharingMode = null; // 'tab', 'window', 'entire-screen'
let sharingStartTime = null;
let avatarOverlayState = {
    visible: false,
    speaking: false,
    listening: false,
    mode: 'avatar'
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// EXTERNAL MESSAGE HANDLER (From Web App)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
chrome.runtime.onMessageExternal.addListener(
    (request, sender, sendResponse) => {
        console.log("[TaskPilot Background] External message:", request);

        if (request.type === "START_SHARING") {
            handleStartSharing(request, sendResponse);
        }
        else if (request.type === "STOP_SHARING") {
            handleStopSharing(sendResponse);
        }
        else if (request.type === "TASKPILOT_ACTION") {
            handleAction(request.payload, request.messageId, sendResponse);
        }

        return true; // Async response
    }
);

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// INTERNAL MESSAGE HANDLER (From Content Scripts)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("[TaskPilot Background] Internal message:", request);

    if (request.type === "START_SHARING") {
        handleStartSharing(request, sendResponse);
    }
    else if (request.type === "STOP_SHARING") {
        handleStopSharing(sendResponse);
    }
    else if (request.type === "TASKPILOT_GET_OVERLAY_STATE") {
        sendResponse({
            success: true,
            isSharing,
            sharingMode,
            avatarState: avatarOverlayState
        });
    }
    else if (request.type === "TASKPILOT_AVATAR_STATE") {
        handleAvatarState(request, sendResponse);
    }
    else if (request.target === "active_tab" && request.actionData) {
        // Action forwarded from content script
        handleAction(request.actionData, request.messageId, sendResponse);
    }

    return true; // Async response
});

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// START SHARING HANDLER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function handleStartSharing(request, sendResponse) {
    isSharing = true;
    sharingMode = request.mode || 'entire-screen';
    sharingStartTime = Date.now();
    avatarOverlayState = {
        visible: true,
        speaking: false,
        listening: true,
        mode: avatarOverlayState.mode || 'avatar'
    };
    
    console.log(`%c🟢 SCREEN SHARING STARTED`, 'background: green; color: white; font-weight: bold; padding: 4px;');
    console.log(`[TaskPilot] Mode: ${sharingMode}`);

    // Get the CURRENT ACTIVE TAB - this is the one being shared (with Chrome's green border)
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length > 0) {
            sharedTabId = tabs[0].id;
            console.log(`%c🎯 SHARED TAB LOCKED: ${sharedTabId}`, 'color: blue; font-weight: bold;');
            console.log(`%c   Actions will execute on THIS tab even when you switch tabs`, 'color: blue;');
            console.log(`%c   Chrome's green border shows which tab is shared`, 'color: green;');
        } else {
            sharedTabId = null;
            console.warn(`[TaskPilot] Warning: Could not detect shared tab`);
        }

        broadcastAvatarState();

        sendResponse({ 
            success: true, 
            mode: sharingMode,
            tabId: sharedTabId 
        });
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STOP SHARING HANDLER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function handleStopSharing(sendResponse) {
    console.log("%c🔴 SCREEN SHARING STOPPED", 'background: red; color: white; font-weight: bold; padding: 4px;');
    console.log("[TaskPilot] Chrome's green border removed automatically");
    
    isSharing = false;
    sharedTabId = null;
    sharingMode = null;
    sharingStartTime = null;
    avatarOverlayState = {
        visible: false,
        speaking: false,
        listening: false,
        mode: avatarOverlayState.mode || 'avatar'
    };
    broadcastAvatarState();

    sendResponse({ success: true });
}

function handleAvatarState(request, sendResponse) {
    if (!isSharing) {
        sendResponse({ success: false, error: 'No active sharing session for avatar state' });
        return;
    }

    avatarOverlayState = {
        visible: typeof request.visible === 'boolean' ? request.visible : avatarOverlayState.visible,
        speaking: typeof request.speaking === 'boolean' ? request.speaking : avatarOverlayState.speaking,
        listening: typeof request.listening === 'boolean' ? request.listening : avatarOverlayState.listening,
        mode: request.mode || avatarOverlayState.mode || 'avatar'
    };

    const payload = {
        action: 'avatar_state',
        ...avatarOverlayState
    };

    chrome.tabs.query({}, (tabs) => {
        let delivered = 0;
        let attempted = 0;

        if (!tabs || tabs.length === 0) {
            sendResponse({ success: false, error: 'No tabs available for avatar state delivery' });
            return;
        }

        tabs.forEach((tab) => {
            if (!tab.id) return;
            attempted += 1;
            chrome.tabs.sendMessage(tab.id, payload, () => {
                if (!chrome.runtime.lastError) {
                    delivered += 1;
                }
            });
        });

        // Respond shortly after fan-out. Some tabs may not host content scripts, which is expected.
        setTimeout(() => {
            sendResponse({ success: delivered > 0, delivered, attempted });
        }, 80);
    });
}

function broadcastAvatarState() {
    const payload = {
        action: 'avatar_state',
        ...avatarOverlayState
    };

    chrome.tabs.query({}, (tabs) => {
        if (!tabs || tabs.length === 0) return;
        tabs.forEach((tab) => {
            if (!tab.id) return;
            chrome.tabs.sendMessage(tab.id, payload, () => {
                // Ignore tabs without content script.
                void chrome.runtime.lastError;
            });
        });
    });
}

function syncAvatarStateToTab(tabId) {
    if (!isSharing || !tabId) return;
    chrome.tabs.sendMessage(
        tabId,
        {
            action: 'avatar_state',
            ...avatarOverlayState
        },
        () => {
            // Ignore tabs without content script.
            void chrome.runtime.lastError;
        }
    );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// ACTION HANDLER (WITH SECURITY)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function handleAction(actionData, messageId, sendResponse) {
    console.log('[TaskPilot Background] handleAction called:', { actionData, messageId, isSharing, sharingMode });
    
    // SECURITY CHECK: Must be sharing
    if (!isSharing) {
        console.warn("[TaskPilot] Action BLOCKED: No screen sharing active");
        sendResponse({ 
            success: false, 
            error: "Screen sharing is not active. Cannot perform action.",
            messageId 
        });
        return;
    }

    // SECURITY CHECK: Minimum duration (prevent accidental immediate actions)
    const MIN_DURATION = 500; // ms
    if (sharingStartTime && Date.now() - sharingStartTime < MIN_DURATION) {
        console.warn("[TaskPilot] Action BLOCKED: Too soon after sharing started");
        sendResponse({ 
            success: false, 
            error: "Please wait before performing actions",
            messageId 
        });
        return;
    }

    // ⭐ Execute on SHARED TAB (not active tab!)
    // This allows user to switch tabs while actions execute on the shared screen
    if (!sharedTabId) {
        console.error("[TaskPilot] Error: No shared tab ID stored");
        sendResponse({ 
            success: false, 
            error: "Shared tab not found",
            messageId 
        });
        return;
    }

    // Get info about current active tab for logging
    chrome.tabs.query({ active: true, currentWindow: true }, (activeTabs) => {
        const activeTabId = activeTabs.length > 0 ? activeTabs[0].id : 'unknown';
        
        console.log(`%c🎯 EXECUTING ON SHARED TAB: ${sharedTabId}`, 'background: blue; color: white; font-weight: bold; padding: 4px;');
        console.log(`%c   (Current active tab: ${activeTabId})`, 'color: gray;');
        console.log(`   Action:`, actionData);

        // Send action to the SHARED tab content script
        chrome.tabs.sendMessage(sharedTabId, actionData, (response) => {
            if (chrome.runtime.lastError) {
                console.error("[TaskPilot] Action failed:", chrome.runtime.lastError);
                sendResponse({ 
                    success: false, 
                    error: chrome.runtime.lastError.message || "Shared tab not accessible",
                    messageId 
                });
            } else {
                console.log(`%c✅ ACTION COMPLETED on shared tab ${sharedTabId}`, 'color: green; font-weight: bold;');
                sendResponse({ 
                    success: true, 
                    response,
                    messageId 
                });
            }
        });
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB CHANGE TRACKING
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Chrome's native green border stays on the shared tab automatically!
// We just log for debugging purposes

chrome.tabs.onActivated.addListener((activeInfo) => {
    if (!isSharing) return;
    
    if (activeInfo.tabId === sharedTabId) {
        console.log(`%c📍 Switched to SHARED tab (${sharedTabId})`, 'color: green;');
    } else {
        console.log(`%c📍 Switched to tab ${activeInfo.tabId}`, 'color: gray;');
        console.log(`%c   Green border stays on shared tab ${sharedTabId}`, 'color: green;');
        console.log(`%c   Actions will still execute on shared tab`, 'color: blue;');
    }

    // Keep avatar persistent on any currently viewed tab during sharing.
    syncAvatarStateToTab(activeInfo.tabId);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
    if (!isSharing) return;
    if (changeInfo.status === 'complete') {
        syncAvatarStateToTab(tabId);
    }
});

chrome.tabs.onCreated.addListener((tab) => {
    if (!isSharing || !tab.id) return;
    // New tabs opened during sharing should also inherit current avatar state.
    syncAvatarStateToTab(tab.id);
});

// Track if shared tab is closed
chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
    if (tabId === sharedTabId) {
        console.warn(`%c⚠️ SHARED TAB CLOSED`, 'background: orange; color: white; font-weight: bold; padding: 4px;');
        console.log('[TaskPilot] Stopping sharing session');
        isSharing = false;
        sharedTabId = null;
        sharingMode = null;
        sharingStartTime = null;
    }
});
