import axios from 'axios';
import type { Task, HealthStatus, ToolInfo } from '../types';

const API_BASE_URL = '/api';

// Get control token from sessionStorage (set by Tauri on launch)
const getControlToken = () => {
  return sessionStorage.getItem('jarvis_control_token') || '';
};

// Create axios instance with authentication
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add control token to all requests
apiClient.interceptors.request.use((config) => {
  const token = getControlToken();
  if (token) {
    config.headers['X-Control-Token'] = token;
  }
  return config;
});

export const healthService = {
  check: async (): Promise<HealthStatus> => {
    const response = await apiClient.get('/health');
    return response.data;
  },
};

export const taskService = {
  list: async (): Promise<Task[]> => {
    const response = await apiClient.get('/tasks');
    return response.data.tasks || [];
  },

  get: async (taskId: string): Promise<Task> => {
    const response = await apiClient.get(`/tasks/${taskId}`);
    return response.data;
  },

  create: async (originalRequest: string): Promise<Task> => {
    const response = await apiClient.post('/tasks', { original_request: originalRequest });
    return response.data;
  },

  cancel: async (taskId: string): Promise<void> => {
    await apiClient.post(`/tasks/${taskId}/cancel`);
  },

  resume: async (taskId: string): Promise<Task> => {
    const response = await apiClient.post(`/tasks/${taskId}/resume`);
    return response.data;
  },

  reply: async (taskId: string, answer: string): Promise<Task> => {
    const response = await apiClient.post(`/tasks/${taskId}/reply`, { answer });
    return response.data;
  },
};

export const voiceService = {
  startSession: async (): Promise<string> => {
    // For now, generate a client-side session ID
    // In production, this would call the backend to start a session
    return crypto.randomUUID();
  },

  endSession: async (sessionId: string): Promise<void> => {
    // Client-side cleanup - backend session ends automatically
    console.log(`Voice session ended: ${sessionId}`);
  },

  transcribeAudio: async (audioData: Uint8Array): Promise<{ text: string }> => {
    // Convert to blob and send to backend
    const blob = new Blob([audioData], { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('audio', blob, 'recording.wav');

    const response = await fetch(`${API_BASE_URL}/voice/transcribe`, {
      method: 'POST',
      headers: {
        'X-Control-Token': getControlToken() || '',
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Transcription failed: ${response.statusText}`);
    }

    return response.json();
  },
};

export const toolService = {
  list: async (): Promise<ToolInfo[]> => {
    const response = await apiClient.get('/tools');
    return response.data.tools || [];
  },
};

export const settingsService = {
  get: async (): Promise<Record<string, string>> => {
    const response = await apiClient.get('/settings');
    return response.data.settings || {};
  },

  update: async (key: string, value: string): Promise<void> => {
    await apiClient.put('/settings', { key, value });
  },
};

export default apiClient;
