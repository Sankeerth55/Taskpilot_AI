import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, Bot, X, StopCircle, Loader2, Monitor, MonitorOff } from 'lucide-react';
import { GoogleGenAI, LiveServerMessage, Modality } from '@google/genai';
import { screenContext } from '../services/live/screenContext';
import { actionExecutor } from '../services/live/actionExecutor';
import playwrightService from '../services/playwrightService';

// --- Constants & Types ---
const SHAKE_INTERVAL = 3000;
const ANIMATION_DURATION = 500;
const ENV = (import.meta as any).env || {};
const API_KEY = ENV.GEMINI_API_KEY || ENV.VITE_GEMINI_API_KEY || process.env.API_KEY || process.env.GEMINI_API_KEY || '';
const LIVE_MODELS = [
    'gemini-2.5-flash-native-audio-preview-12-2025',
    'gemini-live-2.5-flash-preview',
    'gemini-2.0-flash-live-001'
];

type LiveMode = 'voice' | 'avatar' | null;

// --- Audio Utils (PCM Encoding/Decoding) ---

// Convert Float32 audio data to Int16 PCM Base64 for Live API
function floatTo16BitPCM(input: Float32Array): string {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    const bytes = new Uint8Array(output.buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

// Decode Base64 PCM 24kHz/16kHz to AudioBuffer
async function decodeAudioData(base64: string, ctx: AudioContext, sampleRate = 24000): Promise<AudioBuffer> {
    const binaryString = atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
    }

    const buffer = ctx.createBuffer(1, float32.length, sampleRate);
    buffer.getChannelData(0).set(float32);
    return buffer;
}

// --- Component ---

const LiveAssistant: React.FC = () => {
    // UI State
    const [isOpen, setIsOpen] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [isShaking, setIsShaking] = useState(false);
    const [activeMode, setActiveMode] = useState<LiveMode>(null);
    const [status, setStatus] = useState<'idle' | 'connecting' | 'active' | 'error'>('idle');
    const [errorMessage, setErrorMessage] = useState('');
    const [isScreenSharing, setIsScreenSharing] = useState(false);
    const [playwrightConnected, setPlaywrightConnected] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);

    // Audio/Live API Refs
    const sessionPromiseRef = useRef<Promise<any> | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const inputContextRef = useRef<AudioContext | null>(null);
    const nextStartTimeRef = useRef<number>(0);
    const streamRef = useRef<MediaStream | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const speakingTimeoutRef = useRef<number | null>(null);

    // Video/Screen Share Refs
    const screenStreamRef = useRef<MediaStream | null>(null);
    const videoIntervalRef = useRef<number | null>(null);
    const sharedTabIdRef = useRef<string | null>(null); // Track which tab is being shared
    const lastScreenshotRef = useRef<string | null>(null); // Cache last screenshot for continuous actions
    const lastScreenshotTimeRef = useRef<number>(0); // Track when screenshot was taken

    // --- Initialize Playwright mode on mount ---
    useEffect(() => {
        // Set Playwright as the default and only execution mode
        actionExecutor.setExecutionMode('playwright');
        console.log('%c🎭 Playwright mode activated (no extension needed)', 'background: purple; color: white; font-weight: bold; padding: 4px 8px;');
    }, []);

    // --- Animation Logic ---
    useEffect(() => {
        if (activeMode) return; // Disable shake when active

        const interval = setInterval(() => {
            if (!isHovered && !isOpen) {
                setIsShaking(true);
                setTimeout(() => setIsShaking(false), ANIMATION_DURATION);
            }
        }, SHAKE_INTERVAL);

        return () => clearInterval(interval);
    }, [isHovered, isOpen, activeMode]);

    // --- Screen Share State Sync ---
    useEffect(() => {
        // When component unmounts or state changes, ensure proper cleanup
        if (!isScreenSharing && screenContext.getIsSharing()) {
            screenContext.stopSharing();
            // 🎭 KEEP Playwright browser running even after screen share stops
            // This allows actions to continue on the cached screenshot
            console.log('%c🎭 Screen sharing stopped but Playwright browser STAYS ACTIVE for continuous actions', 'background: blue; color: white; padding: 4px 8px;');
        }
        // Don't stop actions when sharing stops - let them continue!
    }, [isScreenSharing, playwrightConnected]);

    // --- Shared-Screen Avatar State Sync ---
    useEffect(() => {
        const showSharedAvatar = Boolean(
            isScreenSharing &&
            activeMode === 'avatar' &&
            status === 'active'
        );

        screenContext.setAvatarState({
            visible: showSharedAvatar,
            speaking: showSharedAvatar ? isSpeaking : false,
            listening: showSharedAvatar ? !isSpeaking : false,
            mode: activeMode === 'voice' ? 'voice' : 'avatar'
        });
    }, [isScreenSharing, activeMode, status, isSpeaking]);

    // --- Cleanup ---
    const disconnectSession = useCallback(() => {
        // Stop Audio Input
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }
        if (inputContextRef.current) {
            inputContextRef.current.close();
            inputContextRef.current = null;
        }

        // Stop Audio Output
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        // Stop Screen Share
        if (screenStreamRef.current) {
            screenStreamRef.current.getTracks().forEach(track => track.stop());
            screenStreamRef.current = null;
        }
        if (videoIntervalRef.current) {
            clearInterval(videoIntervalRef.current);
            videoIntervalRef.current = null;
        }
        
        // Stop Playwright browser on full disconnect
        if (playwrightConnected) {
            playwrightService.stopBrowser();
            setPlaywrightConnected(false);
        }

        // Reset Session Refs
        sessionPromiseRef.current = null;
        if (speakingTimeoutRef.current) {
            clearTimeout(speakingTimeoutRef.current);
            speakingTimeoutRef.current = null;
        }
        setIsSpeaking(false);
        screenContext.setAvatarState({ visible: false, speaking: false, listening: false, mode: 'avatar' });

        setActiveMode(null);
        setStatus('idle');
        setIsOpen(false);
        setIsScreenSharing(false);
        screenContext.stopSharing(); // ✅ FIX: Use stopSharing
        actionExecutor.stop();
    }, []);

    // --- Screen Share Logic ---
    const setupScreenProcessing = (stream: MediaStream) => {
        const video = document.createElement('video');
        video.srcObject = stream;
        video.muted = true;
        video.play();

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Send frames at 1fps
        videoIntervalRef.current = window.setInterval(async () => {
            if (ctx && video.videoWidth > 0 && sessionPromiseRef.current) {
                // Downscale slightly for performance
                const width = video.videoWidth > 1280 ? 1280 : video.videoWidth;
                const height = (width / video.videoWidth) * video.videoHeight;

                canvas.width = width;
                canvas.height = height;
                ctx.drawImage(video, 0, 0, width, height);

                const b64 = canvas.toDataURL('image/jpeg', 0.6).split(',')[1];

                // 💾 Cache the screenshot for continuous actions after sharing stops
                lastScreenshotRef.current = b64;
                lastScreenshotTimeRef.current = Date.now();

                sessionPromiseRef.current.then(session => {
                    session.sendRealtimeInput({
                        media: {
                            mimeType: 'image/jpeg',
                            data: b64
                        }
                    });
                });
            }
        }, 1000);
    };

    const toggleScreenShare = async () => {
        if (!sessionPromiseRef.current) return;

        if (isScreenSharing) {
            // Stop Sharing
            if (screenStreamRef.current) {
                screenStreamRef.current.getTracks().forEach(track => track.stop());
                screenStreamRef.current = null;
            }
            if (videoIntervalRef.current) {
                clearInterval(videoIntervalRef.current);
                videoIntervalRef.current = null;
            }
            setIsScreenSharing(false);
            screenContext.stopSharing();
            screenContext.setAvatarState({ visible: false, speaking: false, listening: false, mode: 'avatar' });

            console.log('%c🎭 Playwright browser remains active for continuous actions', 'background: blue; color: white; padding: 4px 8px;');
            const cacheAge = lastScreenshotTimeRef.current ? Date.now() - lastScreenshotTimeRef.current : 0;
            console.log(`%c💾 Cached screenshot age: ${Math.round(cacheAge / 1000)}s`, 'color: blue;');

            // Notify AI
            sessionPromiseRef.current.then(session => {
                session.sendRealtimeInput({
                    text: 'Screen sharing stopped. Actions will continue using the cached screenshot.'
                });
            });

        } else {
            // Start Sharing
            try {
                // 🌟 Chrome native green border appears automatically!
                const stream = await navigator.mediaDevices.getDisplayMedia({
                    video: { width: 1280, height: 720 },
                    audio: false // Chrome shows green border on shared tab/window
                });
                screenStreamRef.current = stream;

                // Get shared tab reference - Chrome provides this info
                // Store the shared screen reference for targeting actions
                const videoTrack = stream.getVideoTracks()[0];
                const settings = videoTrack.getSettings();
                const displaySurface = settings.displaySurface; // 'monitor', 'window', or 'browser' (tab)
                
                // Generate unique ID for this shared screen session
                const sharedTabId = `shared_${Date.now()}`;
                sharedTabIdRef.current = sharedTabId;

                console.log('%c🟢 CHROME GREEN BORDER ACTIVE', 'background: green; color: white; font-weight: bold; padding: 4px 8px;');
                console.log(`%c📺 Shared Surface: ${displaySurface}`, 'color: green; font-size: 12px;');
                console.log(`%c🎯 Actions will execute on SHARED screen (ID: ${sharedTabId})`, 'color: blue; font-weight: bold;');

                // 🎭 Auto-connect to Playwright for action execution
                try {
                    const connected = await playwrightService.connect();
                    if (connected) {
                        // Start browser with the current URL
                        await playwrightService.startBrowser('chrome');
                        setPlaywrightConnected(true);
                        console.log('%c✅ Playwright connected - Actions ready!', 'background: green; color: white; font-weight: bold; padding: 4px 8px;');
                    }
                } catch (err) {
                    console.error('%c❌ Playwright connection failed:', 'color: red; font-weight: bold;', err);
                    setPlaywrightConnected(false);
                }

                // Handle user clicking "Stop sharing" in browser UI
                stream.getVideoTracks()[0].onended = () => {
                    if (videoIntervalRef.current) {
                        clearInterval(videoIntervalRef.current);
                        videoIntervalRef.current = null;
                    }
                    setIsScreenSharing(false);
                    screenContext.stopSharing();
                    screenStreamRef.current = null;
                    sharedTabIdRef.current = null;
                    
                    console.log('%c🔴 GREEN BORDER REMOVED', 'background: red; color: white; font-weight: bold; padding: 4px 8px;');
                    console.log('%c🎭 Playwright browser CONTINUES RUNNING - Actions will use cached screenshot', 'background: blue; color: white; padding: 4px 8px;');
                    
                    const cacheAge = Date.now() - lastScreenshotTimeRef.current;
                    console.log(`%c💾 Last screenshot cached ${Math.round(cacheAge / 1000)}s ago`, 'color: blue; font-size: 12px;');

                    // Notify AI that we're switching to cached screenshot mode
                    sessionPromiseRef.current.then(session => {
                        session.sendRealtimeInput({
                            text: `Screen sharing stopped. I'll continue using the last screenshot I captured for any actions you request. The Playwright browser is still active and ready to execute commands.`
                        });
                    });
                };

                setIsScreenSharing(true);
                screenContext.startSharing(displaySurface as any, sharedTabId);
                setupScreenProcessing(stream);
                screenContext.setAvatarState({
                    visible: activeMode === 'avatar',
                    speaking: false,
                    listening: activeMode === 'avatar',
                    mode: activeMode === 'voice' ? 'voice' : 'avatar'
                });

                // Notify AI with emphasis on shared screen
                sessionPromiseRef.current.then(session => {
                    session.sendRealtimeInput({
                        text: `Screen sharing started. Chrome's green border shows which ${displaySurface} is shared. All your actions will execute ONLY on this shared screen, even if I switch tabs. The Playwright browser will remain active for continuous actions even if screen sharing stops later.`
                    });
                });

            } catch (err) {
                console.error("Screen share failed or cancelled", err);
                setIsScreenSharing(false);
            }
        }
    };

    // --- Live API Connection ---
    const startSession = async (mode: LiveMode) => {
        try {
            setIsOpen(false); // Close menu
            setActiveMode(mode);
            setStatus('connecting');
            setErrorMessage('');

            // 1. Get User Media FIRST to ensure permissions
            const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = micStream;

            // 2. Initialize Audio Contexts
            const AC = window.AudioContext || window.webkitAudioContext;
            const outputCtx = new AC({ sampleRate: 24000 });
            audioContextRef.current = outputCtx;
            nextStartTimeRef.current = outputCtx.currentTime;

            const inputCtx = new AC({ sampleRate: 16000 });
            inputContextRef.current = inputCtx;

            // 3. Initialize AI Client
            if (!API_KEY) {
                throw new Error('Gemini API key is missing. Add GEMINI_API_KEY to your local .env file and restart the frontend server.');
            }
            const ai = new GoogleGenAI({ apiKey: API_KEY });

            // 4. Connect to Live API
            // Define tools for screen interaction
            const tools = [
                {
                    functionDeclarations: [
                        {
                            name: "scroll",
                            description: "IMMEDIATELY scroll the screen up or down. Use when user says 'scroll down', 'scroll up', 'go down', etc. Call this function directly - don't say 'OK' first!",
                            parameters: {
                                type: "OBJECT" as any,
                                properties: {
                                    direction: { type: "STRING" as any, enum: ["up", "down"] },
                                    amount: { type: "STRING" as any, enum: ["page", "small"], description: "Amount to scroll" }
                                },
                                required: ["direction"]
                            }
                        },
                        {
                            name: "auto_scroll",
                            description: "IMMEDIATELY start automatic scrolling to read long content. Use when user says 'keep scrolling', 'auto scroll', 'scroll automatically'. Call this function directly without verbal acknowledgment!",
                            parameters: {
                                type: "OBJECT" as any,
                                properties: {
                                    speed: { type: "STRING" as any, enum: ["slow", "medium", "fast"] }
                                }
                            }
                        },
                        {
                            name: "stop_action",
                            description: "IMMEDIATELY stop any ongoing action like scrolling. Use when user says 'stop', 'stop scrolling', 'pause'. Call this function directly!",
                            parameters: { type: "OBJECT" as any, properties: {} }
                        },
                        {
                            name: "get_visible_text",
                            description: "IMMEDIATELY get all text visible on screen to read it aloud. Use when user says 'read the screen', 'what does it say', 'read this page'. Call this function directly!",
                            parameters: { type: "OBJECT" as any, properties: {} }
                        },
                        {
                            name: "type_text",
                            description: "IMMEDIATELY type text in the focused input field. Use when user says 'search X', 'type X', 'enter X', 'write X'. Call this function directly with the text - don't say 'OK' first!",
                            parameters: {
                                type: "OBJECT" as any,
                                properties: {
                                    text: { type: "STRING" as any, description: "The exact text to type" }
                                },
                                required: ["text"]
                            }
                        },
                        {
                            name: "click",
                            description: "IMMEDIATELY click an element on screen. Use when user says 'click X', 'press X', 'open X', 'tap X'. Call this function directly with the button/link text or selector - don't acknowledge verbally first!",
                            parameters: {
                                type: "OBJECT" as any,
                                properties: {
                                    target: { type: "STRING" as any, description: "Visible text on button/link (e.g., 'Sign in', 'Search') or CSS selector" }
                                },
                                required: ["target"]
                            }
                        }
                    ]
                }
            ];

            const connectWithFallbackModel = async () => {
                let lastError: unknown = null;

                for (const model of LIVE_MODELS) {
                    try {
                        return await ai.live.connect({
                            model,
                            config: {
                    tools: tools,
                    responseModalities: [Modality.AUDIO],
                    speechConfig: {
                        voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Kore' } }
                    },
                    systemInstruction: `You are TaskPilot AI, an advanced AI assistant with voice and vision capabilities. 

CRITICAL IDENTITY: Your name is TaskPilot AI. NEVER say 'I am Gemini' or mention being a language model. When asked who you are, always respond that you are TaskPilot AI.

CAPABILITIES:
- You can hear the user's voice and see their screen when shared
- You can analyze visual frames to understand what's on screen
- You can read text and answer questions about content
- You have tools for clicking, typing, and scrolling

SHARED SCREEN BEHAVIOR (CRITICAL):
- When user starts screen sharing, Chrome shows a GREEN BORDER on the specific tab/window being shared
- The green border STAYS on that tab even when user switches to other tabs
- ALL your actions (click, type, scroll) execute ONLY on the SHARED screen (the one with green border)
- Even if the user is viewing a different tab, your actions affect only the shared tab
- Example: User shares Google tab → switches to Microsoft tab → you type "search query" → it types in GOOGLE tab (shared screen)
- This allows the user to work on other tabs while you control the shared screen

🎭 CONTINUOUS ACTION MODE:
- When user stops screen sharing, the Playwright browser STAYS ACTIVE
- You can still execute actions using the last cached screenshot
- Actions will continue to work even without live screen updates
- If user requests an action after sharing stops, use the cached context and execute normally
- Example: User shares screen → stops sharing → says "scroll down" → you CAN still scroll using cached screenshot

🔥 CRITICAL ACTION RULES (MUST FOLLOW):
1. When user asks for an action → IMMEDIATELY CALL THE TOOL (don't say "OK" first!)
2. NEVER respond with just text like "OK", "Sure", "Done" - ALWAYS use function calls
3. Examples:
   ❌ WRONG: User: "search weather" → You: "OK, searching for weather"
   ✅ RIGHT: User: "search weather" → You: *call type_text function immediately*
   
   ❌ WRONG: User: "scroll down" → You: "Sure, scrolling down"
   ✅ RIGHT: User: "scroll down" → You: *call scroll function immediately*
   
   ❌ WRONG: User: "click login" → You: "Clicking login button"
   ✅ RIGHT: User: "click login" → You: *call click function immediately*

4. ONLY speak AFTER the tool returns success/failure
5. If tool returns success: true → Say what you did: "Searched for weather" or "Clicked the login button"
6. If tool returns success: false → Say it failed: "I couldn't click that button because [reason from error]"
7. NEVER say "OK" or acknowledge BEFORE calling the tool - just DO IT immediately

ACTION COMMAND DETECTION:
- "search X" = call type_text with X
- "click X" = call click with X
- "scroll down/up" = call scroll
- "type X" = call type_text with X
- "read the screen" = call get_visible_text
- "stop" = call stop_action

IMPORTANT:
- Don't narrate what you're about to do - just use the tool
- The tool execution IS your action - don't duplicate with speech
- All actions execute via Playwright automation (no extension needed)
- Wait for tool result before responding

RESPONSE STYLE:
- Be conversational, concise, and natural
- Always confirm what you actually did or didn't do AFTER the tool completes
- Don't pretend actions worked when they failed`
                            },
                            callbacks: {
                    onopen: () => {
                        console.log("TaskPilot Live Session Opened");
                        setStatus('active');
                    },
                    onmessage: async (msg: LiveServerMessage) => {
                        // Handle Audio
                        const audioData = msg.serverContent?.modelTurn?.parts?.[0]?.inlineData?.data;
                        const toolCall = msg.serverContent?.modelTurn?.parts?.[0]?.functionCall;
                        
                        // 🚨 DETECT: Audio response without tool call (the "OK" problem)
                        if (audioData && !toolCall && isScreenSharing) {
                            console.warn('%c⚠️ WARNING: Gemini responded with audio but NO tool call!', 'background: orange; color: white; font-weight: bold; padding: 4px 8px;');
                            console.warn('%c📢 This might be an "OK" response instead of executing action', 'color: orange; font-size: 12px;');
                            console.warn('%c💡 Check the audio to see if Gemini said "OK/Sure/Done" without calling a tool', 'color: orange; font-size: 11px;');
                        }
                        
                        if (audioData && audioContextRef.current) {
                            try {
                                const buffer = await decodeAudioData(audioData, audioContextRef.current);
                                const source = audioContextRef.current.createBufferSource();
                                source.buffer = buffer;
                                source.connect(audioContextRef.current.destination);

                                setIsSpeaking(true);
                                if (speakingTimeoutRef.current) {
                                    clearTimeout(speakingTimeoutRef.current);
                                }
                                speakingTimeoutRef.current = window.setTimeout(() => {
                                    setIsSpeaking(false);
                                }, Math.max(600, Math.ceil(buffer.duration * 1000) + 120));

                                // Schedule seamless playback
                                const now = audioContextRef.current.currentTime;
                                const start = Math.max(now, nextStartTimeRef.current);
                                source.start(start);
                                nextStartTimeRef.current = start + buffer.duration;
                            } catch (e) {
                                console.error("Audio decoding error", e);
                            }
                        }

                        // Handle Tool Calls
                        if (toolCall) {
                            console.log("🔧 Tool Call Received:", toolCall);
                            const { name, args } = toolCall;
                            let result: any = {};

                            if (name === "scroll") {
                                console.log('%c📜 EXECUTING SCROLL', 'background: blue; color: white; padding: 2px 6px; border-radius: 3px;', args);
                                const scrollResult = await actionExecutor.scroll(args.direction as any, args.amount === 'small' ? 100 : 'page');
                                if (scrollResult.success) {
                                    console.log('%c✅ SCROLL SUCCESS', 'background: green; color: white; padding: 2px 6px; border-radius: 3px;', scrollResult);
                                } else {
                                    console.log('%c❌ SCROLL FAILED', 'background: red; color: white; padding: 2px 6px; border-radius: 3px;', scrollResult);
                                }
                                result = scrollResult.success 
                                    ? { status: "scrolled", success: true } 
                                    : { status: "failed", success: false, error: scrollResult.message || "Could not scroll" };
                            } else if (name === "auto_scroll") {
                                console.log('%c🔄 STARTING AUTO-SCROLL', 'background: blue; color: white; padding: 2px 6px; border-radius: 3px;', args);
                                const speedMap: Record<string, number> = {
                                    "slow": 4000,
                                    "medium": 2000,
                                    "fast": 1000
                                };
                                const interval = speedMap[args.speed as string] || 2000;
                                actionExecutor.startAutoScroll(interval);
                                result = { status: `auto_scroll_started_at_${args.speed || 'medium'}_speed` };
                            } else if (name === "stop_action") {
                                console.log('%c⏹️ STOPPING ACTIONS', 'background: orange; color: white; padding: 2px 6px; border-radius: 3px;');
                                actionExecutor.stop();
                                result = { status: "stopped" };
                            } else if (name === "get_visible_text") {
                                console.log('%c📖 READING TEXT', 'background: blue; color: white; padding: 2px 6px; border-radius: 3px;');
                                const text = await actionExecutor.getVisibleText();
                                console.log('%c✅ TEXT READ', 'background: green; color: white; padding: 2px 6px; border-radius: 3px;', text.substring(0, 100) + "...");
                                result = { text: text };
                            } else if (name === "type_text") {
                                console.log('%c⌨️ TYPING TEXT', 'background: blue; color: white; padding: 2px 6px; border-radius: 3px;', args.text);
                                const typeResult = await actionExecutor.typeText(args.text as string);
                                if (typeResult.success) {
                                    console.log('%c✅ TYPE SUCCESS', 'background: green; color: white; padding: 2px 6px; border-radius: 3px;', typeResult);
                                } else {
                                    console.log('%c❌ TYPE FAILED', 'background: red; color: white; padding: 2px 6px; border-radius: 3px;', typeResult);
                                }
                                result = typeResult.success 
                                    ? { status: "typed", success: true } 
                                    : { status: "failed", success: false, error: typeResult.message || "Could not type text" };
                            } else if (name === "click") {
                                console.log('%c👆 CLICKING', 'background: blue; color: white; padding: 2px 6px; border-radius: 3px;', args.target);
                                const clickResult = await actionExecutor.click(args.target as string);
                                if (clickResult.success) {
                                    console.log('%c✅ CLICK SUCCESS', 'background: green; color: white; padding: 2px 6px; border-radius: 3px;', clickResult);
                                } else {
                                    console.log('%c❌ CLICK FAILED', 'background: red; color: white; padding: 2px 6px; border-radius: 3px;', clickResult);
                                }
                                result = clickResult.success 
                                    ? { status: "clicked", success: true } 
                                    : { status: "failed", success: false, error: clickResult.message || "Could not click element" };
                            }

                            // Send Tool Response back to Gemini
                            sessionPromise.then(session => {
                                session.sendToolResponse({
                                    functionResponses: [
                                        {
                                            name: name,
                                            response: { result: result }
                                        }
                                    ]
                                });
                            });
                        }
                    },
                    onclose: () => {
                        console.log("TaskPilot Live Session Closed");
                        disconnectSession();
                    },
                    onerror: (err) => {
                        console.error("TaskPilot Live Error:", err);
                        setErrorMessage("Network error. Please try again.");
                        setStatus('error');
                        // Do not immediately disconnect on all errors, but Network Error usually is fatal.
                    }
                            }
                        });
                    } catch (err) {
                        lastError = err;
                        console.warn(`Live connection failed for model: ${model}`, err);
                    }
                }

                throw lastError instanceof Error
                    ? lastError
                    : new Error('Unable to connect to Gemini Live API with available models.');
            };

            const sessionPromise = connectWithFallbackModel();

            sessionPromiseRef.current = sessionPromise;

            // 5. Setup Audio Stream Processing
            setupAudioProcessing(micStream, inputCtx, sessionPromise);

        } catch (e) {
            console.error(e);
            setStatus('error');
            setErrorMessage(e instanceof Error ? e.message : "Failed to start session");
        }
    };

    const setupAudioProcessing = (stream: MediaStream, ctx: AudioContext, sessionPromise: Promise<any>) => {
        const source = ctx.createMediaStreamSource(stream);
        const processor = ctx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
            const inputData = e.inputBuffer.getChannelData(0);
            const b64Data = floatTo16BitPCM(inputData);

            // Use the promise to send data to avoid stale closures and ensure session is ready
            sessionPromise.then(session => {
                session.sendRealtimeInput({
                    media: {
                        mimeType: "audio/pcm;rate=16000",
                        data: b64Data
                    }
                });
            }).catch(e => {
                console.error("Failed to send audio input", e);
            });
        };

        source.connect(processor);
        processor.connect(ctx.destination);
    };

    const isAvatarActive = activeMode === 'avatar' && status === 'active';
    const shouldFloatAvatar = isAvatarActive && isScreenSharing;

    return (
        <>
            {/* ✅ NO CUSTOM OVERLAY - Chrome's native green border shows automatically! */}
            {/* Chrome displays green border on the SPECIFIC shared tab/window */}
            {/* Border stays visible even when switching tabs */}
            
            {/* Active Session Overlay */}
            {activeMode && (
                <div className="fixed inset-0 z-[100] bg-white/95 backdrop-blur-sm flex flex-col items-center justify-center p-6 animate-in fade-in duration-300">
                    <div className="max-w-md w-full flex flex-col items-center text-center space-y-8">
                        {status === 'connecting' && (
                            <div className="flex flex-col items-center text-slate-500">
                                <Loader2 className="w-12 h-12 animate-spin text-blue-500 mb-4" />
                                <p>Connecting to Live AI...</p>
                            </div>
                        )}

                        {status === 'error' && (
                            <div className="text-red-500 bg-red-50 p-6 rounded-xl border border-red-100">
                                <p className="font-semibold mb-2">Connection Failed</p>
                                <p className="text-sm">{errorMessage}</p>
                                <button onClick={disconnectSession} className="mt-4 text-sm font-medium underline">Close</button>
                            </div>
                        )}

                        {status === 'active' && (
                            <>
                                <div className="relative flex justify-center items-center">
                                    {activeMode === 'avatar' ? (
                                        // Large Avatar Display for "AI Avatar" Mode
                                        <div
                                            className={`
                                                w-48 h-60 bg-gradient-to-b from-white via-slate-50 to-slate-300 rounded-[48%] border border-white/60 flex flex-col items-center pt-14
                                                transform-gpu will-change-transform transition-[transform,opacity,box-shadow] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]
                                                ${shouldFloatAvatar
                                                    ? 'fixed bottom-[20px] right-[20px] z-[9999] scale-75 opacity-95 shadow-[0_24px_50px_-20px_rgba(0,0,0,0.45),inset_0_-10px_10px_rgba(0,0,0,0.1),inset_0_5px_15px_rgba(255,255,255,1)]'
                                                    : 'relative scale-100 opacity-100 shadow-[0_30px_60px_-15px_rgba(0,0,0,0.3),inset_0_-10px_10px_rgba(0,0,0,0.1),inset_0_5px_15px_rgba(255,255,255,1)]'}
                                                ${isSpeaking ? 'animate-[gentle-shake_0.5s_ease-in-out_infinite]' : 'animate-[gentle-shake_3s_ease-in-out_infinite]'}
                                            `}
                                        >
                                            {/* Top Highlights */}
                                            <div className="absolute top-4 left-1/2 -translate-x-1/2 w-24 h-12 bg-white/90 blur-md rounded-[50%] z-30 opacity-80"></div>

                                            {/* Face */}
                                            <div className="relative w-32 h-24 bg-slate-950 rounded-[2.5rem] border-[4px] border-slate-800 shadow-[inset_0_0_20px_rgba(0,0,0,1)] flex items-center justify-center overflow-hidden z-30">
                                                <div className="absolute top-3 right-5 w-8 h-4 bg-white/10 rotate-12 blur-[2px] rounded-full"></div>
                                                <div className="font-mono text-[16px] font-black tracking-widest text-center leading-tight z-40 text-cyan-400 drop-shadow-[0_0_15px_rgba(34,211,238,1)] animate-pulse">
                                                    LIVE<br />AI
                                                </div>
                                                <div className="absolute inset-0 bg-blue-500/10 blur-sm z-10"></div>
                                            </div>

                                            {/* Seam */}
                                            <div className="w-full h-[1px] bg-slate-300/50 mt-8 shadow-sm z-20"></div>

                                            {/* Arms */}
                                            <div className="absolute top-24 -left-6 w-8 h-24 bg-gradient-to-r from-slate-200 to-white rounded-full -rotate-12 shadow-[4px_4px_10px_rgba(0,0,0,0.1)] border border-white z-10"></div>
                                            <div className="absolute top-24 -right-6 w-8 h-24 bg-gradient-to-l from-slate-200 to-white rounded-full rotate-12 shadow-[-4px_4px_10px_rgba(0,0,0,0.1)] border border-white z-10"></div>
                                        </div>
                                    ) : (
                                        // Standard Mic Visual for "Voice Mode"
                                        <>
                                            <div className="absolute -inset-4 bg-gradient-to-r from-blue-400 to-purple-400 rounded-full blur-xl opacity-30 animate-pulse"></div>
                                            <div className="w-32 h-32 rounded-full bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center shadow-2xl relative z-10">
                                                <Mic className="text-white w-12 h-12 animate-pulse" />
                                            </div>
                                        </>
                                    )}
                                </div>

                                <div className="space-y-2 mt-8">
                                    <h2 className="text-2xl font-bold text-slate-800">
                                        {activeMode === 'voice' ? 'Live Voice Mode' : 'AI Avatar Session'}
                                    </h2>
                                    <p className="text-slate-500">
                                        {isSpeaking
                                            ? 'Speaking...'
                                            : isScreenSharing
                                            ? '🟢 Looking at your screen in real-time...'
                                            : playwrightConnected 
                                                ? '📸 Using cached screenshot · Actions still work'
                                                : (activeMode === 'voice' ? 'Listening... Speak naturally.' : 'Interactive AI companion is active.')
                                        }
                                    </p>
                                </div>

                                <div className="flex gap-1 h-12 items-center justify-center">
                                    {[...Array(5)].map((_, i) => (
                                        <div
                                            key={i}
                                            className="w-2 bg-slate-800 rounded-full animate-[bounce_1s_infinite]"
                                            style={{
                                                height: `${Math.random() * 100}%`,
                                                animationDelay: `${i * 0.1}s`
                                            }}
                                        />
                                    ))}
                                </div>
                            </>
                        )}
                    </div>

                    <div className="absolute bottom-8 left-0 right-0 flex flex-col items-center gap-3">
                        {/* Playwright Status - Active Sharing */}
                        {status === 'active' && isScreenSharing && playwrightConnected && (
                            <div className="bg-green-50 border-2 border-green-400 text-green-900 px-6 py-3 rounded-xl shadow-lg max-w-lg text-center">
                                <p className="font-bold text-sm">✅ Live Screen + Actions Ready</p>
                                <p className="text-xs mt-1">
                                    🟢 <strong>Green border visible</strong> · AI sees your screen in real-time<br/>
                                    🎭 Playwright browser active · Actions execute immediately
                                </p>
                            </div>
                        )}
                        
                        {/* Playwright Status - Cached Mode (sharing stopped but actions still work) */}
                        {status === 'active' && !isScreenSharing && playwrightConnected && (
                            <div className="bg-blue-50 border-2 border-blue-400 text-blue-900 px-6 py-3 rounded-xl shadow-lg max-w-lg text-center">
                                <p className="font-bold text-sm">🎭 Actions Continue via Cached Screenshot</p>
                                <p className="text-xs mt-1">
                                    📸 Using last captured screen · <strong>Actions still work!</strong><br/>
                                    💡 Share screen again for live updates
                                </p>
                            </div>
                        )}
                        
                        {/* Playwright Status - Connecting */}
                        {status === 'active' && isScreenSharing && !playwrightConnected && (
                            <div className="bg-yellow-50 border-2 border-yellow-400 text-yellow-900 px-6 py-3 rounded-xl shadow-lg max-w-lg text-center">
                                <p className="font-bold text-sm">⚠️ Connecting to Playwright...</p>
                                <p className="text-xs mt-1">
                                    Make sure backend server is running on port 8000
                                </p>
                            </div>
                        )}

                        <div className="flex gap-4">
                            {status === 'active' && (
                                <button
                                    onClick={toggleScreenShare}
                                    className={`
                                        group flex items-center gap-3 px-6 py-4 rounded-full shadow-lg transition-all hover:scale-105 active:scale-95 border
                                        ${isScreenSharing
                                            ? 'bg-white text-green-600 border-green-200 hover:bg-green-50 shadow-green-100'
                                            : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                                        }
                                    `}
                                >
                                    {isScreenSharing ? (
                                        <>
                                            <MonitorOff size={24} className="stroke-current" />
                                            <span className="font-semibold text-lg">Stop Sharing</span>
                                        </>
                                    ) : (
                                        <>
                                            <Monitor size={24} className="stroke-current" />
                                            <span className="font-semibold text-lg">Share Screen</span>
                                        </>
                                    )}
                                </button>
                            )}

                            <button
                                onClick={disconnectSession}
                                className="group flex items-center gap-3 px-8 py-4 bg-red-500 hover:bg-red-600 text-white rounded-full shadow-lg shadow-red-200 transition-all hover:scale-105 active:scale-95"
                            >
                                <StopCircle size={24} className="fill-current" />
                                <span className="font-semibold text-lg">End Session</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Floating Entry Point */}
            <div className={`fixed bottom-8 right-8 z-50 flex flex-col items-end gap-4 font-sans ${activeMode ? 'hidden' : ''}`}>

                {/* Popup Menu */}
                {isOpen && (
                    <div className="mb-6 mr-4 w-72 bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden animate-in slide-in-from-bottom-2 duration-200 origin-bottom-right">
                        <div className="p-3 bg-slate-50 border-b border-slate-100 flex justify-between items-center">
                            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider px-2">Choose Mode</span>
                            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-slate-600 p-1">
                                <X size={14} />
                            </button>
                        </div>
                        <div className="p-2 space-y-1">
                            {/* Option 1: Live Voice */}
                            <button
                                onClick={() => startSession('voice')}
                                className="w-full p-3 flex items-start gap-3 hover:bg-slate-50 rounded-xl transition-colors text-left group"
                            >
                                <div className="w-10 h-10 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
                                    <Mic size={20} />
                                </div>
                                <div>
                                    <h4 className="font-semibold text-slate-800 text-sm">Live Voice</h4>
                                    <p className="text-xs text-slate-500 leading-snug">Conversational mode. Share screen anytime.</p>
                                </div>
                            </button>

                            {/* Option 2: AI Avatar (Replaced Screen Share) */}
                            <button
                                onClick={() => startSession('avatar')}
                                className="w-full p-3 flex items-start gap-3 hover:bg-slate-50 rounded-xl transition-colors text-left group"
                            >
                                <div className="w-10 h-10 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
                                    <Bot size={20} />
                                </div>
                                <div>
                                    <h4 className="font-semibold text-slate-800 text-sm">AI Avatar</h4>
                                    <p className="text-xs text-slate-500 leading-snug">Interact with a visual AI assistant.</p>
                                </div>
                            </button>
                        </div>
                    </div>
                )}

                {/* 3D ROBOT BOT AVATAR (Floating Button) */}
                <button
                    onClick={() => setIsOpen(!isOpen)}
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                    className={`
                        relative group cursor-pointer transition-transform duration-300 hover:scale-105 active:scale-95 outline-none
                        ${isShaking ? 'animate-[gentle-shake_0.5s_ease-in-out]' : ''}
                    `}
                    style={{
                        animation: isShaking ? 'gentle-shake 0.5s ease-in-out' : 'none'
                    }}
                >
                    {/* Bot Body (White Glossy Egg Shape) */}
                    <div className="relative w-28 h-36 bg-gradient-to-b from-white via-slate-50 to-slate-300 rounded-[48%] shadow-[0_20px_40px_-10px_rgba(0,0,0,0.3),inset_0_-8px_8px_rgba(0,0,0,0.1),inset_0_4px_12px_rgba(255,255,255,1)] border border-white/60 flex flex-col items-center pt-8 z-20 overflow-hidden">

                        {/* Top Highlights (Head Gloss) */}
                        <div className="absolute top-2 left-1/2 -translate-x-1/2 w-16 h-8 bg-white/90 blur-md rounded-[50%] z-30 opacity-80"></div>
                        <div className="absolute top-5 left-1/2 -translate-x-1/2 w-20 h-20 bg-gradient-to-b from-white to-transparent opacity-60 rounded-full z-20"></div>

                        {/* The Face / Screen Area */}
                        <div className="relative w-20 h-16 bg-slate-950 rounded-[2rem] border-[3px] border-slate-800 shadow-[inset_0_0_15px_rgba(0,0,0,1)] flex items-center justify-center overflow-hidden z-30">
                            {/* Screen Glare */}
                            <div className="absolute top-2 right-3 w-6 h-3 bg-white/10 rotate-12 blur-[2px] rounded-full"></div>

                            {/* LED Text Content */}
                            <div className={`
                                font-mono text-[13px] font-black tracking-widest text-center leading-tight z-40
                                ${isOpen
                                    ? 'text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,1)]'
                                    : 'text-cyan-400 drop-shadow-[0_0_10px_rgba(34,211,238,1)] animate-pulse'}
                            `}>
                                {isOpen ? 'CLOSE' : <>LIVE<br />AI</>}
                            </div>

                            {/* Deep Blue Screen Ambience */}
                            <div className="absolute inset-0 bg-blue-500/10 blur-sm z-10"></div>
                        </div>

                        {/* Mid-Body Seam Line */}
                        <div className="w-full h-[1px] bg-slate-300/50 mt-5 shadow-sm z-20"></div>

                        {/* Bottom Reflection */}
                        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-16 h-8 bg-white/40 blur-xl rounded-full z-20"></div>
                    </div>

                    {/* Floating Arms (Sides) */}
                    <div className="absolute top-16 -left-4 w-6 h-16 bg-gradient-to-r from-slate-200 to-white rounded-full -rotate-12 shadow-[4px_4px_10px_rgba(0,0,0,0.1)] border border-white z-10 transition-transform group-hover:-translate-x-1 group-hover:-rotate-12"></div>
                    <div className="absolute top-16 -right-4 w-6 h-16 bg-gradient-to-l from-slate-200 to-white rounded-full rotate-12 shadow-[-4px_4px_10px_rgba(0,0,0,0.1)] border border-white z-10 transition-transform group-hover:translate-x-1 group-hover:rotate-12"></div>

                    {/* Shadow underneath */}
                    <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-16 h-4 bg-black/20 blur-md rounded-[50%] z-0 group-hover:scale-90 transition-transform"></div>
                </button>

                <style>{`
                    @keyframes gentle-shake {
                        0%, 100% { transform: rotate(0deg) scale(1) translateY(0); }
                        25% { transform: rotate(-3deg) scale(1.02) translateY(-2px); }
                        75% { transform: rotate(3deg) scale(1.02) translateY(-2px); }
                    }
                `}</style>
            </div>
        </>
    );
};

export default LiveAssistant;