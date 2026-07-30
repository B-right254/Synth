import { useState, useEffect } from 'react';
import { useAppStore } from '../store/appStore';
import { healthService, taskService } from '../services/api';

export function useAppInit() {
  const { 
    setHealthStatus, 
    setConnected, 
    setError, 
    setTasks,
    setLoading 
  } = useAppStore();

  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    const initializeApp = async () => {
      setLoading(true);
      
      try {
        // Check health
        const health = await healthService.check();
        setHealthStatus(health);
        setConnected(true);
        
        // Load tasks
        const tasks = await taskService.list();
        setTasks(tasks);
        
        setIsInitialized(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect to backend');
        setConnected(false);
      } finally {
        setLoading(false);
      }
    };

    initializeApp();
  }, []);

  return { isInitialized };
}
