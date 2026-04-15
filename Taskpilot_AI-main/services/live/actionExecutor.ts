
/**
 * Action Executor Agent
 * Executes safe browser actions commands from Gemini Live.
 * 
 * SUPPORTS TWO MODES:
 * 1. Chrome Extension (default) - Works in current browser
 * 2. Playwright WebSocket - Cross-browser (Chrome/Edge/Firefox)
 * 
 * SECURITY: All actions are validated against screen sharing state.
 * Actions are ONLY executed when screen sharing is active.
 */

import { screenContext } from './screenContext';
import playwrightService from '../playwrightService';
import type { ScreenAction } from './geminiActionParser';

type ScrollDirection = 'up' | 'down';
type ExecutionMode = 'extension' | 'playwright';

interface ActionResult {
    success: boolean;
    message?: string;
    data?: any;
}

export class ActionExecutor {
    private scrollInterval: number | null = null;
    private waitTimeout: number | null = null;
    private actionHistory: ScreenAction[] = [];
    private maxHistorySize: number = 20;
    private executionMode: ExecutionMode = 'extension'; // Default to extension

    /**
     * Set execution mode: 'extension' or 'playwright'
     */
    public setExecutionMode(mode: ExecutionMode): void {
        this.executionMode = mode;
        console.log(`%c🔧 Action execution mode: ${mode}`, 'color: blue; font-weight: bold;');
    }

    /**
     * Get current execution mode
     */
    public getExecutionMode(): ExecutionMode {
        return this.executionMode;
    }

    /**
     * Security check before executing any action
     */
    private canExecute(): boolean {
        if (!screenContext.canPerformAction()) {
            console.error('[ActionExecutor] BLOCKED: Screen sharing not active');
            return false;
        }
        return true;
    }

    /**
     * Helper to send actions - routes to either Extension or Playwright
     */
    private sendAction(action: string, data: any): Promise<ActionResult> {
        if (this.executionMode === 'playwright') {
            return this.sendActionPlaywright(action, data);
        } else {
            return this.sendActionExtension(action, data);
        }
    }

    /**
     * Send action via Playwright WebSocket
     */
    private async sendActionPlaywright(action: string, data: any): Promise<ActionResult> {
        if (!this.canExecute()) {
            return {
                success: false,
                message: 'Screen sharing is not active. Please start screen sharing first.'
            };
        }

        if (!playwrightService.isConnected()) {
            console.warn('[ActionExecutor] ⚠️ Playwright not connected');
            return {
                success: false,
                message: 'Playwright not connected. Using extension mode or start Playwright backend.'
            };
        }

        try {
            const playwrightAction: any = {
                action: this.mapActionToPlaywright(action),
                current_url: window.location.href // 🎯 Send current URL to mirror
            };

            // Map data fields
            if (data.target) playwrightAction.selector = data.target;
            if (data.text) playwrightAction.text = data.text;
            if (data.direction) playwrightAction.direction = data.direction;
            if (data.amount) playwrightAction.amount = data.amount;

            console.log(`%c🎯 [Playwright] ${action}`, 'color: purple;', playwrightAction);
            console.log(`%c🔄 Mirroring URL: ${window.location.href}`, 'color: blue;');

            const response = await playwrightService.executeAction(playwrightAction);

            // 📸 Show screenshot if available
            if (response.data?.screenshot) {
                console.log('%c📸 Screenshot received from mirrored browser', 'color: green;');
                // Optionally display screenshot in UI
            }

            return {
                success: response.success,
                message: response.message,
                data: response.data
            };

        } catch (error) {
            console.error('[ActionExecutor] Playwright action failed:', error);
            return {
                success: false,
                message: error instanceof Error ? error.message : 'Playwright action failed'
            };
        }
    }

    /**
     * Map extension action names to Playwright action names
     */
    private mapActionToPlaywright(action: string): string {
        const mapping: Record<string, string> = {
            'scroll': 'scroll',
            'type_text': 'type',
            'click': 'click',
            'focus_element': 'click', // Focus by clicking
            'read': 'get_text'
        };
        return mapping[action] || action;
    }

