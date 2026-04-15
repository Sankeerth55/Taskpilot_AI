/**
 * Live Assistant Integration Example
 * Shows how to integrate the Gemini Screen Controller
 */

import { geminiScreenController } from './geminiScreenController';
import { screenContext } from './screenContext';

// ═══════════════════════════════════════════════════════════
// INTEGRATION POINT 1: Screen Sharing Start
// ═══════════════════════════════════════════════════════════

function handleScreenShareStart(stream: MediaStream) {
    // Determine sharing mode based on stream
    const videoTrack = stream.getVideoTracks()[0];
    const settings = videoTrack.getSettings();
    
    let mode: 'tab' | 'window' | 'entire-screen' = 'entire-screen';
    
    // Chrome provides displaySurface in settings
    if ('displaySurface' in settings) {
        const surface = (settings as any).displaySurface;
        if (surface === 'browser') mode = 'tab';
        else if (surface === 'window') mode = 'window';
        else mode = 'entire-screen';
    }
    
    // Start screen context
    screenContext.startSharing(mode);
    
    console.log(`[Integration] Screen sharing started: ${mode}`);
    
    // Listen for track end
    videoTrack.addEventListener('ended', () => {
        handleScreenShareStop();
    });
}

// ═══════════════════════════════════════════════════════════
// INTEGRATION POINT 2: Screen Sharing Stop
// ═══════════════════════════════════════════════════════════

function handleScreenShareStop() {
    screenContext.stopSharing();
    console.log('[Integration] Screen sharing stopped');
}

// ═══════════════════════════════════════════════════════════
// INTEGRATION POINT 3: Process Voice Commands
// ═══════════════════════════════════════════════════════════

async function handleGeminiTranscript(transcript: string): Promise<string> {
    console.log('[Integration] Processing transcript:', transcript);
    
    // Check if screen sharing is active
    if (!screenContext.getIsSharing()) {
        return "I cannot interact with your screen because sharing is not active. Please share your screen first.";
    }
    
    // Process command
    const result = await geminiScreenController.processCommand(transcript);
    
    if (result.success) {
        // Success - provide feedback
        if (result.action?.type === 'READ') {
            return `I can see: ${result.result?.text?.substring(0, 200)}...`;
        } else if (result.action?.type === 'NONE') {
            return result.message || "Okay, I understand.";
        } else {
            return `Done! ${result.message || 'Action completed.'}`;
        }
    } else {
        // Error - explain what went wrong
        return `Sorry, I couldn't do that: ${result.error || 'Unknown error'}`;
    }
}

// ═══════════════════════════════════════════════════════════
// INTEGRATION POINT 4: React Hook for Screen State
// ═══════════════════════════════════════════════════════════

import { useState, useEffect } from 'react';
import type { ScreenState } from './screenContext';

function useScreenSharing() {
    const [screenState, setScreenState] = useState<ScreenState>({
        isSharing: false,
        mode: null
    });

    useEffect(() => {
        const unsubscribe = screenContext.subscribe((state) => {
            setScreenState(state);
        });

        return () => unsubscribe();
    }, []);

    return screenState;
}

// ═══════════════════════════════════════════════════════════
// INTEGRATION POINT 5: Example React Component
// ═══════════════════════════════════════════════════════════

function ScreenControlPanel() {
    const screenState = useScreenSharing();

    return (
        <div className="screen-control-panel">
            {screenState.isSharing ? (
                <div className="sharing-active">
                    <div className="status-indicator">
                        <span className="green-dot"></span>
                        <span>Controlling: {screenContext.getSharingLabel()}</span>
                    </div>
                    
                    <div className="quick-actions">
                        <button onClick={() => geminiScreenController.quickScroll('down')}>
                            Scroll Down
                        </button>
                        <button onClick={() => geminiScreenController.quickRead()}>
                            Read Page
                        </button>
                        <button onClick={handleScreenShareStop}>
                            Stop Sharing
                        </button>
                    </div>
                </div>
            ) : (
                <div className="sharing-inactive">
                    <p>Screen sharing is not active</p>
                    <button onClick={requestScreenShare}>
                        Start Screen Share
                    </button>
                </div>
            )}
        </div>
    );
}

async function requestScreenShare() {
    try {
        const stream = await navigator.mediaDevices.getDisplayMedia({
            video: true,
            audio: false
        });
        
        handleScreenShareStart(stream);
    } catch (error) {
        console.error('Screen share denied:', error);
    }
}

