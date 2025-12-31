// src/services/apiClient.ts
import {API_BASE_URL} from '../config';

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  async get(endpoint: string) {
    return this.request('GET', endpoint);
  }

  // Add other methods like post, put, delete as needed

  private async request(method: string, endpoint: string, body?: any) {
    const headers = new Headers({
      'Content-Type': 'application/json',
    });

    if (this.token) {
      headers.append('Authorization', `Bearer ${this.token}`);
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });

    if (!response.ok) {
      // More sophisticated error handling can be added here
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (response.status === 204) {
      // No Content
      return null;
    }

    return response.json();
  }
}

export default new ApiClient();
