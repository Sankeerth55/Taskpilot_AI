import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Bot,
  Plus,
  MessageSquare,
  Search,
  Mic,
  ArrowUp,
  Paperclip,
  Menu,
  X,
  Sparkles,
  User,
  MoreHorizontal,
  Trash2,
  Edit2,
  FileText,
  UploadCloud
} from 'lucide-react';
import { Message, Sender, ChatSession, Attachment, MessageStatus, StorageSchema } from '../types';
import { sendMessageToGemini } from '../services/geminiService';
import {
  sendMessage as sendMessageToBackend,
  createSession as createBackendSession,
  checkBackendHealth,
  AIResponse
} from '../services/backendService';
import LiveAssistant from './LiveAssistant';
import { actionExecutor } from '../services/live/actionExecutor';

interface ChatInterfaceProps {
  onBack: () => void;
}

const STORAGE_KEY = 'taskpilot_sessions_v2';
const CURRENT_VERSION = 1;
const ALLOWED_FILE_MIME_TYPES = new Set([
  'application/pdf',
  'image/png',
  'image/jpeg'
]);
const ALLOWED_FILE_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg'];

// Helper to format date for grouping based on timestamp
const getSessionDateLabel = (timestamp: number): string => {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return 'Today';
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return 'Previous 7 Days';
};

// Voice Waveform Component
const VoiceVisualizer = () => (
  <div className="flex items-center gap-1 h-6 px-2">
    <div className="w-1 h-2 bg-red-500 rounded-full animate-[pulse_0.8s_ease-in-out_infinite]"></div>
    <div className="w-1 h-4 bg-red-500 rounded-full animate-[pulse_0.8s_ease-in-out_0.1s_infinite]"></div>
    <div className="w-1 h-6 bg-red-500 rounded-full animate-[pulse_0.8s_ease-in-out_0.2s_infinite]"></div>
    <div className="w-1 h-3 bg-red-500 rounded-full animate-[pulse_0.8s_ease-in-out_0.3s_infinite]"></div>
    <div className="w-1 h-5 bg-red-500 rounded-full animate-[pulse_0.8s_ease-in-out_0.4s_infinite]"></div>
    <span className="text-xs font-medium text-red-500 ml-2 animate-pulse">Listening...</span>
  </div>
);