// ═══════════════════════════════════════════════════════════
// INTEGRATION POINT 6: Command Shortcuts
// ═══════════════════════════════════════════════════════════

export const CommandShortcuts = {
    // Quick navigation
    scrollDown: () => geminiScreenController.quickScroll('down', 500),
    scrollUp: () => geminiScreenController.quickScroll('up', 500),
    scrollToTop: () => geminiScreenController.quickScroll('up', 999999),
    scrollToBottom: () => geminiScreenController.quickScroll('down', 999999),
    
    // Quick reading
    readPage: () => geminiScreenController.quickRead(),
    
    // Quick interactions
    clickButton: (buttonText: string) => geminiScreenController.quickClick(buttonText),
    typeText: (text: string) => geminiScreenController.quickType(text),
    
    // Status
    getStatus: () => geminiScreenController.getStatus(),
    canControl: () => screenContext.canPerformAction()
};

// ═══════════════════════════════════════════════════════════
// INTEGRATION POINT 7: Error Handling
// ═══════════════════════════════════════════════════════════

async function safeExecuteCommand(command: string): Promise<string> {
    try {
        const result = await geminiScreenController.processCommand(command);
        
        if (!result.success) {
            // Log for debugging
            console.error('[Integration] Command failed:', {
                command,
                error: result.error,
                action: result.action
            });
            
            // User-friendly error messages
            if (result.error?.includes('not active')) {
                return "Please share your screen first before I can help with that.";
            } else if (result.error?.includes('not found')) {
                return "I couldn't find that element on the page. Could you describe it differently?";
            } else if (result.error?.includes('Timeout')) {
                return "The page took too long to respond. Please try again.";
            }
            
            return `I encountered a problem: ${result.message || result.error}`;
        }
        
        return result.message || "Done!";
        
    } catch (error) {
        console.error('[Integration] Exception:', error);
        return "Something went wrong. Please try again.";
    }
}

// ═══════════════════════════════════════════════════════════
// EXPORT EVERYTHING
// ═══════════════════════════════════════════════════════════

export {
    handleScreenShareStart,
    handleScreenShareStop,
    handleGeminiTranscript,
    useScreenSharing,
    ScreenControlPanel,
    requestScreenShare,
    safeExecuteCommand
};

// ═══════════════════════════════════════════════════════════
// USAGE IN LiveAssistant.tsx
// ═══════════════════════════════════════════════════════════

/**
 * INTEGRATION GUIDE
 * 
 * STEP 1: Import the integration helpers
 * -------------------------------------
 * import { 
 *     handleScreenShareStart, 
 *     handleScreenShareStop,
 *     handleGeminiTranscript 
 * } from './services/live/screenIntegrationExample';
 * 
 * 
 * STEP 2: In your setupScreenProcessing function
 * -----------------------------------------------
 * const setupScreenProcessing = (stream: MediaStream) => {
 *     // Your existing video processing...
 *     
 *     // Add this line:
 *     handleScreenShareStart(stream);
 *     
 *     // Track when stream ends
 *     stream.getVideoTracks()[0].addEventListener('ended', () => {
 *         handleScreenShareStop();
 *     });
 * };
 * 
 * 
 * STEP 3: In your Gemini message handler
 * ---------------------------------------
 * // When you receive a transcript from Gemini Live
 * const handleLiveMessage = async (message: LiveServerMessage) => {
 *     if (message.serverContent?.turnComplete) {
 *         const transcript = extractTranscript(message);
 *         
 *         if (transcript) {
 *             // Process as a potential command
 *             const response = await handleGeminiTranscript(transcript);
 *             console.log('[Gemini Response]', response);
 *             
 *             // Optionally send response back to Gemini
 *             // session.send([{ text: response }]);
 *         }
 *     }
 * };
 * 
 * 
 * STEP 4: Add screen state indicator to your UI
 * -----------------------------------------------
 * import { useScreenSharing } from './services/live/screenIntegrationExample';
 * 
 * function LiveAssistant() {
 *     const screenState = useScreenSharing();
 *     
 *     // Then in your JSX:
 *     // {screenState.isSharing && (
 *     //     <div className="screen-sharing-indicator">
 *     //         🟢 Controlling: {screenState.mode}
 *     //     </div>
 *     // )}
 * }
 */

