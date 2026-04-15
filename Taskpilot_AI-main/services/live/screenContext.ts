
/**
 * Screen Context Manager
 * Handles the state of screen sharing and visual feedback (Green Border).
 * 
 * SECURITY: Enforces that actions only occur when screen sharing is active.
 */

export type SharingMode = 'entire-screen' | 'window' | 'tab' | null;

export interface ScreenState {
    isSharing: boolean;
    mode: SharingMode;
    tabId?: string;
    startedAt?: number;
}

export interface SharedAvatarState {
    visible: boolean;
    speaking?: boolean;
    listening?: boolean;
    mode?: 'avatar' | 'voice';
}

type StateCallback = (state: ScreenState) => void;

class ScreenContextManager {
    private state: ScreenState = {
        isSharing: false,
        mode: null
    };
    private listeners: StateCallback[] = [];
    private extensionId: string | null = null;

    constructor() {
        this.state = {
            isSharing: false,
            mode: null
        };

        // Listen for messages from the extension
        window.addEventListener('message', (event) => {
            if (event.data.type === 'TASKPILOT_EXTENSION_READY') {
                this.extensionId = event.data.extensionId;
                console.log('%c✅ EXTENSION DETECTED!', 'color: green; font-weight: bold; font-size: 14px');
                console.log('[ScreenContext] TaskPilot Extension loaded:', this.extensionId);
                console.log('%c🎉 Voice commands (click/type/scroll) will now work!', 'color: green; font-size: 12px');
            }
        });

        // Ping extension after a short delay (in case content script loads after this)
        setTimeout(() => {
            if (!this.extensionId) {
                console.log('%c⚠️ WARNING: Extension not detected yet', 'color: orange; font-weight: bold; font-size: 14px');
                console.log('%c📦 Load extension at chrome://extensions/ to enable click/type/scroll actions', 'color: orange; font-size: 12px');
                console.log('[ScreenContext] 🔍 Checking for extension...');
                // Request extension to announce itself
                window.postMessage({ type: 'TASKPILOT_CHECK_EXTENSION' }, '*');
            }
        }, 1000);
    }

    /**
     * Check if the Chrome extension is installed and loaded
     */
    public isExtensionLoaded(): boolean {
        return this.extensionId !== null;
    }

    /**
     * Get the extension ID (null if not connected)
     */
    public getExtensionId(): string | null {
        return this.extensionId;
    }

    /**
     * Start screen sharing with a specific mode
     */
    public startSharing(mode: SharingMode = 'entire-screen', tabId?: string): void {
        this.state = {
            isSharing: true,
            mode,
            tabId,
            startedAt: Date.now()
        };

        console.log(`[ScreenContext] 🟢 Chrome green border active on ${mode}`, tabId ? `(ID: ${tabId})` : '');
        console.log('[ScreenContext] ✅ Actions will execute on SHARED screen, not active tab');
        
        this.notifyListeners();
        this.notifyExtension('START_SHARING', { mode, tabId });
    }

    /**
     * Stop screen sharing and clear all permissions
     */
    public stopSharing(): void {
        const wasSharing = this.state.isSharing;

        this.state = {
            isSharing: false,
            mode: null,
            tabId: undefined,
            startedAt: undefined
        };

        if (wasSharing) {
            console.log('[ScreenContext] Sharing stopped - All permissions cleared');
            this.setAvatarState({ visible: false, speaking: false, listening: false, mode: 'avatar' });
            this.notifyListeners();
            this.notifyExtension('STOP_SHARING', {});
        }
    }

    /**
     * Update the shared-screen avatar state in extension overlay.
     */
    public setAvatarState(avatarState: SharedAvatarState): void {
        this.notifyExtension('TASKPILOT_AVATAR_STATE', avatarState);
    }

    /**
     * Legacy: Set sharing state (for backward compatibility)
     */
    public setSharing(sharing: boolean): void {
        if (sharing && !this.state.isSharing) {
            this.startSharing('entire-screen');
        } else if (!sharing && this.state.isSharing) {
            this.stopSharing();
        }
    }

    /**
     * Get current sharing state
     */
    public getState(): ScreenState {
        return { ...this.state };
    }

    /**
     * Check if sharing is active
     */
    public getIsSharing(): boolean {
        return this.state.isSharing;
    }

    /**
     * Get the current sharing mode
     */
    public getMode(): SharingMode {
        return this.state.mode;
    }

    /**
     * Get the shared tab/window ID
     */
    public getSharedTabId(): string | undefined {
        return this.state.tabId;
    }

    /**
     * Get a human-readable label for what's being shared
     */
    public getSharingLabel(): string {
        if (!this.state.isSharing) return 'Not Sharing';
        
        switch (this.state.mode) {
            case 'tab':
                return 'This Tab';
            case 'window':
                return 'This Window';
            case 'entire-screen':
                return 'Entire Screen';
            default:
                return 'Screen Sharing Active';
        }
    }

    /**
     * Validate if an action can be performed (security check)
     */
    public canPerformAction(): boolean {
        if (!this.state.isSharing) {
            console.warn('[ScreenContext] Action blocked: Screen sharing not active');
            return false;
        }

        // Optional: Check if sharing has been active for a minimum duration
        // to prevent accidental actions immediately after starting
        const MIN_DURATION = 500; // ms
        if (this.state.startedAt && Date.now() - this.state.startedAt < MIN_DURATION) {
            console.warn('[ScreenContext] Action blocked: Too soon after sharing started');
            return false;
        }

        return true;
    }

    /**
     * Subscribe to state changes (used by React components)
     */
    public subscribe(callback: StateCallback): () => void {
        this.listeners.push(callback);
        // Initial call with current state
        callback(this.state);

        return () => {
            this.listeners = this.listeners.filter(l => l !== callback);
        };
    }

    /**
     * Notify all listeners of state change
     */
    private notifyListeners(): void {
        this.listeners.forEach(cb => cb(this.state));
    }

    /**
     * Send message to browser extension
     */
    private notifyExtension(type: string, data: any): void {
        try {
            window.postMessage({
                type,
                source: 'taskpilot-webapp',
                ...data
            }, "*");

            // Also try Chrome extension messaging if available
            if (typeof chrome !== 'undefined' && chrome.runtime) {
                chrome.runtime.sendMessage(this.extensionId || '', {
                    type,
                    ...data
                }).catch(() => {
                    // Extension might not be installed, which is fine
                });
            }
        } catch (error) {
            console.warn('[ScreenContext] Could not notify extension:', error);
        }
    }
}

export const screenContext = new ScreenContextManager();