    /**
     * Send action via Chrome Extension (original method)
     */
    private sendActionExtension(action: string, data: any): Promise<ActionResult> {
        // Check extension is loaded
        if (!screenContext.isExtensionLoaded()) {
            console.warn('[ActionExecutor] ⚠️ Chrome Extension not detected - action cannot be executed');
            return Promise.resolve({
                success: false,
                message: `Action "${action}" cannot be executed. The browser extension is optional but required for click/type/scroll commands. Vision and conversation features work without it.`
            });
        }

        if (!this.canExecute()) {
            return Promise.resolve({
                success: false,
                message: 'Screen sharing is not active. Please start screen sharing first.'
            });
        }

        // Get shared tab ID to target the correct screen
        const sharedTabId = screenContext.getSharedTabId();

        return new Promise((resolve) => {
            const messageId = `action_${Date.now()}_${Math.random()}`;
            
            console.log(`[ActionExecutor] 📤 Sending action: ${action}`, { ...data, targetTabId: sharedTabId });
            
            // Listen for response
            const handleResponse = (event: MessageEvent) => {
                if (event.data.type === 'TASKPILOT_ACTION_RESPONSE' && event.data.messageId === messageId) {
                    window.removeEventListener('message', handleResponse);
                    console.log(`[ActionExecutor] ✅ Action "${action}" completed on shared screen:`, event.data);
                    resolve({
                        success: event.data.success,
                        message: event.data.message,
                        data: event.data.data
                    });
                }
            };

            window.addEventListener('message', handleResponse);

            // Timeout after 5 seconds
            setTimeout(() => {
                window.removeEventListener('message', handleResponse);
                console.error(`[ActionExecutor] ⏱️ Timeout waiting for "${action}" response`);
                resolve({
                    success: false,
                    message: `Action "${action}" timeout - extension may not be responding. Check browser console for errors.`
                });
            }, 5000);

            // Send action to extension with shared tab ID
            window.postMessage({
                type: "TASKPILOT_ACTION",
                messageId,
                targetTabId: sharedTabId, // ⭐ Target the shared screen, not active tab
                payload: { action, ...data }
            }, "*");
        });
    }

    /**
     * Execute a structured action from Gemini parser
     */
    async executeAction(action: ScreenAction): Promise<ActionResult> {
        // Record action in history
        this.actionHistory.push(action);
        if (this.actionHistory.length > this.maxHistorySize) {
            this.actionHistory.shift();
        }

        console.log('[ActionExecutor] Executing action:', action);

        switch (action.type) {
            case 'CLICK':
                return this.click(action.target || action.selector || '');
            
            case 'TYPE':
                return this.typeText(action.text || '');
            
            case 'SCROLL':
                return this.scroll(action.direction || 'down', action.amount || 300);
            
            case 'READ':
                const text = await this.getVisibleText();
                return { success: true, message: 'Page content read', data: text };
            
            case 'WAIT':
                await this.wait(action.duration || 1000);
                return { success: true, message: `Waited ${action.duration}ms` };
            
            case 'FOCUS':
                return this.focusElement(action.target || '');
            
            case 'NONE':
                return { success: true, message: 'No action required' };
            
            default:
                return { success: false, message: `Unknown action type: ${action.type}` };
        }
    }

    /**
     * Get action history for context
     */
    getActionHistory(): ScreenAction[] {
        return [...this.actionHistory];
    }

    /**
     * Clear action history
     */
    clearHistory(): void {
        this.actionHistory = [];
    }

    /**
     * Scroll the window in a direction.
     * Quantity can be 'page' or a number of pixels.
     */
    public async scroll(direction: ScrollDirection, quantity: 'page' | number = 'page'): Promise<ActionResult> {
        console.log(`[ActionExecutor] Scrolling ${direction} by ${quantity}`);
        const amount = quantity === 'page' ? 800 : quantity;
        return this.sendAction("scroll", { direction, amount });
    }

