export enum Sender {
  User = 'user',
  System = 'system',
  Agent = 'agent'
}

export enum MessageStatus {
  Pending = 'pending',
  Sent = 'sent',
  Error = 'error'
}

export interface Attachment {
  name: string;
  mimeType: string;
  data: string; // Base64 string
}

export interface Message {
  id: string;
  text: string;
  sender: Sender;
  timestamp: number;
  status?: MessageStatus;
  attachments?: Attachment[];
  // Optional metadata for rich UI states
  isThinking?: boolean;
  thinkingStep?: string;
  stepProgress?: { current: number; total: number };
  structuredData?: Array<{ title: string; description: string; color: string }>;
}

export interface ChatSession {
  id: string;
  title: string;
  // date field removed in favor of dynamic grouping based on timestamps
  createdAt: number;
  updatedAt: number;
  backendSessionId?: string;
  messages: Message[];
}

export interface StorageSchema {
  version: number;
  sessions: ChatSession[];
}

export enum AppView {
  Landing = 'landing',
  Chat = 'chat'
}

// Add global type for Web Speech API
declare global {
  interface Window {
    webkitSpeechRecognition: any;
    SpeechRecognition: any;
    webkitAudioContext: typeof AudioContext;
  }
}