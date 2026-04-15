/**
 * Gemini Action Parser
 * Converts natural language commands into structured actions using Google Gemini API
 */

import { GoogleGenAI } from "@google/genai";

// Initialize Gemini AI Client
const API_KEY = (import.meta as any).env?.VITE_GEMINI_API_KEY || process.env.VITE_GEMINI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey: API_KEY || 'dummy_key' });

export interface ScreenAction {
    type: 'CLICK' | 'TYPE' | 'SCROLL' | 'READ' | 'WAIT' | 'FOCUS' | 'NONE';
    target?: string;
    text?: string;
    direction?: 'up' | 'down';
    amount?: number;
    duration?: number;
    selector?: string;
    confidence?: number;
}

const ACTION_PARSING_PROMPT = `You are a command parser for a screen automation system. Your ONLY job is to parse user commands into structured JSON actions.

ALLOWED ACTIONS:
1. CLICK - Click on an element
   - Requires: target (button text, link text, or CSS selector)
   - Example: {"type": "CLICK", "target": "Submit", "selector": "button.submit"}

2. TYPE - Type text into active input field
   - Requires: text (the text to type)
   - Example: {"type": "TYPE", "text": "hello@example.com"}

3. SCROLL - Scroll the page
   - Requires: direction ("up" or "down"), amount (pixels, default 300)
   - Example: {"type": "SCROLL", "direction": "down", "amount": 300}

4. READ - Read page content
   - No parameters needed
   - Example: {"type": "READ"}

5. WAIT - Wait for duration
   - Requires: duration (milliseconds)
   - Example: {"type": "WAIT", "duration": 2000}

6. FOCUS - Focus on an input field
   - Requires: target (field label or CSS selector)
   - Example: {"type": "FOCUS", "target": "email"}

7. NONE - No action needed (conversational response)
   - Example: {"type": "NONE"}

RULES:
- Return ONLY valid JSON, no explanations
- If uncertain, return {"type": "NONE"}
- For clicking, prefer visible text over selectors
- Always include confidence score (0-1)

USER COMMAND EXAMPLES:
"Click the submit button" -> {"type": "CLICK", "target": "submit", "confidence": 0.9}
"Type my email" -> {"type": "TYPE", "text": "user@email.com", "confidence": 0.7}
"Scroll down" -> {"type": "SCROLL", "direction": "down", "amount": 300, "confidence": 1.0}
"What's on this page?" -> {"type": "READ", "confidence": 1.0}
"Wait 3 seconds" -> {"type": "WAIT", "duration": 3000, "confidence": 1.0}
"Hello" -> {"type": "NONE", "confidence": 1.0}

Now parse this command:`;

export class GeminiActionParser {
    private model: any;
    private conversationContext: string[] = [];

    constructor() {
        // Use flash model for fast, efficient parsing
        try {
            this.model = ai.models.get({ model: 'gemini-2.0-flash-lite' });
        } catch {
            // Fallback to flash if lite not available
            this.model = ai.models.get({ model: 'gemini-2.0-flash' });
        }
    }

    /**
     * Parse a natural language command into a structured action
     */
    async parseCommand(command: string, screenContext?: string): Promise<ScreenAction> {
        try {
            // Prepare context-aware prompt
            let contextInfo = '';
            if (screenContext) {
                contextInfo = `\n\nCURRENT SCREEN CONTEXT:\n${screenContext.substring(0, 500)}...\n`;
            }

            const fullPrompt = `${ACTION_PARSING_PROMPT}\n${contextInfo}\nCOMMAND: "${command}"\n\nJSON:`;

            const result = await this.model.generateText({
                prompt: fullPrompt,
                config: {
                    temperature: 0.3, // Low temperature for consistent parsing
                    maxOutputTokens: 200,
                }
            });

            const responseText = result.text.trim();
            
            // Extract JSON from response (handle code blocks)
            let jsonText = responseText;
            if (responseText.includes('```json')) {
                jsonText = responseText.split('```json')[1].split('```')[0].trim();
            } else if (responseText.includes('```')) {
                jsonText = responseText.split('```')[1].split('```')[0].trim();
            }

            // Parse JSON
            const action: ScreenAction = JSON.parse(jsonText);

            // Validate action type
            const validTypes = ['CLICK', 'TYPE', 'SCROLL', 'READ', 'WAIT', 'FOCUS', 'NONE'];
            if (!validTypes.includes(action.type)) {
                console.warn(`Invalid action type: ${action.type}, defaulting to NONE`);
                return { type: 'NONE', confidence: 0 };
            }

            // Store in context for follow-up commands
            this.conversationContext.push(command);
            if (this.conversationContext.length > 5) {
                this.conversationContext.shift();
            }

            console.log('[GeminiActionParser] Parsed action:', action);
            return action;

        } catch (error) {
            console.error('[GeminiActionParser] Parsing error:', error);
            // Return NONE action on error
            return { type: 'NONE', confidence: 0 };
        }
    }

    /**
     * Parse command with conversational context for better understanding
     */
    async parseWithContext(command: string, previousActions: ScreenAction[], screenText?: string): Promise<ScreenAction> {
        // Build context string
        const contextLines = [
            'PREVIOUS ACTIONS:',
            ...previousActions.slice(-3).map((a, i) => `${i + 1}. ${a.type} ${JSON.stringify(a)}`),
            '',
            'RECENT COMMANDS:',
            ...this.conversationContext.slice(-3),
        ];

        const context = contextLines.join('\n');
        return this.parseCommand(command, screenText || context);
    }

    /**
     * Clear conversation context
     */
    clearContext(): void {
        this.conversationContext = [];
    }

    /**
     * Quick parse for common commands (fallback without API call)
     */
    quickParse(command: string): ScreenAction | null {
        const lower = command.toLowerCase().trim();

        // Scroll commands
        if (lower.match(/scroll\s+(down|up)/)) {
            const direction = lower.includes('down') ? 'down' : 'up';
            return { type: 'SCROLL', direction, amount: 300, confidence: 1.0 };
        }

        // Read commands
        if (lower.match(/read|what('s| is) (on |in )?(this |the )?(page|screen)/)) {
            return { type: 'READ', confidence: 1.0 };
        }

        // Click commands with obvious targets
        if (lower.match(/click|press|tap/)) {
            const targetMatch = lower.match(/(?:click|press|tap)\s+(?:on\s+)?(?:the\s+)?['"]?(\w+)['"]?/);
            if (targetMatch) {
                return { type: 'CLICK', target: targetMatch[1], confidence: 0.8 };
            }
        }

        // Type commands
        if (lower.match(/type|enter|input/)) {
            // Extract quoted text
            const textMatch = command.match(/['"]([^'"]+)['"]/);
            if (textMatch) {
                return { type: 'TYPE', text: textMatch[1], confidence: 0.9 };
            }
        }

        return null;
    }
}

// Singleton instance
export const geminiActionParser = new GeminiActionParser();
