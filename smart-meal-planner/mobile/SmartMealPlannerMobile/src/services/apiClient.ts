// src/services/apiClient.ts
import {API_BASE_URL, getApiBaseUrl} from '../config';

class ApiClient {
  private token: string | null = null;
  private customBaseUrl: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  setBaseUrl(url: string | null) {
    this.customBaseUrl = url;
  }

  async getBaseUrl(): Promise<string> {
    if (this.customBaseUrl) {
      return this.customBaseUrl;
    }
    return getApiBaseUrl();
  }

  async get(endpoint: string) {
    return this.request('GET', endpoint);
  }

  async post(endpoint: string, body?: any) {
    return this.request('POST', endpoint, body);
  }

  async put(endpoint: string, body?: any) {
    return this.request('PUT', endpoint, body);
  }

  async delete(endpoint: string) {
    return this.request('DELETE', endpoint);
  }

  private async request(method: string, endpoint: string, body?: any) {
    const headers = new Headers({
      'Content-Type': 'application/json',
    });

    if (this.token) {
      headers.append('Authorization', `Bearer ${this.token}`);
    }

    const baseUrl = await this.getBaseUrl();
    const cleanBase = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

    const response = await fetch(`${cleanBase}${cleanEndpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (response.status === 204) {
      return null;
    }

    return response.json();
  }
}

export default new ApiClient();
