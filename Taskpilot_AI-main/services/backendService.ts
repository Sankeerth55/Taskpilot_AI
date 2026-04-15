// TaskPilot AI Backend Service
// Connects frontend to the FastAPI backend with multi-agent orchestration

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const DEFAULT_REQUEST_TIMEOUT_MS = 30000;
const MESSAGE_REQUEST_TIMEOUT_MS = 70000;
const RETRY_DELAY_MS = 350;

const getConnectionError = (error: unknown, endpoint: string): Error => {
  const detail = error instanceof Error ? error.message : String(error);
  return new Error(
    `TaskPilot backend connection failed at ${API_BASE_URL}${endpoint}. ` +
    `Ensure FastAPI is running on http://127.0.0.1:8000. Details: ${detail}`
  );
};

const fetchWithTimeout = async (
  url: string,
  options: RequestInit,
  timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS
): Promise<Response> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }
};

const delay = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

const shouldRetryResponse = (response: Response): boolean => {
  return response.status === 429 || response.status >= 500;
};

const fetchWithRetry = async (
  url: string,
  options: RequestInit,
  timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS,
  retries: number = 2
): Promise<Response> => {
  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetchWithTimeout(url, options, timeoutMs);

      if (!shouldRetryResponse(response) || attempt === retries) {
        return response;
      }

      await delay(RETRY_DELAY_MS);
      continue;
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        lastError = new Error('Backend request timed out while waiting for a response.');
      } else {
        lastError = error;
      }
      if (attempt === retries) {
        throw lastError instanceof Error ? lastError : error;
      }
      await delay(RETRY_DELAY_MS);
    }
  }

  throw lastError instanceof Error ? lastError : new Error('Backend request failed after retry.');
};

export interface Session {
  id: string;
  title: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  session_id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface AgentStep {
  name: string;
  status: string;
  output: string;
  details?: Record<string, any>;
}

export interface StructuredAIOutput {
  fetched_context?: string;
  analysis?: string;
  plan?: string[];
  report?: string;
}

export interface AIResponse {
  session_id: string;
  message: Message;
  agent_summary: string | null;
  structured?: StructuredAIOutput;
  steps?: AgentStep[];
}

// Create a new session
export const createSession = async (title?: string): Promise<Session> => {
  try {
    const response = await fetchWithRetry(
      `${API_BASE_URL}/sessions`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: title || 'New Chat' }),
      },
      DEFAULT_REQUEST_TIMEOUT_MS,
      2
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error creating session:', error);
    throw getConnectionError(error, '/sessions');
  }
};

// Get all sessions
export const getSessions = async (): Promise<Session[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/sessions`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data.sessions || [];
  } catch (error) {
    console.error('Error fetching sessions:', error);
    throw getConnectionError(error, '/sessions');
  }
};

// Get session with messages
export const getSession = async (sessionId: string): Promise<Session & { messages: Message[] }> => {
  try {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching session:', error);
    throw getConnectionError(error, `/sessions/${sessionId}`);
  }
};

// Send a message
export const sendMessage = async (
  sessionId: string,
  content: string,
  attachments?: Array<{ mimeType: string; data: string; name?: string }>
): Promise<AIResponse> => {
  try {
    const attachmentPayload = (attachments || []).map((att) => ({
      mime_type: att.mimeType,
      data: att.data,
      filename: att.name,
    }));

    const response = await fetchWithRetry(
      `${API_BASE_URL}/messages`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          content,
          attachments: attachmentPayload.length > 0 ? attachmentPayload : undefined,
        }),
      },
      MESSAGE_REQUEST_TIMEOUT_MS,
      1
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Backend request timed out while processing the message.');
    }
    console.error('Error sending message:', error);
    throw getConnectionError(error, '/messages');
  }
};

// Send voice message
export const sendVoiceMessage = async (
  sessionId: string,
  transcript: string,
  screenContext?: string
): Promise<AIResponse> => {
  try {
    const response = await fetchWithRetry(
      `${API_BASE_URL}/voice`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          transcript,
          screen_context: screenContext,
        }),
      },
      MESSAGE_REQUEST_TIMEOUT_MS,
      1
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Backend voice request timed out.');
    }
    console.error('Error sending voice message:', error);
    throw getConnectionError(error, '/voice');
  }
};

// Store screen context
export const storeScreenContext = async (
  sessionId: string,
  context: string,
  metadata?: Record<string, string>
): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE_URL}/screen-context`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        context,
        metadata,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  } catch (error) {
    console.error('Error storing screen context:', error);
    throw getConnectionError(error, '/screen-context');
  }
};

// Check backend health
export const checkBackendHealth = async (): Promise<boolean> => {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/health/ping`,
        { method: 'GET' },
        5000
      );

      if (response.ok) {
        if (attempt > 0) {
          console.log('✅ Backend health check recovered on retry');
        } else {
          console.log('✅ Backend health check passed');
        }
        return true;
      }
      console.warn('⚠️ Backend returned non-OK status:', response.status);
    } catch (error) {
      console.warn('⚠️ Backend health check failed:', error instanceof Error ? error.message : 'Unknown error');
    }

    if (attempt === 0) {
      await delay(RETRY_DELAY_MS);
    }
  }

  return false;
};
