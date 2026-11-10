/** Typed HTTP client for the RepoX FastAPI backend. */

export interface RepositoryCreateRequest {
  repository_url: string
  branch?: string
}

export interface RepositoryCreateResponse {
  repository_id: string
  owner: string
  name: string
  url: string
  branch: string | null
  status: 'cloned' | string
}

export interface RepositoryRecordResponse extends RepositoryCreateResponse {
  status: 'cloned' | 'indexed' | string
  index_result: RepositoryIndexResponse | null
  created_at: string
  updated_at: string
}

export interface RepositoryIndexResponse {
  repository_id: string
  status: 'indexed' | string
  analyzed_files: number
  relationships: number
  total_chunks: number
  embedded_chunks: number
  reused_chunks: number
  deleted_chunks: number
}

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string; loc?: (string | number)[] }>
}

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_REPOX_API_URL ?? 'http://127.0.0.1:8000'
).replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new Error(
      `Cannot reach the RepoX API at ${API_BASE_URL}. Check that the backend is running and the URL is correct.`,
    )
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg ?? 'Invalid request').join('; ')
      : body.detail
    throw new Error(detail || `RepoX API request failed (${response.status}).`)
  }

  return (await response.json()) as T
}

export function listRepositories(): Promise<RepositoryRecordResponse[]> {
  return request<RepositoryRecordResponse[]>('/repositories')
}

export function getRepository(repositoryId: string): Promise<RepositoryRecordResponse> {
  return request<RepositoryRecordResponse>(
    `/repositories/${encodeURIComponent(repositoryId)}`,
  )
}

export function createRepository(
  payload: RepositoryCreateRequest,
): Promise<RepositoryCreateResponse> {
  return request<RepositoryCreateResponse>('/repositories', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function indexRepository(
  repositoryId: string,
): Promise<RepositoryIndexResponse> {
  return request<RepositoryIndexResponse>(
    `/repositories/${encodeURIComponent(repositoryId)}/index`,
    { method: 'POST' },
  )
}

export function getApiBaseUrl(): string {
  return API_BASE_URL
}
