const BASE_URL = ''

interface RequestOptions {
  method: string
  headers?: Record<string, string>
  body?: string
}

async function request<T = any>(path: string, options: RequestOptions): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  const resp = await fetch(`${BASE_URL}${path}`, {
    method: options.method,
    headers,
    body: options.body,
  })

  const data = await resp.json()

  if (!resp.ok) {
    throw new Error(data.error || `HTTP ${resp.status}`)
  }

  return data as T
}

export const apiClient = {
  get<T = any>(path: string): Promise<T> {
    return request<T>(path, { method: 'GET' })
  },

  post<T = any>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  },

  put<T = any>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
  },

  del<T = any>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' })
  },
}
