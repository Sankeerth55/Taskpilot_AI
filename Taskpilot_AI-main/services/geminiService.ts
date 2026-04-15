import { GoogleGenAI, GenerateContentResponse } from "@google/genai";
import { Attachment } from "../types";

// Initialize Gemini AI Client
const ENV = (import.meta as any).env || {};
const apiKey = ENV.VITE_GEMINI_API_KEY || ENV.GEMINI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey: apiKey || 'dummy_key' });

const SYSTEM_INSTRUCTION = `You are TaskPilot, an advanced multi-agent orchestration system. 
You are helpful, precise, and professional.
When appropriate, format your responses to look like structured data analysis.
Use bullet points effectively.
If asked about CRM tools or similar comparisons, provide a structured list.
Keep responses concise but informative.
`;

interface HistoryItem {
  role: string;
  parts: Array<{ text?: string; inlineData?: { mimeType: string; data: string } }>;
}

const wait = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

const isRateLimitError = (error: unknown): boolean => {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return msg.includes('quota') || msg.includes('429') || msg.includes('rate');
};

export const sendMessageToGemini = async (
  message: string,
  history: HistoryItem[],
  attachments: Attachment[] = []
): Promise<string> => {
  try {
    if (!apiKey) {
      return attachments.length > 0
        ? "File analysis needs a Gemini API key. Add VITE_GEMINI_API_KEY (or GEMINI_API_KEY) in your frontend .env file and restart the app."
        : "Gemini API key is missing. Add VITE_GEMINI_API_KEY (or GEMINI_API_KEY) in your frontend .env file and restart the app.";
    }

    // Use the stable model that supports vision/multimodal
    const modelSetting = ENV.VITE_GEMINI_MODEL || ENV.GEMINI_MODEL || 'auto';
    const modelCandidates = modelSetting.toLowerCase() === 'auto'
      ? ['gemini-2.0-flash', 'gemini-1.5-flash']
      : [modelSetting];
    
    // Construct the chat including history
    const createChat = (modelName: string) => ai.chats.create({
      model: modelName,
      config: {
        systemInstruction: `${SYSTEM_INSTRUCTION}\nWhen files are attached, treat them as the source of truth. Summarize the file, answer user questions from file evidence, and explain content clearly. If the user message is empty, provide a concise summary of the uploaded file.`
      },
      history: history.map(h => ({
        role: h.role === 'user' ? 'user' : 'model',
        parts: h.parts
      }))
    });

    // Construct the current message parts
    const prompt = message && message.trim()
      ? message
      : attachments.length > 0
        ? 'Please summarize the uploaded file and explain the key points.'
        : 'Answer the user directly and concisely.';
    const currentParts: any[] = [{ text: prompt }];
    
    // Add attachments if they exist
    attachments.forEach(att => {
      // Remove base64 header if present (data:image/png;base64,)
      const base64Data = att.data.split(',')[1] || att.data;
      currentParts.push({
        inlineData: {
          mimeType: att.mimeType,
          data: base64Data
        }
      });
    });

    const retryDelays = [0, 1200, 2500];
    let lastError: unknown = null;

    for (const modelName of modelCandidates) {
      const chat = createChat(modelName);
      for (let attempt = 0; attempt < retryDelays.length; attempt++) {
        if (retryDelays[attempt] > 0) {
          await wait(retryDelays[attempt]);
        }

        try {
          const result: GenerateContentResponse = await chat.sendMessage(currentParts as any);
          return result.text || "I processed your request but could not generate a text response.";
        } catch (error) {
          lastError = error;
          if (!isRateLimitError(error)) {
            break;
          }
        }
      }
    }

    throw lastError;
  } catch (error) {
    console.error("Gemini API Error:", error);
    // Check if it's a quota error
    if (isRateLimitError(error)) {
      return attachments.length > 0
        ? "File analysis is temporarily rate-limited. Please retry in a few minutes, or try the same question again so backend processing can handle it."
        : "The AI service is temporarily rate-limited. Please retry in a few minutes, or try again so backend processing can handle it.";
    }
    return attachments.length > 0
      ? "I could not analyze the uploaded file right now. Please try again in a moment."
      : "I could not answer right now. Please try again in a moment.";
  }
};