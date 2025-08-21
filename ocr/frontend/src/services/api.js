import axios from 'axios';

// API URL helper function
export const getApiUrl = (path) => {
  // For production, use relative paths with the proxy
  // For development with direct access, use absolute URL
  const isDev = process.env.NODE_ENV === 'development';
  return isDev ? `http://localhost:5000${path}` : path;
};

// Create an API client instance
const apiClient = axios.create({
  timeout: 30000, // 30 seconds timeout
  headers: {
    'Content-Type': 'application/json'
  }
});

// Request interceptor
apiClient.interceptors.request.use((config) => {
  // If the URL doesn't start with http, apply the API URL helper
  if (config.url && !config.url.startsWith('http')) {
    config.url = getApiUrl(config.url);
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle error response
    console.error('API Error:', error);
    
    // If the error is related to a connection issue
    if (!error.response) {
      console.error('Network Error: Could not connect to the backend server');
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;
