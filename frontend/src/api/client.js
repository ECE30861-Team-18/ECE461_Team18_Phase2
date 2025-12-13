// src/api/client.js

import axios from "axios";

/*
 * ============================================================
 * AXIOS INSTANCE
 * ============================================================
 */
const API = axios.create({
  baseURL: "https://wc1j5prmsj.execute-api.us-east-1.amazonaws.com/dev",
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

/*
 * ============================================================
 * RESPONSE / ERROR NORMALIZATION
 * Keeps UI code clean and consistent
 * ============================================================
 */
API.interceptors.response.use(
  (response) => response,
  (error) => {
    const normalizedError = {
      status: error.response?.status ?? 500,
      message:
        error.response?.data?.message ||
        error.message ||
        "Unexpected API error",
      data: error.response?.data ?? null,
    };

    return Promise.reject(normalizedError);
  }
);

/*
 * ============================================================
 * HEALTH & SYSTEM
 * ============================================================
 */

/** GET /health */
export const healthCheck = () => API.get("/health");

/** GET /health/components */
export const healthComponents = () => API.get("/health/components");

/** POST /reset */
export const resetSystem = () => API.post("/reset");

/*
 * ============================================================
 * AUTHENTICATION
 * ============================================================
 */

/** POST /authenticate */
export const authenticate = (payload) =>
  API.post("/authenticate", payload);

/*
 * ============================================================
 * ARTIFACT INGESTION & QUERY
 * ============================================================
 */

/**
 * POST /artifact/{artifact_type}
 * artifact_type = "model" | "dataset" | etc.
 */
export const ingestArtifact = (artifactType, payload) =>
  API.post(`/artifact/${artifactType}`, payload);

/**
 * GET /artifacts
 * Fetch all artifacts
 */
export const getArtifacts = () => API.get("/artifacts");

/**
 * GET /artifacts/{artifact_type}/{id}
 */
export const getArtifactById = (artifactType, id) =>
  API.get(`/artifacts/${artifactType}/${id}`);

/**
 * GET /artifact/byName/{name}
 */
export const getArtifactByName = (name) =>
  API.get(`/artifact/byName/${encodeURIComponent(name)}`);

/**
 * POST /artifact/byRegEx
 */
export const getArtifactsByRegex = (payload) =>
  API.post("/artifact/byRegEx", payload);

/*
 * ============================================================
 * MODEL-SPECIFIC OPERATIONS
 * ============================================================
 */

/**
 * POST /artifact/model/{id}/rate
 * Rate a model
 */
export const rateModel = (id, payload) =>
  API.post(`/artifact/model/${id}/rate`, payload);

/**
 * GET /artifact/model/{id}/lineage
 */
export const getModelLineage = (id) =>
  API.get(`/artifact/model/${id}/lineage`);

/**
 * GET /artifact/model/{id}/license-check
 */
export const checkModelLicense = (id) =>
  API.get(`/artifact/model/${id}/license-check`);

/*
 * ============================================================
 * COST & AUDIT
 * ============================================================
 */

/**
 * GET /artifact/{artifact_type}/{id}/cost
 */
export const getArtifactCost = (artifactType, id) =>
  API.get(`/artifact/${artifactType}/${id}/cost`);

/**
 * GET /artifact/{artifact_type}/{id}/audit
 */
export const getArtifactAudit = (artifactType, id) =>
  API.get(`/artifact/${artifactType}/${id}/audit`);

/*
 * ============================================================
 * TRACKS
 * ============================================================
 */

/** GET /tracks */
export const getTracks = () => API.get("/tracks");

/*
 * ============================================================
 * RAW INSTANCE (advanced usage only)
 * ============================================================
 */
export default API;