const ChatInterface: React.FC<ChatInterfaceProps> = ({ onBack }) => {

  const extractAssistantText = (backendResponse: AIResponse): string => {
    const direct = backendResponse?.message?.content;
    if (typeof direct === 'string' && direct.trim()) return direct;

    const structured = backendResponse?.structured;
    if (structured?.report && structured.report.trim()) return structured.report;
    if (structured?.analysis && structured.analysis.trim()) return structured.analysis;
    if (structured?.fetched_context && structured.fetched_context.trim()) return structured.fetched_context;

    if (backendResponse?.agent_summary && backendResponse.agent_summary.trim()) {
      return backendResponse.agent_summary;
    }

    return "I processed your request, but could not generate a readable response. Please try again.";
  };

  const ensureVisibleResponse = (text: string): string => {
    if (typeof text === 'string' && text.trim()) return text;
    return "I processed your request, but the response was empty. Please try asking again.";
  };

  const isInstantGreeting = (text: string): boolean => {
    const normalized = text.trim().toLowerCase();
    if (!normalized) return false;
    const greetings = new Set([
      'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening',
      'greetings', 'hi there', 'hello there', 'hey there'
    ]);
    if (greetings.has(normalized)) return true;
    return /^(hi|hello|hey)(\s+[a-z0-9]+){0,2}$/.test(normalized);
  };

  const greetingReply = "Hello! I'm TaskPilot AI. How can I assist you today? I can help with real-time information, news, research, and much more!";

  const looksLikeAttachmentMiss = (text: string): boolean => {
    if (!text) return false;
    const normalized = text.toLowerCase();
    const markers = [
      'do not see an image attached',
      'do not see a document attached',
      'document was not attached',
      'please try uploading',
      'once the image is visible'
    ];
    return markers.some(marker => normalized.includes(marker));
  };

  const isGeminiAttachmentTemporaryFailure = (text: string): boolean => {
    if (!text) return true;
    const normalized = text.toLowerCase();
    const markers = [
      'temporarily rate-limited',
      'could not analyze the uploaded file',
      'needs a gemini api key',
      'gemini api key is missing',
      'backend is temporarily busy'
    ];
    return markers.some(marker => normalized.includes(marker));
  };

  // Helper function to render text with clickable markdown links
  const renderTextWithLinks = (text: string) => {
    if (!text) return null;

    // Split by markdown links [text](url) and regular URLs
    const parts: JSX.Element[] = [];
    let lastIndex = 0;

    // Match markdown links [text](url)
    const markdownLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g;
    // Match plain URLs (http/https, www, localhost, 127.0.0.1)
    const urlRegex = /(https?:\/\/[^\s<]+|www\.[^\s<]+|localhost:\d+[^\s<]*|127\.0\.0\.1:\d+[^\s<]*)/g;

    const normalizeUrl = (rawUrl: string) => {
      const cleaned = rawUrl.replace(/[\s\)\]\},.;]+$/, '');
      if (/^https?:\/\//i.test(cleaned)) return cleaned;
      return `http://${cleaned}`;
    };

    let match;
    const processedRanges: Array<{ start: number, end: number }> = [];

    // First, find all markdown links
    while ((match = markdownLinkRegex.exec(text)) !== null) {
      const fullMatch = match[0];
      const linkText = match[1];
      const url = match[2];
      const matchStart = match.index;
      const matchEnd = matchStart + fullMatch.length;

      // Add text before this link
      if (matchStart > lastIndex) {
        const beforeText = text.slice(lastIndex, matchStart);
        parts.push(<span key={`text-${lastIndex}`}>{beforeText}</span>);
      }

      // Add the clickable link
      parts.push(
        <a
          key={`link-${matchStart}`}
            href={normalizeUrl(url)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-500 hover:text-blue-600 underline hover:underline-offset-2 transition-colors font-medium"
        >
          {linkText}
        </a>
      );

      processedRanges.push({ start: matchStart, end: matchEnd });
      lastIndex = matchEnd;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      let remainingText = text.slice(lastIndex);

      // Now find plain URLs in the remaining text
      const urlParts: JSX.Element[] = [];
      let urlLastIndex = 0;

      while ((match = urlRegex.exec(remainingText)) !== null) {
        const rawUrl = match[1];
        const url = normalizeUrl(rawUrl);
        const matchStart = match.index;
        const matchEnd = matchStart + rawUrl.length;

        // Add text before URL
        if (matchStart > urlLastIndex) {
          urlParts.push(<span key={`url-text-${urlLastIndex}`}>{remainingText.slice(urlLastIndex, matchStart)}</span>);
        }

        // Add clickable URL
        urlParts.push(
          <a
            key={`plain-url-${matchStart}`}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-500 hover:text-blue-600 underline break-all"
          >
            {rawUrl}
          </a>
        );

        urlLastIndex = matchEnd;
      }

      // Add any remaining text after URLs
      if (urlLastIndex < remainingText.length) {
        urlParts.push(<span key={`url-text-end`}>{remainingText.slice(urlLastIndex)}</span>);
      }

      parts.push(<span key={`remaining-${lastIndex}`}>{urlParts.length > 0 ? urlParts : remainingText}</span>);
    }

    return parts.length > 0 ? <>{parts}</> : text;
  };

  const renderFormattedMessage = (text: string) => {
    const lines = text.split('\n');
    const elements: JSX.Element[] = [];

    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      if (!trimmed) {
        elements.push(<div key={`space-${idx}`} className="h-2" />);
        return;
      }

      if (trimmed.startsWith('### ')) {
        elements.push(<h4 key={`h3-${idx}`} className="text-base font-semibold text-slate-800">{trimmed.replace(/^###\s+/, '')}</h4>);
        return;
      }
      if (trimmed.startsWith('## ')) {
        elements.push(<h3 key={`h2-${idx}`} className="text-lg font-bold text-slate-800">{trimmed.replace(/^##\s+/, '')}</h3>);
        return;
      }
      if (trimmed.startsWith('# ')) {
        elements.push(<h2 key={`h1-${idx}`} className="text-xl font-bold text-slate-900">{trimmed.replace(/^#\s+/, '')}</h2>);
        return;
      }
      if (trimmed.startsWith('- ')) {
        elements.push(
          <div key={`li-${idx}`} className="flex gap-2 text-slate-700">
            <span className="mt-2 h-1.5 w-1.5 rounded-full bg-slate-400" />
            <span>{renderTextWithLinks(trimmed.replace(/^-\s+/, ''))}</span>
          </div>
        );
        return;
      }

      const orderedMatch = trimmed.match(/^(\d+)[\).\s]+(.+)$/);
      if (orderedMatch) {
        elements.push(
          <div key={`ol-${idx}`} className="flex gap-3 text-slate-700">
            <span className="mt-0.5 min-w-6 text-sm font-semibold text-slate-500">{orderedMatch[1]}.</span>
            <span className="flex-1 whitespace-pre-wrap">{renderTextWithLinks(orderedMatch[2])}</span>
          </div>
        );
        return;
      }

      const labelMatch = trimmed.match(/^(Price|Description|Rating|Book Now|Direct link|Link|Source):\s*(.+)$/i);
      if (labelMatch) {
        elements.push(
          <p key={`label-${idx}`} className="whitespace-pre-wrap text-slate-700 leading-relaxed">
            <span className="font-semibold text-slate-900">{labelMatch[1]}:</span> {renderTextWithLinks(labelMatch[2])}
          </p>
        );
        return;
      }

      elements.push(
        <p key={`p-${idx}`} className="whitespace-pre-wrap text-slate-700 leading-relaxed">
          {renderTextWithLinks(line)}
        </p>
      );
    });

    return <div className="space-y-1">{elements}</div>;
  };

  // --- STATE MANAGEMENT ---
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        // Handle migration from legacy array format if necessary
        if (Array.isArray(parsed)) {
          // Legacy migration: add updatedAt if missing
          return parsed.map((s: any) => ({
            ...s,
            updatedAt: s.updatedAt || s.createdAt
          }));
        }
        // Handle schema object
        if (parsed.version === CURRENT_VERSION && Array.isArray(parsed.sessions)) {
          return parsed.sessions;
        }
      }
      // Fallback for missing or corrupted data
      return [];
    } catch (e) {
      console.error("Failed to load sessions:", e);
      return [];
    }
  });

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Feature States
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [fileValidationError, setFileValidationError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [backendAvailable, setBackendAvailable] = useState(false);

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // --- DERIVED STATE ---
  const activeSession = useMemo(() =>
    sessions.find(s => s.id === activeSessionId),
    [sessions, activeSessionId]);

  const currentMessages = useMemo(() => {
    if (activeSession) return activeSession.messages;
    return [{
      id: 'welcome',
      sender: Sender.System,
      text: "Ready to pilot your tasks. Which agent do you need today?",
      timestamp: Date.now(),
      status: MessageStatus.Sent
    }];
  }, [activeSession]);

  // --- PERSISTENCE ---
  useEffect(() => {
    const data: StorageSchema = {
      version: CURRENT_VERSION,
      sessions: sessions
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }, [sessions]);

  useEffect(() => {
    scrollToBottom();
  }, [currentMessages.length, activeSessionId]);

  // Check backend availability on mount
  useEffect(() => {
    const checkBackend = async () => {
      const isAvailable = await checkBackendHealth();
      setBackendAvailable(isAvailable);
      if (isAvailable) {
        console.log('✅ TaskPilot AI Backend connected - using multi-agent orchestration');
      } else {
        console.log('⚠️  Backend unavailable - using direct Gemini API fallback');
        console.log('ℹ️  Make sure backend is running at http://127.0.0.1:8000');
        // Retry after 3 seconds
        setTimeout(async () => {
          const retryAvailable = await checkBackendHealth();
          if (retryAvailable && !isAvailable) {
            setBackendAvailable(true);
            console.log('✅ Backend connection established on retry');
          }
        }, 3000);
      }
    };
    checkBackend();

    // Keep probing so UI can recover automatically if backend starts later.
    const healthInterval = setInterval(async () => {
      const isAvailable = await checkBackendHealth();
      setBackendAvailable(isAvailable);
    }, 10000);

    return () => clearInterval(healthInterval);
  }, []);

  useEffect(() => {
    if (editingSessionId && renameInputRef.current) {
      renameInputRef.current.focus();
    }
  }, [editingSessionId]);

  // Click outside to close menus
  useEffect(() => {
    const handleClickOutside = () => setOpenMenuId(null);
    window.addEventListener('click', handleClickOutside);
    return () => window.removeEventListener('click', handleClickOutside);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // --- ACTIONS ---

  const handleNewChat = () => {
    setActiveSessionId(null);
    setInputValue('');
    setAttachments([]);
    setFileValidationError(null);
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  // --- SESSION MANAGEMENT ---
  const handleRenameStart = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(session.id);
    setRenameValue(session.title);
    setOpenMenuId(null);
  };

  const handleRenameSave = () => {
    if (editingSessionId) {
      setSessions(prev => prev.map(s =>
        s.id === editingSessionId ? { ...s, title: renameValue, updatedAt: Date.now() } : s
      ));
      setEditingSessionId(null);
    }
  };

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessions(prev => prev.filter(s => s.id !== sessionId));
    if (activeSessionId === sessionId) {
      setActiveSessionId(null);
    }
    setOpenMenuId(null);
  };

  const handleMenuToggle = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenMenuId(openMenuId === sessionId ? null : sessionId);
  };

  // --- MIC / SPEECH RECOGNITION ---
  const toggleMic = () => {
    if (isListening) {
      setIsListening(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false; // Stop after one sentence like ChatGPT
      recognition.interimResults = true; // Show results as we speak
      recognition.lang = 'en-US';

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);

      recognition.onresult = (event: any) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setInputValue(prev => {
            const trailingSpace = prev.length > 0 && !prev.endsWith(' ') ? ' ' : '';
            return prev + trailingSpace + finalTranscript;
          });
        }
      };

      recognition.start();
    } else {
      alert("Speech recognition is not supported in this browser.");
    }
  };

  // --- FILE HANDLING (Universal) ---
  const processFiles = (files: File[]) => {
    const acceptedFiles: File[] = [];
    const rejectedFiles: string[] = [];

    Array.from(files).forEach(file => {
      const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
      const extensionAllowed = ALLOWED_FILE_EXTENSIONS.includes(extension);
      const mimeAllowed = ALLOWED_FILE_MIME_TYPES.has(file.type);

      if (extensionAllowed || mimeAllowed) {
        acceptedFiles.push(file);
      } else {
        rejectedFiles.push(file.name);
      }
    });

    if (rejectedFiles.length > 0) {
      setFileValidationError(
        `Unsupported file type: ${rejectedFiles.join(', ')}. Only PDF and PNG/JPG/JPEG are allowed.`
      );
    } else {
      setFileValidationError(null);
    }

    acceptedFiles.forEach(file => {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setAttachments(prev => [...prev, {
            name: file.name,
            mimeType: file.type || 'application/octet-stream',
            data: event.target.result as string
          }]);
        }
      };
      reader.readAsDataURL(file);
    });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      processFiles(Array.from(e.target.files));
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === 'file') {
        const file = items[i].getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length > 0) {
      e.preventDefault(); // Prevent pasting the file name as text
      processFiles(files);
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  // --- DRAG AND DROP ---
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.currentTarget === e.target) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(Array.from(e.dataTransfer.files));
    }
  };

  // --- SEND MESSAGE ---
  const handleSendMessage = async () => {
    if ((!inputValue.trim() && attachments.length === 0) || isLoading) return;

    const userText = inputValue;
    const userAttachments = [...attachments];

    setInputValue('');
    setAttachments([]);
    setIsLoading(true);

    const now = Date.now();

    const newUserMessage: Message = {
      id: now.toString(),
      sender: Sender.User,
      text: userText,
      timestamp: now,
      status: MessageStatus.Pending,
      attachments: userAttachments
    };

    let sessionId = activeSessionId;
    let currentSessions = [...sessions];
    let session: ChatSession | undefined;

    if (!sessionId) {
      sessionId = now.toString();
      // Safe title generation
      const titleCandidate = userText.trim().split('\n')[0] || "New Conversation";
      const title = titleCandidate.length > 30 ? titleCandidate.slice(0, 30) + '...' : titleCandidate;

      session = {
        id: sessionId,
        title: title,
        createdAt: now,
        updatedAt: now,
        backendSessionId: undefined,
        messages: []
      };
      // Add new session to start
      currentSessions.unshift(session);
      setActiveSessionId(sessionId);
    } else {
      // Find existing session
      const index = currentSessions.findIndex(s => s.id === sessionId);
      if (index > -1) {
        session = { ...currentSessions[index], updatedAt: now };
        currentSessions.splice(index, 1);
        currentSessions.unshift(session);
      }
    }

    if (!session) return; // Should not happen

    // Update session with user message and thinking state
    const thinkingId = (now + 1).toString();
    const thinkingMessage: Message = {
      id: thinkingId,
      sender: Sender.Agent,
      text: "",
      timestamp: now + 1,
      status: MessageStatus.Pending,
      isThinking: true,
      thinkingStep: "Processing input...",
      stepProgress: { current: 1, total: 4 }
    };

    session.messages = [...session.messages, newUserMessage, thinkingMessage];
    setSessions(currentSessions);

    // Simulation of progress steps
    const steps = ["Analyzing intent...", "Checking knowledge base...", "Synthesizing response..."];
    let stepIndex = 0;

    const progressInterval = setInterval(() => {
      stepIndex++;
      if (stepIndex < steps.length) {
        setSessions(prev => prev.map(s => {
          if (s.id === sessionId) {
            return {
              ...s,
              messages: s.messages.map(m =>
                m.id === thinkingId
                  ? { ...m, thinkingStep: steps[stepIndex], stepProgress: { current: stepIndex + 1, total: 4 } }
                  : m
              )
            };
          }
          return s;
        }));
      }
    }, 800);

    try {
      let responseText = '';
      let agentSteps: any[] = [];

      const historyContext = session.messages
        .filter(m => !m.isThinking && m.id !== thinkingId && m.id !== newUserMessage.id)
        .map(m => ({
          role: m.sender === Sender.User ? 'user' : 'model',
          parts: [
            { text: m.text },
            ...(m.attachments?.map(att => ({
              inlineData: { mimeType: att.mimeType, data: att.data.split(',')[1] }
            })) || [])
          ]
        }));

      // Gemini-first is restricted to file/image turns. Text chat stays backend-first
      // so users do not see rate-limit messages from direct Gemini calls.
      const preferDirectGemini = userAttachments.length > 0;

      // For uploaded files, prefer Gemini multimodal first.
      if (preferDirectGemini) {
        const geminiResponse = ensureVisibleResponse(
          await sendMessageToGemini(userText, historyContext, userAttachments)
        );

        if (!isGeminiAttachmentTemporaryFailure(geminiResponse)) {
          responseText = geminiResponse;
        }
      }

      // Fast-path greeting on the client to avoid any backend wait.
      if (!responseText && userAttachments.length === 0 && isInstantGreeting(userText)) {
        responseText = greetingReply;
      }

      if (responseText) {
        clearInterval(progressInterval);

        setSessions(prev => prev.map(s => {
          if (s.id === sessionId) {
            const filteredMessages = s.messages.filter(m => m.id !== thinkingId);
            const updatedMessages = filteredMessages.map(m =>
              m.id === newUserMessage.id ? { ...m, status: MessageStatus.Sent } : m
            );

            const newAgentMessage: Message = {
              id: (Date.now() + 2).toString(),
              sender: Sender.Agent,
              text: responseText,
              timestamp: Date.now() + 2,
              status: MessageStatus.Sent,
            };

            return {
              ...s,
              updatedAt: Date.now(),
              messages: [...updatedMessages, newAgentMessage]
            };
          }
          return s;
        }));

        return;
      }

      const forceBackend = userAttachments.length === 0;
      let useBackend = forceBackend || backendAvailable;

      // If the initial probe failed, re-check at send-time before falling back.
      if (!useBackend) {
        const isAvailableNow = await checkBackendHealth();
        if (isAvailableNow) {
          setBackendAvailable(true);
          useBackend = true;
          console.log('✅ Backend recovered at send time, using multi-agent orchestration');
        }
      }

      if (useBackend) {
        // Use TaskPilot AI Backend with multi-agent orchestration
        let currentBackendSessionId = session?.backendSessionId || null;

        // Create backend session for this local chat if missing.
        if (!currentBackendSessionId) {
          const backendSession = await createBackendSession(session?.title || 'New Chat');
          currentBackendSessionId = backendSession.id;
          setSessions(prev => prev.map(s =>
            s.id === sessionId ? { ...s, backendSessionId: currentBackendSessionId! } : s
          ));
        }

        // Send message to backend
        let backendResponse: AIResponse;
        try {
          backendResponse = await sendMessageToBackend(
            currentBackendSessionId!,
            userText,
            userAttachments
          );
        } catch (backendError) {
          // If backend session became stale/invalid, create a fresh one and retry once.
          const detail = backendError instanceof Error ? backendError.message : String(backendError);
          if (detail.includes('404')) {
            const freshBackendSession = await createBackendSession(session?.title || 'New Chat');
            currentBackendSessionId = freshBackendSession.id;
            setSessions(prev => prev.map(s =>
              s.id === sessionId ? { ...s, backendSessionId: currentBackendSessionId! } : s
            ));
            backendResponse = await sendMessageToBackend(
              currentBackendSessionId,
              userText,
              userAttachments
            );
          } else {
            throw backendError;
          }
        }

        responseText = ensureVisibleResponse(extractAssistantText(backendResponse));
        agentSteps = backendResponse.steps || [];

        // If backend misses attachment context, fall back to Gemini multimodal for this turn.
        if (userAttachments.length > 0 && looksLikeAttachmentMiss(responseText)) {
          responseText = ensureVisibleResponse(
            await sendMessageToGemini(userText, historyContext, userAttachments)
          );
        }

        // CRITICAL DEBUG: Log response text
        console.log('📝 Response Text Length:', responseText.length);
        console.log('📝 Response Text Preview:', responseText.substring(0, 200));
        console.log('📝 Full Backend Response:', JSON.stringify(backendResponse, null, 2).substring(0, 500));

        // Log agent activity for debugging
        if (backendResponse.agent_summary) {
          console.log('🤖 Agent Summary:', backendResponse.agent_summary);
        }
        if (backendResponse.structured) {
          console.log('📊 Structured Output:', backendResponse.structured);
          // Check for screen actions
          const structuredData = backendResponse.structured as any;
          if (structuredData.screen_action) {
            const action = structuredData.screen_action;
            console.log("🚀 Executing Screen Action:", action);

            if (action.action === 'scroll') {
              actionExecutor.scroll(action.target || 'down', action.value === 'page' ? 'page' : parseInt(action.value));
            } else if (action.action === 'type') {
              actionExecutor.typeText(action.value);
            } else if (action.action === 'click') {
              actionExecutor.click(action.target);
            } else if (action.action === 'read') {
              // We can't easily return the read text back to the chat context in this turn 
              // without a follow-up request, but we can at least trigger the read log
              actionExecutor.getVisibleText().then(text => {
                console.log("Read text:", text.substring(0, 100) + "...");
              });
            }
          }
        }
      } else {
        // Fallback to direct Gemini API
        responseText = ensureVisibleResponse(await sendMessageToGemini(userText, historyContext, userAttachments));
      }

      clearInterval(progressInterval);

      setSessions(prev => prev.map(s => {
        if (s.id === sessionId) {
          // Remove thinking message
          const filteredMessages = s.messages.filter(m => m.id !== thinkingId);

          // Mark user message as sent
          const updatedMessages = filteredMessages.map(m =>
            m.id === newUserMessage.id ? { ...m, status: MessageStatus.Sent } : m
          );

          const newAgentMessage: Message = {
            id: (Date.now() + 2).toString(),
            sender: Sender.Agent,
            text: responseText,
            timestamp: Date.now() + 2,
            status: MessageStatus.Sent,
            structuredData: responseText.includes("HubSpot") || responseText.includes("Startups")
              ? [
                { title: "HubSpot CRM", description: "Best for scaling. Free tier available.", color: "bg-cyan-400" },
                { title: "Pipedrive", description: "Visual sales pipeline focus.", color: "bg-pink-400" }
              ]
              : undefined
          };
          // CRITICAL DEBUG: Log the agent message being created
          console.log('💬 Creating Agent Message:', {
            id: newAgentMessage.id,
            sender: newAgentMessage.sender,
            textLength: newAgentMessage.text?.length || 0,
            textPreview: newAgentMessage.text?.substring(0, 100) || 'EMPTY'
          });

          return {
            ...s,
            updatedAt: Date.now(),
            messages: [...updatedMessages, newAgentMessage]
          };
        }
        return s;
      }));

    } catch (error) {
      clearInterval(progressInterval);
      console.error("Chat Error:", error);

      // If backend was supposed to be available but failed, try fallback
      let fallbackResponse = '';
      if (backendAvailable && error instanceof Error) {
        console.warn('🔄 Backend request failed, attempting Gemini API fallback...');
        setBackendAvailable(false);
        try {
          const historyContext = session.messages
            .filter(m => !m.isThinking && m.id !== thinkingId && m.id !== newUserMessage.id)
            .map(m => ({
              role: m.sender === Sender.User ? 'user' : 'model',
              parts: [{ text: m.text }]
            }));
          fallbackResponse = ensureVisibleResponse(await sendMessageToGemini(userText, historyContext, userAttachments));
        } catch (fallbackError) {
          console.error('Fallback also failed:', fallbackError);
        }
      }

      if (fallbackResponse) {
        // Use fallback response
        setSessions(prev => prev.map(s => {
          if (s.id === sessionId) {
            const filteredMessages = s.messages.filter(m => m.id !== thinkingId);
            const updatedMessages = filteredMessages.map(m =>
              m.id === newUserMessage.id ? { ...m, status: MessageStatus.Sent } : m
            );
            const newAgentMessage: Message = {
              id: (Date.now() + 2).toString(),
              sender: Sender.Agent,
              text: fallbackResponse,
              timestamp: Date.now() + 2,
              status: MessageStatus.Sent,
            };
            return {
              ...s,
              updatedAt: Date.now(),
              messages: [...updatedMessages, newAgentMessage]
            };
          }
          return s;
        }));
      } else {
        // Update state to remove thinking message and mark user message as error
        setSessions(prev => prev.map(s => {
          if (s.id === sessionId) {
            const failedMessages = s.messages
              .filter(m => m.id !== thinkingId)
              .map(m => m.id === newUserMessage.id ? { ...m, status: MessageStatus.Error } : m);

            const systemErrorMessage: Message = {
              id: (Date.now() + 3).toString(),
              sender: Sender.System,
              text: `I could not process that request right now. Error details: ${error instanceof Error ? error.message : String(error)}`,
              timestamp: Date.now() + 3,
              status: MessageStatus.Sent,
            };

            return {
              ...s,
              messages: [...failedMessages, systemErrorMessage]
            };
          }
          return s;
        }));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Grouping logic based on sorting
  const groupedSessions = useMemo(() => {
    // Sort sessions by updatedAt descending first
    const sortedSessions = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);

    const groups: { [key: string]: ChatSession[] } = {
      'Today': [],
      'Yesterday': [],
      'Previous 7 Days': []
    };

    sortedSessions.forEach(session => {
      const label = getSessionDateLabel(session.updatedAt);
      if (groups[label]) {
        groups[label].push(session);
      } else {
        // Fallback for older than 7 days if strictly following label, 
        // or put everything else in "Previous 7 Days" container for this UI 
        // (assuming UI only has these 3 buckets)
        if (!groups['Previous 7 Days']) groups['Previous 7 Days'] = [];
        groups['Previous 7 Days'].push(session);
      }
    });
    return groups;
  }, [sessions]);

  return (
    <div
      className="flex h-screen bg-[#F3F5FA] overflow-hidden font-sans relative"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Live Assistant Add-on */}
      <LiveAssistant />

      {/* Drag Overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-[60] bg-white/80 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <div className="bg-white p-8 rounded-2xl shadow-2xl border-2 border-dashed border-indigo-400 flex flex-col items-center animate-bounce">
            <UploadCloud size={64} className="text-indigo-500 mb-4" />
            <h3 className="text-2xl font-bold text-slate-700">Drop files here</h3>
            <p className="text-slate-500 mt-2">Add attachments to your chat</p>
          </div>
        </div>
      )}

      {/* Mobile Menu Overlay */}
      {!isSidebarOpen && (
        <div className="fixed top-4 left-4 z-50 md:hidden">
          <button onClick={() => setIsSidebarOpen(true)} className="p-2 bg-white rounded-lg shadow-sm">
            <Menu size={20} />
          </button>
        </div>
      )}

      {/* Sidebar */}
      <aside
        className={`
            fixed md:relative z-40 h-full w-[280px] bg-[#fcfcfd] border-r border-slate-100 flex flex-col transition-transform duration-300
            ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-0 md:opacity-0 md:overflow-hidden'}
        `}
      >
        <div className="p-4 flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between mb-8 px-2">
            <div onClick={onBack} className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity">
              <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-purple-200">
                <Bot size={20} />
              </div>
              <span className="font-bold text-slate-800 tracking-tight">TaskPilot AI</span>
            </div>
            <button onClick={() => setIsSidebarOpen(false)} className="md:hidden text-slate-400">
              <X size={20} />
            </button>
          </div>

          {/* New Chat Button */}
          <button
            onClick={handleNewChat}
            className="w-full py-3 px-4 rounded-full bg-gradient-to-r from-[#2DD4BF] to-[#818CF8] hover:from-[#2cc1ae] hover:to-[#737df5] text-white font-medium shadow-md shadow-indigo-200 flex items-center justify-center gap-2 transition-all active:scale-95 mb-8"
          >
            <Plus size={18} />
            <span>New Chat</span>
          </button>

          {/* History List */}
          <div className="flex-1 overflow-y-auto pr-2 space-y-6 scrollbar-hide">
            {['Today', 'Yesterday', 'Previous 7 Days'].map(groupLabel => {
              const groupItems = groupedSessions[groupLabel];
              if (!groupItems || groupItems.length === 0) return null;

              return (
                <div key={groupLabel}>
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-3 mb-3">{groupLabel}</h3>
                  <div className="space-y-1">
                    {groupItems.map(s => (
                      <div key={s.id} className="relative group">
                        {editingSessionId === s.id ? (
                          <div className="px-3 py-2">
                            <input
                              ref={renameInputRef}
                              type="text"
                              value={renameValue}
                              onChange={(e) => setRenameValue(e.target.value)}
                              onBlur={handleRenameSave}
                              onKeyDown={(e) => e.key === 'Enter' && handleRenameSave()}
                              className="w-full text-sm bg-white border border-indigo-200 rounded px-2 py-1 outline-none focus:border-indigo-400 text-slate-700"
                            />
                          </div>
                        ) : (
                          <button
                            onClick={() => { setActiveSessionId(s.id); if (window.innerWidth < 768) setIsSidebarOpen(false); }}
                            className={`w-full text-left px-3 py-2.5 rounded-lg text-sm flex items-center gap-3 transition-colors pr-8 relative
                                                    ${activeSessionId === s.id ? 'bg-slate-100 text-slate-800 font-medium' : 'text-slate-600 hover:bg-slate-50'}
                                                `}
                          >
                            <MessageSquare size={16} className={`flex-shrink-0 ${activeSessionId === s.id ? 'text-indigo-500' : 'text-slate-400'}`} />
                            <span className="truncate">{s.title}</span>

                            {/* Context Menu Trigger */}
                            <div
                              onClick={(e) => handleMenuToggle(s.id, e)}
                              className={`absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md hover:bg-slate-200 transition-opacity
                                                        ${openMenuId === s.id ? 'opacity-100 bg-slate-200' : 'opacity-0 group-hover:opacity-100'}
                                                    `}
                            >
                              <MoreHorizontal size={14} className="text-slate-500" />
                            </div>
                          </button>
                        )}

                        {/* Dropdown Menu */}
                        {openMenuId === s.id && !editingSessionId && (
                          <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg shadow-lg border border-slate-100 z-50 overflow-hidden py-1">
                            <button
                              onClick={(e) => handleRenameStart(s, e)}
                              className="w-full text-left px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 flex items-center gap-2"
                            >
                              <Edit2 size={12} /> Rename
                            </button>
                            <button
                              onClick={(e) => handleDeleteSession(s.id, e)}
                              className="w-full text-left px-3 py-2 text-xs text-red-500 hover:bg-red-50 flex items-center gap-2"
                            >
                              <Trash2 size={12} /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col relative h-full">
        {/* Toggle Sidebar Button (Desktop) */}
        {!isSidebarOpen && (
          <div className="absolute top-6 left-6 z-30 hidden md:block">
            <button onClick={() => setIsSidebarOpen(true)} className="p-2 bg-white/50 backdrop-blur rounded-lg hover:bg-white text-slate-500 transition-all">
              <Menu size={20} />
            </button>
          </div>
        )}

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 pt-8 pb-32">
          <div className="max-w-3xl mx-auto space-y-8">
            {currentMessages.map((msg, index) => (
              <div key={msg.id} className={`flex gap-4 ${msg.sender === Sender.User ? 'justify-end' : 'justify-start'}`}>
                {/* Avatar for System/Agent */}
                {msg.sender !== Sender.User && (
                  <div className="w-8 h-8 rounded-full bg-white shadow-sm flex items-center justify-center flex-shrink-0 mt-1">
                    {msg.sender === Sender.System ? (
                      <Bot size={16} className="text-indigo-500" />
                    ) : (
                      <Sparkles size={16} className="text-purple-500" />
                    )}
                  </div>
                )}

                {/* Message Content */}
                <div className={`max-w-[85%] space-y-2 ${msg.sender === Sender.User ? 'flex flex-col items-end' : ''}`}>
                  {msg.sender === Sender.System && (
                    <span className="text-xs text-slate-400 ml-1">TaskPilot System</span>
                  )}
                  {msg.sender === Sender.Agent && !msg.isThinking && (
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs font-medium text-slate-600 mb-1">
                      <Search size={12} />
                      TaskPilot AI
                    </div>
                  )}

                  {/* Actual Bubble */}
                  <div className={`
                                p-5 rounded-2xl shadow-sm leading-relaxed
                                ${msg.sender === Sender.User
                      ? 'bg-white text-slate-800 rounded-br-sm border border-slate-100'
                      : msg.sender === Sender.System
                        ? 'bg-white/60 text-slate-600 backdrop-blur-sm border border-slate-100/50 rounded-tl-sm'
                        : 'bg-white text-slate-800 rounded-tl-sm border border-slate-100 w-full'
                    }
                                ${msg.status === MessageStatus.Error ? 'border-red-300 bg-red-50' : ''}
                            `}>
                    {/* Attachments Display within Bubble */}
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="mb-3 flex flex-wrap gap-2">
                        {msg.attachments.map((att, i) => (
                          <div key={i} className="relative group rounded-lg overflow-hidden border border-slate-200 bg-slate-50">
                            {att.mimeType.startsWith('image/') ? (
                              <img src={att.data} alt="attachment" className="h-32 w-auto object-cover" />
                            ) : (
                              <div className="h-20 w-32 flex flex-col items-center justify-center gap-1 text-slate-500 p-2">
                                <FileText size={24} />
                                <span className="text-[10px] truncate w-full text-center">{att.name}</span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {msg.isThinking ? (
                      // Thinking State UI
                      <div className="w-full min-w-[300px]">
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></div>
                            <span className="text-sm font-medium text-slate-700">{msg.thinkingStep}</span>
                          </div>
                          <span className="text-xs text-slate-400">Step {msg.stepProgress?.current} of {msg.stepProgress?.total}</span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden mb-6">
                          <div
                            className="h-full bg-gradient-to-r from-blue-400 to-purple-400 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${((msg.stepProgress?.current || 0) / (msg.stepProgress?.total || 1)) * 100}%` }}
                          ></div>
                        </div>
                        <div className="flex justify-center gap-2">
                          {[1, 2, 3, 4, 5].map(step => (
                            <div key={step} className={`w-1.5 h-1.5 rounded-full ${step === msg.stepProgress?.current ? 'bg-blue-400' : 'bg-slate-200'}`}></div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      // Normal Text Content with Clickable Links
                      <div className="prose prose-sm prose-slate max-w-none">
                        {renderFormattedMessage(msg.text)}

                        {/* Structured Data View */}
                        {msg.structuredData && (
                          <div className="mt-6 space-y-4">
                            {msg.structuredData.map((item, idx) => (
                              <div key={idx} className="flex gap-4 p-3 hover:bg-slate-50 rounded-lg transition-colors">
                                <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${item.color}`}></div>
                                <div>
                                  <h4 className="font-semibold text-slate-800">{item.title}</h4>
                                  <p className="text-slate-600 text-sm mt-1">{item.description}</p>
                                </div>
                              </div>
                            ))}
                            <div className="flex items-center gap-2 text-xs text-blue-400 mt-4 pl-1 font-medium cursor-pointer hover:underline">
                              <div className="flex gap-1">
                                <span className="w-1 h-1 rounded-full bg-blue-400"></span>
                                <span className="w-1 h-1 rounded-full bg-purple-400"></span>
                                <span className="w-1 h-1 rounded-full bg-indigo-400"></span>
                              </div>
                              Synthesizing more data...
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* User Avatar */}
                  {msg.sender === Sender.User && (
                    <div className="absolute top-1/2 -right-12 w-8 h-8 rounded-full bg-slate-300 flex items-center justify-center text-white text-xs ring-2 ring-white shadow-sm opacity-50">
                      <User size={16} />
                    </div>
                  )}

                  {/* Error Status Indicator */}
                  {msg.status === MessageStatus.Error && (
                    <div className="absolute -bottom-6 right-0 text-xs text-red-500 font-medium">
                      Failed to send. Please try again.
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-[#F3F5FA] via-[#F3F5FA] to-transparent">
          <div className="max-w-3xl mx-auto relative">

            {/* Attachment Previews (Above Input) */}
            {attachments.length > 0 && (
              <div className="flex gap-2 mb-2 px-2 overflow-x-auto pb-2">
                {attachments.map((att, i) => (
                  <div key={i} className="relative group bg-white p-1 rounded-lg border border-slate-200 shadow-sm flex-shrink-0">
                    {att.mimeType.startsWith('image/') ? (
                      <img src={att.data} alt="preview" className="h-16 w-16 object-cover rounded-md" />
                    ) : (
                      <div className="h-16 w-16 bg-slate-50 rounded-md flex flex-col items-center justify-center gap-1 text-slate-400">
                        <FileText size={20} />
                        <span className="text-[8px] max-w-full truncate px-1">{att.name}</span>
                      </div>
                    )}
                    <button
                      onClick={() => removeAttachment(i)}
                      className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 shadow-md hover:bg-red-600 transition-colors"
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="relative group">
              <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-300 via-purple-300 to-indigo-300 rounded-full opacity-20 transition duration-500 blur"></div>
              <div className={`
                        relative bg-white/80 backdrop-blur-xl rounded-full flex items-center p-2 shadow-lg ring-1 ring-white/50 transition-all duration-300
                        ${isListening ? 'ring-red-400 bg-red-50/50' : ''}
                    `}>

                {/* Hidden File Input (Restricted to PDF + images) */}
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                  onChange={handleFileSelect}
                />

                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="p-3 text-slate-400 hover:text-slate-600 transition-colors"
                  title="Attach File"
                >
                  <Paperclip size={20} />
                </button>

                {isListening ? (
                  <div className="flex-1 flex items-center justify-center">
                    <VoiceVisualizer />
                  </div>
                ) : (
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onPaste={handlePaste}
                    placeholder="Ask TaskPilot..."
                    className="chat-text-input flex-1 bg-transparent border-none outline-none text-slate-700 placeholder-slate-400 px-4 py-2 font-medium"
                    disabled={isLoading}
                  />
                )}

                <button
                  onClick={toggleMic}
                  className={`p-3 transition-colors ${isListening ? 'text-red-500 bg-red-100 rounded-full' : 'text-slate-400 hover:text-slate-600'}`}
                  title="Voice Input"
                >
                  <Mic size={20} />
                </button>

                <button
                  onClick={handleSendMessage}
                  disabled={(!inputValue.trim() && attachments.length === 0) || isLoading}
                  className={`
                                p-3 rounded-full text-white shadow-md transition-all duration-300 ml-1
                                ${(inputValue.trim() || attachments.length > 0)
                      ? 'bg-gradient-to-r from-blue-500 to-purple-600 hover:scale-105'
                      : 'bg-slate-300 cursor-not-allowed'}
                            `}
                >
                  <ArrowUp size={20} />
                </button>

              </div>
            </div>
            {fileValidationError && (
              <div className="text-center mt-2">
                <span className="text-[11px] text-red-500 font-medium">{fileValidationError}</span>
              </div>
            )}
            <div className="text-center mt-3">
              <span className="text-[10px] text-slate-400 font-medium">TaskPilot can make mistakes. Please verify important information.</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ChatInterface;