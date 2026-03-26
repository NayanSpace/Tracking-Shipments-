import axios from "axios";
import { getToken, clearAuth } from "../utils/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// ─── Request Interceptor — attach JWT ────────────────────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// ─── Response Interceptor — handle 401 globally ──────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuth();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ─── Friendly Error Messages ─────────────────────────────────────────────────
export const getFriendlyError = (err) => {
  if (!err.response) return "Unable to connect. Check your internet connection.";
  const { status, data } = err.response;
  if (status === 429) return "Too many requests — please wait a moment.";
  if (status === 404) return "Not found.";
  if (status === 400) return data?.message || "Invalid request.";
  if (status === 403) return "You don't have permission to do that.";
  return data?.message || "An error occurred. Please try again.";
};

// ─── Auth ─────────────────────────────────────────────────────────────────────
export const loginApi = (username, password) =>
  api.post("/auth/login", { username, password }).then((r) => r.data);

export const registerApi = (username, email, password) =>
  api.post("/auth/register", { username, email, password }).then((r) => r.data);

export const getMeApi = () =>
  api.get("/auth/me").then((r) => r.data);

// ─── Tracking ─────────────────────────────────────────────────────────────────
export const addTrackingApi = (carrier, tracking_numbers) =>
  api.post("/tracking/add", { carrier, tracking_numbers }).then((r) => r.data);

export const listTrackingApi = (params = {}) =>
  api.get("/tracking/list", { params }).then((r) => r.data);

export const getTrackingApi = (id) =>
  api.get(`/tracking/${id}`).then((r) => r.data);

export const refreshTrackingApi = (id) =>
  api.post(`/tracking/${id}/refresh`).then((r) => r.data);

export const deleteTrackingApi = (id) =>
  api.delete(`/tracking/${id}`).then((r) => r.data);

export default api;
