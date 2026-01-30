import axios from 'axios';
import type { ResearchState, ResearchSessionSummary } from '../types';

const API_BASE_URL = 'http://localhost:8000'; // Adjust if env var needed

const api = axios.create({
    baseURL: API_BASE_URL,
});

export const startResearch = async (topic: string): Promise<{ session_id: string, message: string }> => {
    const response = await api.post('/research/start', { topic });
    return response.data;
};

export const getHistory = async (): Promise<ResearchSessionSummary[]> => {
    const response = await api.get('/research/history');
    return response.data;
};

export const getSessionState = async (sessionId: string): Promise<ResearchState> => {
    const response = await api.get(`/research/${sessionId}`);
    return response.data;
};

export const getExportUrl = (sessionId: string): string => {
    return `${API_BASE_URL}/research/${sessionId}/export`;
};
