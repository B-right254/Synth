import { create } from 'zustand';
import type { Task, HealthStatus } from '../types';

interface AppState {
  // Tasks
  tasks: Task[];
  activeTaskId: string | null;
  isLoading: boolean;
  error: string | null;
  
  // Health
  healthStatus: HealthStatus | null;
  isConnected: boolean;
  
  // Voice
  isVoiceEnabled: boolean;
  isRecording: boolean;
  
  // Actions
  setTasks: (tasks: Task[]) => void;
  setActiveTask: (taskId: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setHealthStatus: (status: HealthStatus | null) => void;
  setConnected: (connected: boolean) => void;
  setVoiceEnabled: (enabled: boolean) => void;
  setRecording: (recording: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  tasks: [],
  activeTaskId: null,
  isLoading: false,
  error: null,
  healthStatus: null,
  isConnected: false,
  isVoiceEnabled: false,
  isRecording: false,
  
  // Actions
  setTasks: (tasks) => set({ tasks }),
  setActiveTask: (taskId) => set({ activeTaskId: taskId }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setHealthStatus: (status) => set({ healthStatus: status }),
  setConnected: (connected) => set({ isConnected: connected }),
  setVoiceEnabled: (enabled) => set({ isVoiceEnabled: enabled }),
  setRecording: (recording) => set({ isRecording: recording }),
}));
