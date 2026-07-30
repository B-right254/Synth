import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAppInit } from './hooks/useAppInit';
import { Dashboard } from './components/Dashboard';
import { useAppStore } from './store/appStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppContent() {
  const { isInitialized } = useAppInit();
  const { isConnected, error } = useAppStore();

  if (!isInitialized) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}>Loading...</div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div style={styles.errorContainer}>
        <h2>Connection Error</h2>
        <p>{error || 'Unable to connect to JARVIS backend'}</p>
        <p style={styles.errorHint}>
          Make sure the backend server is running on port 8000
        </p>
      </div>
    );
  }

  return <Dashboard />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;

const styles: { [key: string]: React.CSSProperties } = {
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    backgroundColor: '#1a1a1a',
    color: '#fff',
  },
  loadingSpinner: {
    fontSize: '18px',
  },
  errorContainer: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    backgroundColor: '#1a1a1a',
    color: '#fff',
    padding: '24px',
    textAlign: 'center',
  },
  errorHint: {
    marginTop: '16px',
    color: '#888',
    fontSize: '14px',
  },
};
