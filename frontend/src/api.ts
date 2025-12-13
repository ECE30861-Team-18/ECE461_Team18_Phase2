import {
  Artifact,
  ArtifactCost,
  ArtifactLineageGraph,
  ArtifactMetadata,
  ArtifactQuery,
  ArtifactRegEx,
  ArtifactType,
  ArtifactAuditEntry,
  AuthenticationRequest,
  AuthenticationToken,
  ModelRating,
  SimpleLicenseCheckRequest,
  HealthComponentCollection,
  TracksResponse,
  ApiError,
} from './types';

const API_BASE_URL = 'https://wc1j5prmsj.execute-api.us-east-1.amazonaws.com/dev';

class ApiClient {
  private token: AuthenticationToken | null = null;

  constructor() {
    // Load token from localStorage on init
    const savedToken = localStorage.getItem('auth_token');
    if (savedToken) {
      this.token = savedToken;
    }
  }

  setToken(token: AuthenticationToken | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('auth_token', token);
    } else {
      localStorage.removeItem('auth_token');
    }
  }

  getToken(): AuthenticationToken | null {
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // Add auth token if available
    if (this.token) {
      headers['X-Authorization'] = this.token;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    // Handle error responses
    if (!response.ok) {
      const error: ApiError = {
        message: `HTTP ${response.status}: ${response.statusText}`,
        status: response.status,
      };

      try {
        const errorData = await response.json();
        error.message = errorData.message || error.message;
      } catch {
        // Use default error message
      }

      throw error;
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    // Parse offset header for pagination
    const offset = response.headers.get('offset');
    const data = await response.json();

    if (offset) {
      return { data, offset } as T;
    }

    return data;
  }

  // ==================== Authentication ====================

  async authenticate(request: AuthenticationRequest): Promise<AuthenticationToken> {
    const token = await this.request<AuthenticationToken>('/authenticate', {
      method: 'PUT',
      body: JSON.stringify(request),
    });
    this.setToken(token);
    return token;
  }

  logout() {
    this.setToken(null);
  }

  // ==================== Health ====================

  async healthCheck(): Promise<void> {
    await this.request<void>('/health');
  }

  async getHealthComponents(
    windowMinutes: number = 60,
    includeTimeline: boolean = false
  ): Promise<HealthComponentCollection> {
    const params = new URLSearchParams({
      windowMinutes: windowMinutes.toString(),
      includeTimeline: includeTimeline.toString(),
    });
    return this.request<HealthComponentCollection>(
      `/health/components?${params}`
    );
  }

  // ==================== Artifacts ====================

  async listArtifacts(
    queries: ArtifactQuery[],
    offset?: string
  ): Promise<{ data: ArtifactMetadata[]; offset?: string }> {
    const params = offset ? `?offset=${offset}` : '';
    return this.request<{ data: ArtifactMetadata[]; offset?: string }>(
      `/artifacts${params}`,
      {
        method: 'POST',
        body: JSON.stringify(queries),
      }
    );
  }

  async getArtifact(
    type: ArtifactType,
    id: string
  ): Promise<Artifact> {
    return this.request<Artifact>(`/artifacts/${type}/${id}`);
  }

  async createArtifact(
    type: ArtifactType,
    data: { url: string }
  ): Promise<Artifact> {
    return this.request<Artifact>(`/artifact/${type}`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateArtifact(
    type: ArtifactType,
    id: string,
    artifact: Artifact
  ): Promise<void> {
    await this.request<void>(`/artifacts/${type}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(artifact),
    });
  }

  async deleteArtifact(type: ArtifactType, id: string): Promise<void> {
    await this.request<void>(`/artifacts/${type}/${id}`, {
      method: 'DELETE',
    });
  }

  async getArtifactsByName(name: string): Promise<ArtifactMetadata[]> {
    return this.request<ArtifactMetadata[]>(`/artifact/byName/${name}`);
  }

  async searchArtifactsByRegex(regex: ArtifactRegEx): Promise<ArtifactMetadata[]> {
    return this.request<ArtifactMetadata[]>('/artifact/byRegEx', {
      method: 'POST',
      body: JSON.stringify(regex),
    });
  }

  // ==================== Model Specific ====================

  async getModelRating(id: string): Promise<ModelRating> {
    return this.request<ModelRating>(`/artifact/model/${id}/rate`);
  }

  async getModelLineage(id: string): Promise<ArtifactLineageGraph> {
    return this.request<ArtifactLineageGraph>(`/artifact/model/${id}/lineage`);
  }

  async checkModelLicense(
    id: string,
    request: SimpleLicenseCheckRequest
  ): Promise<boolean> {
    return this.request<boolean>(`/artifact/model/${id}/license-check`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // ==================== Cost ====================

  async getArtifactCost(
    type: ArtifactType,
    id: string,
    includeDependencies: boolean = false
  ): Promise<ArtifactCost> {
    const params = includeDependencies ? '?dependency=true' : '';
    return this.request<ArtifactCost>(
      `/artifact/${type}/${id}/cost${params}`
    );
  }

  // ==================== Audit ====================

  async getArtifactAudit(
    type: ArtifactType,
    id: string
  ): Promise<ArtifactAuditEntry[]> {
    return this.request<ArtifactAuditEntry[]>(
      `/artifact/${type}/${id}/audit`
    );
  }

  // ==================== Admin ====================

  async resetRegistry(): Promise<void> {
    await this.request<void>('/reset', {
      method: 'DELETE',
    });
  }

  async getTracks(): Promise<TracksResponse> {
    return this.request<TracksResponse>('/tracks');
  }
}

export const apiClient = new ApiClient();
export default apiClient;