    /**
     * Start auto-scrolling at a set interval.
     */
    public startAutoScroll(intervalMs: number = 2000): void {
        if (!this.canExecute()) return;

        this.stop(); // Clear existing
        console.log(`[ActionExecutor] Starting auto-scroll every ${intervalMs}ms`);

        this.scroll('down', 100); // Initial nudge

        this.scrollInterval = window.setInterval(() => {
            this.scroll('down', 300);
        }, intervalMs);
    }

    /**
     * Type text into the active element.
     */
    public async typeText(text: string): Promise<ActionResult> {
        console.log(`[ActionExecutor] Typing text: "${text}"`);
        return this.sendAction("type_text", { text });
    }

    /**
     * Focus on an element (input field, textarea, etc)
     */
    public async focusElement(target: string): Promise<ActionResult> {
        console.log(`[ActionExecutor] Focusing element: "${target}"`);
        return this.sendAction("focus_element", { target });
    }

    /**
     * Wait for a duration
     */
    public wait(durationMs: number): Promise<void> {
        console.log(`[ActionExecutor] Waiting ${durationMs}ms`);
        return new Promise(resolve => {
            this.waitTimeout = window.setTimeout(resolve, durationMs);
        });
    }

    /**
     * Stop all ongoing actions (scrolling, waiting).
     */
    public stop(): void {
        console.log('[ActionExecutor] Stopping all actions');
        if (this.scrollInterval) {
            clearInterval(this.scrollInterval);
            this.scrollInterval = null;
        }
        if (this.waitTimeout) {
            clearTimeout(this.waitTimeout);
            this.waitTimeout = null;
        }
    }

    /**
     * Click an element on the shared screen.
     */
    public async click(target: string): Promise<ActionResult> {
        console.log(`[ActionExecutor] Clicking: "${target}"`);
        return this.sendAction("click", { target });
    }

    /**
     * Read visible text from the shared screen.
     * Returns a Promise that resolves with the text.
     */
    public async getVisibleText(): Promise<string> {
        if (!this.canExecute()) {
            return 'Screen sharing is not active. Cannot read page content.';
        }

        return new Promise((resolve) => {
            const messageId = `read_${Date.now()}`;
            const timeout = setTimeout(() => {
                window.removeEventListener("message", handleResponse);
                resolve("Timeout: Could not read page content");
            }, 5000);

            const handleResponse = (event: MessageEvent) => {
                if (event.data.type === "TASKPILOT_ACTION_RESPONSE" && 
                    event.data.messageId === messageId) {
                    clearTimeout(timeout);
                    window.removeEventListener("message", handleResponse);
                    resolve(event.data.data?.text || event.data.data || "");
                }
            };

            window.addEventListener("message", handleResponse);

            window.postMessage({
                type: "TASKPILOT_ACTION",
                messageId,
                payload: { action: "read" }
            }, "*");
        });
    }

    /**
     * Get page metadata (title, URL, etc)
     */
    public async getPageInfo(): Promise<{ title: string; url: string; text: string }> {
        if (!this.canExecute()) {
            return { title: '', url: '', text: 'Screen sharing not active' };
        }

        return new Promise((resolve) => {
            const messageId = `info_${Date.now()}`;
            const timeout = setTimeout(() => {
                window.removeEventListener("message", handleResponse);
                resolve({ title: '', url: '', text: '' });
            }, 5000);

            const handleResponse = (event: MessageEvent) => {
                if (event.data.type === "TASKPILOT_ACTION_RESPONSE" && 
                    event.data.messageId === messageId) {
                    clearTimeout(timeout);
                    window.removeEventListener("message", handleResponse);
                    resolve(event.data.data || { title: '', url: '', text: '' });
                }
            };

            window.addEventListener("message", handleResponse);

            window.postMessage({
                type: "TASKPILOT_ACTION",
                messageId,
                payload: { action: "read" }
            }, "*");
        });
    }
}

// Singleton instance
export const actionExecutor = new ActionExecutor();

