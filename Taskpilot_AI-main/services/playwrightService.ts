/**
 * Playwright WebSocket Service
 * Connects to backend Playwright executor for cross-browser action execution
 * Supports Chrome, Edge, and any browser with green border
 */

interface PlaywrightAction {
    action: 'click' | 'type' | 'scroll' | 'enter' | 'search' | 'navigate' | 'get_text' | 'screenshot';
    selector?: string;
    target?: string;
    text?: string;
    direction?: 'up' | 'down';
    amount?: number;
    url?: string;
}

interface PlaywrightMessage {
    type: 'START' | 'STOP' | 'ACTION' | 'SET_SHARED_TAB' | 'PING';
    browser?: 'chrome' | 'edge' | 'firefox';
    cdpUrl?: string;
    tabId?: string;
    pageIndex?: number;
    action?: PlaywrightAction;
}

interface PlaywrightResponse {
    type: string;
    success: boolean;
    message?: string;
    data?: any;
    tabId?: string;
    browser?: string;
    sharedTabId?: string;
    connected?: boolean;
}

type ResponseCallback = (response: PlaywrightResponse) => void;

class PlaywrightService {
    private ws: WebSocket | null = null;
    private messageQueue: PlaywrightMessage[] = [];
    private responseCallbacks: Map<string, ResponseCallback> = new Map();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 2000;
    private isConnecting = false;
    private sharedTabId: string | null = null;
    
    constructor(private wsUrl: string = 'ws://localhost:8000/api/ws/actions') {}
    
    /**
     * Connect to Playwright WebSocket server
     */
    async connect(): Promise<boolean> {
        if (this.ws?.readyState === WebSocket.OPEN) {
            console.log('[Playwright] Already connected');
            return true;
        }
        
        if (this.isConnecting) {
            console.log('[Playwright] Connection in progress...');
            return false;
        }
        
        this.isConnecting = true;
        
        return new Promise((resolve) => {
            console.log('%c🔌 Connecting to Playwright WebSocket...', 'color: blue; font-weight: bold;');
            
            try {
                this.ws = new WebSocket(this.wsUrl);
                
                this.ws.onopen = () => {
                    console.log('%c✅ Playwright WebSocket connected!', 'color: green; font-weight: bold;');
                    this.isConnecting = false;
                    this.reconnectAttempts = 0;
                    
                    // Send queued messages
                    this.flushMessageQueue();
                    
                    resolve(true);
                };
                
                this.ws.onmessage = (event) => {
                    try {
                        const response: PlaywrightResponse = JSON.parse(event.data);
                        console.log('[Playwright] Response:', response);
                        
                        // Call response callback if exists
                        const callback = this.responseCallbacks.get(response.type);
                        if (callback) {
                            callback(response);
                        }
                    } catch (e) {
                        console.error('[Playwright] Failed to parse response:', e);
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('[Playwright] WebSocket error:', error);
                    this.isConnecting = false;
                    resolve(false);
                };
                
                this.ws.onclose = () => {
                    console.warn('%c🔌 Playwright WebSocket disconnected', 'color: orange;');
                    this.isConnecting = false;
                    this.ws = null;
                    
                    // Attempt reconnect
                    if (this.reconnectAttempts < this.maxReconnectAttempts) {
                        this.reconnectAttempts++;
                        console.log(`[Playwright] Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                        setTimeout(() => this.connect(), this.reconnectDelay);
                    }
                };
                
            } catch (error) {
                console.error('[Playwright] Failed to create WebSocket:', error);
                this.isConnecting = false;
                resolve(false);
            }
        });
    }
    
    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    
    /**
     * Send message to Playwright server
     */
    private sendMessage(message: PlaywrightMessage): Promise<PlaywrightResponse> {
        return new Promise((resolve, reject) => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                console.warn('[Playwright] WebSocket not ready, queueing message');
                this.messageQueue.push(message);
                reject(new Error('WebSocket not connected'));
                return;
            }
            
            try {
                // Set up response callback
                const responseType = `${message.type}_RESPONSE`;
                this.responseCallbacks.set(responseType, (response) => {
                    this.responseCallbacks.delete(responseType);
                    resolve(response);
                });
                
                // Send message
                this.ws.send(JSON.stringify(message));
                
                // Timeout after 10s
                setTimeout(() => {
                    if (this.responseCallbacks.has(responseType)) {
                        this.responseCallbacks.delete(responseType);
                        reject(new Error('Request timeout'));
                    }
                }, 10000);
                
            } catch (error) {
                reject(error);
            }
        });
    }
    
    /**
     * Flush queued messages
     */
    private flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            if (message) {
                this.sendMessage(message).catch(console.error);
            }
        }
    }
    
    /**
     * Start Playwright and connect to browser
     */
    async startBrowser(browser: 'chrome' | 'edge' | 'firefox' = 'chrome', cdpUrl?: string): Promise<PlaywrightResponse> {
        console.log(`%c🚀 Starting ${browser} browser...`, 'color: blue; font-weight: bold;');
        
        return this.sendMessage({
            type: 'START',
            browser,
            cdpUrl
        });
    }
    
    /**
     * Stop Playwright
     */
    async stopBrowser(): Promise<PlaywrightResponse> {
        console.log('%c🔴 Stopping browser...', 'color: red; font-weight: bold;');
        
        return this.sendMessage({
            type: 'STOP'
        });
    }
    
    /**
     * Set which tab is the shared screen (the one with green border)
     */
    async setSharedTab(tabId: string, pageIndex: number = 0): Promise<PlaywrightResponse> {
        console.log(`%c🎯 Setting shared tab: ${tabId}`, 'color: blue; font-weight: bold;');
        this.sharedTabId = tabId;
        
        return this.sendMessage({
            type: 'SET_SHARED_TAB',
            tabId,
            pageIndex
        });
    }
    
    /**
     * Execute action on shared screen (not active tab!)
     */
    async executeAction(action: PlaywrightAction): Promise<PlaywrightResponse> {
        console.log(`%c🎯 Executing '${action.action}' on SHARED SCREEN`, 'color: blue; font-weight: bold;');
        
        return this.sendMessage({
            type: 'ACTION',
            tabId: this.sharedTabId || undefined,
            action
        });
    }
    
    /**
     * Ping server to check connection
     */
    async ping(): Promise<PlaywrightResponse> {
        return this.sendMessage({
            type: 'PING'
        });
    }
    
    /**
     * Check if connected
     */
    isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }
}

// Global instance
export const playwrightService = new PlaywrightService();

export default playwrightService;
