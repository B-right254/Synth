import { useState } from 'react';
import { taskService } from '../services/api';
import { useAppStore } from '../store/appStore';

export function Dashboard() {
  const [newTaskRequest, setNewTaskRequest] = useState('');
  const { tasks, activeTaskId, setActiveTask, setTasks, isVoiceEnabled, setVoiceEnabled } = useAppStore();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskRequest.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const task = await taskService.create(newTaskRequest);
      setTasks([...tasks, task]);
      setNewTaskRequest('');
      setActiveTask(task.id);
    } catch (error) {
      console.error('Failed to create task:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelTask = async (taskId: string) => {
    try {
      await taskService.cancel(taskId);
      // Update local state
      setTasks(tasks.map(t => 
        t.id === taskId ? { ...t, state: 'cancelled' as const } : t
      ));
      if (activeTaskId === taskId) {
        setActiveTask(null);
      }
    } catch (error) {
      console.error('Failed to cancel task:', error);
    }
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>JARVIS</h1>
        <div style={styles.controls}>
          <button
            onClick={() => setVoiceEnabled(!isVoiceEnabled)}
            style={{
              ...styles.button,
              backgroundColor: isVoiceEnabled ? '#4CAF50' : '#666',
            }}
          >
            🎤 Voice {isVoiceEnabled ? 'On' : 'Off'}
          </button>
          <button style={{ ...styles.button, backgroundColor: '#f44336' }}>
            ⏹ Stop
          </button>
        </div>
      </header>

      <main style={styles.main}>
        {/* New Task Form */}
        <form onSubmit={handleCreateTask} style={styles.form}>
          <input
            type="text"
            value={newTaskRequest}
            onChange={(e) => setNewTaskRequest(e.target.value)}
            placeholder="What would you like me to do?"
            style={styles.input}
            disabled={isSubmitting}
          />
          <button 
            type="submit" 
            style={styles.submitButton}
            disabled={!newTaskRequest.trim() || isSubmitting}
          >
            {isSubmitting ? 'Creating...' : 'Submit'}
          </button>
        </form>

        {/* Tasks List */}
        <div style={styles.tasksSection}>
          <h2 style={styles.sectionTitle}>Tasks</h2>
          {tasks.length === 0 ? (
            <p style={styles.emptyMessage}>No tasks yet. Create one above!</p>
          ) : (
            <div style={styles.taskList}>
              {tasks.map((task) => (
                <div
                  key={task.id}
                  onClick={() => setActiveTask(task.id)}
                  style={{
                    ...styles.taskCard,
                    borderLeft: `4px solid ${getStateColor(task.state)}`,
                    backgroundColor: activeTaskId === task.id ? '#333' : '#2a2a2a',
                  }}
                >
                  <div style={styles.taskHeader}>
                    <span style={styles.taskState}>{task.state}</span>
                    <span style={styles.taskDate}>
                      {new Date(task.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p style={styles.taskRequest}>{task.original_request}</p>
                  {task.final_result && (
                    <p style={styles.taskResult}>{task.final_result}</p>
                  )}
                  {task.state === 'running' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCancelTask(task.id);
                      }}
                      style={styles.cancelButton}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function getStateColor(state: string): string {
  switch (state) {
    case 'completed':
      return '#4CAF50';
    case 'failed':
      return '#f44336';
    case 'cancelled':
      return '#9e9e9e';
    case 'running':
      return '#2196F3';
    case 'waiting_for_user':
      return '#FF9800';
    default:
      return '#666';
  }
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#1a1a1a',
    color: '#fff',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    borderBottom: '1px solid #333',
  },
  title: {
    fontSize: '24px',
    fontWeight: 'bold',
    margin: 0,
  },
  controls: {
    display: 'flex',
    gap: '12px',
  },
  button: {
    padding: '8px 16px',
    border: 'none',
    borderRadius: '4px',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '14px',
  },
  main: {
    flex: 1,
    padding: '24px',
    overflowY: 'auto',
  },
  form: {
    display: 'flex',
    gap: '12px',
    marginBottom: '24px',
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    border: '1px solid #333',
    borderRadius: '4px',
    backgroundColor: '#2a2a2a',
    color: '#fff',
    fontSize: '16px',
  },
  submitButton: {
    padding: '12px 24px',
    border: 'none',
    borderRadius: '4px',
    backgroundColor: '#2196F3',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '16px',
  },
  tasksSection: {
    marginTop: '24px',
  },
  sectionTitle: {
    fontSize: '18px',
    marginBottom: '16px',
  },
  emptyMessage: {
    color: '#666',
    textAlign: 'center',
    padding: '40px',
  },
  taskList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  taskCard: {
    padding: '16px',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'background-color 0.2s',
  },
  taskHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: '8px',
  },
  taskState: {
    fontSize: '12px',
    textTransform: 'uppercase',
    color: '#888',
  },
  taskDate: {
    fontSize: '12px',
    color: '#666',
  },
  taskRequest: {
    fontSize: '14px',
    marginBottom: '8px',
  },
  taskResult: {
    fontSize: '14px',
    color: '#4CAF50',
    marginTop: '8px',
  },
  cancelButton: {
    marginTop: '8px',
    padding: '6px 12px',
    border: 'none',
    borderRadius: '4px',
    backgroundColor: '#f44336',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '12px',
  },
};
