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


export interface RepositoryGraphNode {
  id: string
  name: string
  kind: 'file' | 'class' | 'function' | string
  path: string
  language: string
  start_line: number | null
  end_line: number | null
}

export interface RepositoryGraphEdge {
  source: string
  target: string
  kind: string
  evidence: string | null
}

export interface RepositoryGraphResponse {
  repository_id: string
  summary: {
    files: number
    symbols: number
    classes: number
    functions: number
    relationships: number
    parse_errors: number
    scan_errors: number
    languages: Record<string, number>
    relationship_kinds: Record<string, number>
  }
  nodes: RepositoryGraphNode[]
  edges: RepositoryGraphEdge[]
}

export function getRepositoryGraph(
  repositoryId: string,
): Promise<RepositoryGraphResponse> {
  return request<RepositoryGraphResponse>(
    `/repositories/${encodeURIComponent(repositoryId)}/graph`,
  )
}


export interface DebugTracebackFrame {
  path: string
  line: number
  function: string
}

export interface RepositoryDebugResponse {
  repository_id: string
  description: string
  exception_type: string | null
  exception_message: string | null
  frames: DebugTracebackFrame[]
  innermost_frame: DebugTracebackFrame | null
  answer: string
  model: string
  citations: { source_id: string; file_path: string; start_line: number; end_line: number }[]
  citation_fallback_used: boolean
}

export function debugRepository(
  repositoryId: string,
  payload: { description?: string; traceback?: string },
): Promise<RepositoryDebugResponse> {
  return request<RepositoryDebugResponse>(
    `/repositories/${encodeURIComponent(repositoryId)}/debug`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}


export interface RepositorySearchResult {
  file_path: string
  language: string
  kind: string
  symbol_id: string
  symbol_name: string
  start_line: number
  end_line: number
  content: string
  score: number
  distance: number
}

export interface RepositorySearchResponse {
  repository_id: string
  query: string
  result_count: number
  results: RepositorySearchResult[]
}

export interface RepositoryAskResponse {
  repository_id: string
  query: string
  answer: string
  model: string
  citations: {
    source_id: string
    file_path: string
    start_line: number
    end_line: number
  }[]
  invalid_citations: string[]
  citation_retry_used: boolean
  citation_fallback_used: boolean
  uncited_draft: string | null
}

export function searchRepository(
  repositoryId: string,
  payload: { query: string; top_k?: number },
): Promise<RepositorySearchResponse> {
  return request<RepositorySearchResponse>(
    `/repositories/${encodeURIComponent(repositoryId)}/search`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function askRepository(
  repositoryId: string,
  payload: {
    query: string
    top_k?: number
    context_limit?: number
    token_budget?: number
    max_output_tokens?: number
  },
): Promise<RepositoryAskResponse> {
  return request<RepositoryAskResponse>(
    `/repositories/${encodeURIComponent(repositoryId)}/ask`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}
