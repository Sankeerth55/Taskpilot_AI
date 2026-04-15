/**
 * Gemini Screen Controller
 * Main orchestrator that connects Gemini AI, Action Parser, and Action Executor
 * 
 * This is the BRAIN that controls screen interactions.
 */

import { geminiActionParser, type ScreenAction } from './geminiActionParser';
import { actionExecutor } from './actionExecutor';
import { screenContext } from './screenContext';

export interface CommandResult {
    success: boolean;
    action?: ScreenAction;
    result?: any;
    message?: string;
    error?: string;
}

export class GeminiScreenController {
    private commandHistory: Array<{ command: string; action: ScreenAction; result: any }> = [];
    private isProcessing: boolean = false;

    /**
     * Process a natural language command and execute it
     */
    async processCommand(command: string): Promise<CommandResult> {
        // Security check
        if (!screenContext.canPerformAction()) {
            return {
                success: false,
                message: "I cannot perform actions when screen sharing is not active. Please share your screen first.",
                error: 'Screen sharing not active'
            };
        }

        if (this.isProcessing) {
            return {
                success: false,
                message: "Please wait, I'm still processing the previous command.",
                error: 'Busy'
            };
        }

        this.isProcessing = true;

        try {
            console.log('[GeminiScreenController] Processing command:', command);

            // Step 1: Try quick parse first (faster, no API call)
            let action = geminiActionParser.quickParse(command);

            // Step 2: If quick parse fails, use Gemini AI for context-aware parsing
            if (!action) {
                // Get screen context for better understanding
                const screenText = await this.getScreenContext();
                const previousActions = actionExecutor.getActionHistory();
                
                action = await geminiActionParser.parseWithContext(
                    command,
                    previousActions,
                    screenText
                );
            }

            console.log('[GeminiScreenController] Parsed action:', action);

            // Step 3: Execute the action
            if (action.type === 'NONE') {
                return {
                    success: true,
                    action,
                    message: "This seems like a conversational message, not an action command."
                };
            }

            const result = await actionExecutor.executeAction(action);

            // Step 4: Record in history
            this.commandHistory.push({ command, action, result });
            if (this.commandHistory.length > 10) {
                this.commandHistory.shift();
            }

            return {
                success: result.success,
                action,
                result: result.data,
                message: result.message
            };

        } catch (error) {
            console.error('[GeminiScreenController] Error processing command:', error);
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error',
                message: "Sorry, I encountered an error while processing your command."
            };
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Get current screen context (for better AI understanding)
     */
    private async getScreenContext(): Promise<string> {
        try {
            const pageInfo = await actionExecutor.getPageInfo();
            return `Page: ${pageInfo.title}\nURL: ${pageInfo.url}\nVisible Text: ${pageInfo.text.substring(0, 500)}...`;
        } catch {
            return '';
        }
    }

    /**
     * Handle voice command (same as text command)
     */
    async processVoiceCommand(transcript: string): Promise<CommandResult> {
        return this.processCommand(transcript);
    }

    /**
     * Execute a pre-parsed action directly
     */
    async executeAction(action: ScreenAction): Promise<CommandResult> {
        if (!screenContext.canPerformAction()) {
            return {
                success: false,
                message: "Screen sharing is not active.",
                error: 'Not authorized'
            };
        }

        const result = await actionExecutor.executeAction(action);
        
        return {
            success: result.success,
            action,
            result: result.data,
            message: result.message
        };
    }

    /**
     * Get command history
     */
    getHistory() {
        return [...this.commandHistory];
    }

    /**
     * Clear command history
     */
    clearHistory() {
        this.commandHistory = [];
        actionExecutor.clearHistory();
        geminiActionParser.clearContext();
    }

    /**
     * Check if controller can process commands
     */
    canProcess(): boolean {
        return screenContext.canPerformAction() && !this.isProcessing;
    }

    /**
     * Get current status
     */
    getStatus() {
        return {
            isProcessing: this.isProcessing,
            isSharing: screenContext.getIsSharing(),
            mode: screenContext.getMode(),
            sharingLabel: screenContext.getSharingLabel(),
            historyCount: this.commandHistory.length
        };
    }

    /**
     * Perform common actions with shortcuts
     */
    async quickScroll(direction: 'up' | 'down', amount: number = 300): Promise<CommandResult> {
        const action: ScreenAction = { type: 'SCROLL', direction, amount, confidence: 1.0 };
        return this.executeAction(action);
    }

    async quickClick(target: string): Promise<CommandResult> {
        const action: ScreenAction = { type: 'CLICK', target, confidence: 0.8 };
        return this.executeAction(action);
    }

    async quickType(text: string): Promise<CommandResult> {
        const action: ScreenAction = { type: 'TYPE', text, confidence: 1.0 };
        return this.executeAction(action);
    }

    async quickRead(): Promise<CommandResult> {
        const action: ScreenAction = { type: 'READ', confidence: 1.0 };
        return this.executeAction(action);
    }
}

// Singleton instance
export const geminiScreenController = new GeminiScreenController();
