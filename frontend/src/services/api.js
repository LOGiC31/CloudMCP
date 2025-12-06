import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const resourceService = {
  getAll: (includeGcp = true) => api.get('/api/resources', { params: { include_gcp: includeGcp } }),
  getStatus: (resourceId) => api.get(`/api/resources/${resourceId}`),
  getStatusUpdates: (includeGcp = true) => api.get('/api/resources/status', { params: { include_gcp: includeGcp } }), // Lightweight status-only endpoint
};

export const logService = {
  getErrorLogs: (params = {}) => api.get('/api/logs', { params }),
  getLogs: (params = {}) => api.get('/api/logs', { params }),
};

export const fixService = {
  trigger: () => api.post('/api/fixes/trigger', {}),
  getAll: (params = {}) => api.get('/api/fixes', { params }),
  getById: (fixId) => api.get(`/api/fixes/${fixId}`),
  deleteAll: () => api.delete('/api/fixes'),
};

export const llmService = {
  getInteractions: (params = {}) => api.get('/api/llm/interactions', { params }),
  getInteraction: (interactionId) => api.get(`/api/llm/interactions/${interactionId}`),
};

export const toolService = {
  getAll: () => api.get('/api/mcp/tools'),
  getByResource: (resourceType) => api.get(`/api/mcp/tools?resource_type=${resourceType}`),
};

export const sampleAppService = {
  introduceFailure: async (type, params = {}) => {
    const SAMPLE_APP_URL = 'http://localhost:8001';
    try {
      if (type === 'redis') {
        const response = await axios.post(`${SAMPLE_APP_URL}/load/redis`, null, { 
          params: { size_mb: params.size_mb || 250 } 
        });
        return response;
      } else if (type === 'database') {
        const response = await axios.post(`${SAMPLE_APP_URL}/load/database/blocking`, null, { 
          params: { queries: params.queries || 85 } 
        });
        return response;
      } else if (type === 'nginx') {
        // Use higher connection count to ensure degradation (need >80% of worker_connections)
        // Default worker_connections is 100, but may have been scaled up, so use 90 to be safe
        // If scaled to 300, we'd need 240+, but let's use 90 which works for default 100
        const response = await axios.post(`${SAMPLE_APP_URL}/load/nginx`, null, { 
          params: { connections: params.connections || 90 } 
        });
        return response;
      } else if (type === 'both') {
        const [redisRes, dbRes] = await Promise.all([
          axios.post(`${SAMPLE_APP_URL}/load/redis`, null, { params: { size_mb: 250 } }),
          axios.post(`${SAMPLE_APP_URL}/load/database/blocking`, null, { params: { queries: 85 } }),
        ]);
        return { data: { message: 'Both failures introduced', redis: redisRes.data, database: dbRes.data } };
      }
    } catch (error) {
      throw new Error(error.response?.data?.detail || error.message || 'Failed to introduce failure');
    }
  },
  resetRedis: async () => {
    // Call the backend API to reset Redis
    return api.post('/api/resources/redis/reset');
  },
  resetPostgres: async () => {
    // Call the backend API to reset PostgreSQL
    return api.post('/api/resources/postgres/reset');
  },
  resetNginx: async () => {
    // Call the backend API to reset Nginx
    return api.post('/api/resources/nginx/reset');
  },
};

export const gcpFailureService = {
  // Redis failures
  redisMemoryPressure: async (instanceId, fillPercent = 0.95) => {
    return api.post(`/api/gcp/failures/redis/${instanceId}/memory-pressure`, null, {
      params: { fill_percent: fillPercent }
    });
  },
  clearRedisMemory: async (instanceId) => {
    return api.post(`/api/gcp/failures/redis/${instanceId}/clear-memory`);
  },
  degradeRedis: async (instanceId, memoryGb = 0.5) => {
    return api.post(`/api/gcp/failures/redis/${instanceId}/degrade`, null, {
      params: { memory_gb: memoryGb }
    });
  },
  resetRedis: async (instanceId, memoryGb = 1.0) => {
    return api.post(`/api/gcp/failures/redis/${instanceId}/reset`, null, {
      params: { memory_gb: memoryGb }
    });
  },
  // Compute failures
  computeCpuStress: async (instanceName, zone = null, durationSeconds = 600, cpuPercent = 90) => {
    return api.post(`/api/gcp/failures/compute/${instanceName}/cpu-stress`, null, {
      params: { 
        zone: zone || undefined,
        duration_seconds: durationSeconds,
        cpu_percent: cpuPercent
      }
    });
  },
  computeMemoryPressure: async (instanceName, zone = null, fillPercent = 0.90) => {
    return api.post(`/api/gcp/failures/compute/${instanceName}/memory-pressure`, null, {
      params: { 
        zone: zone || undefined,
        fill_percent: fillPercent
      }
    });
  },
  stopCompute: async (instanceName, zone = null) => {
    return api.post(`/api/gcp/failures/compute/${instanceName}/stop`, null, {
      params: zone ? { zone } : {}
    });
  },
  startCompute: async (instanceName, zone = null) => {
    return api.post(`/api/gcp/failures/compute/${instanceName}/start`, null, {
      params: zone ? { zone } : {}
    });
  },
  // SQL failures
  sqlConnectionOverload: async (instanceId, connections = 100) => {
    return api.post(`/api/gcp/failures/sql/${instanceId}/connection-overload`, null, {
      params: { connections }
    });
  },
  sqlBlockingQueries: async (instanceId, queries = 10, durationSeconds = 300) => {
    return api.post(`/api/gcp/failures/sql/${instanceId}/blocking-queries`, null, {
      params: { queries, duration_seconds: durationSeconds }
    });
  },
  stopSQL: async (instanceId) => {
    return api.post(`/api/gcp/failures/sql/${instanceId}/stop`);
  },
  startSQL: async (instanceId) => {
    return api.post(`/api/gcp/failures/sql/${instanceId}/start`);
  },
};

export default api;

