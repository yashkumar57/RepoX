import type {
  RepositoryAskResponse,
  RepositoryCreateResponse,
  RepositoryIndexResponse,
} from '@/lib/api'

const STORAGE_KEY = 'repox.workspace.v1'
const VERSION = 1

export interface AskConversationEntry {
  query: string
  response: RepositoryAskResponse
}

export interface AskConversationState {
  draft: string
  entries: AskConversationEntry[]
}

export interface WorkspaceSession {
  repository: RepositoryCreateResponse | null
  indexResult: RepositoryIndexResponse | null
  conversations: Record<string, AskConversationState>
}

interface StoredWorkspaceSession extends WorkspaceSession {
  version: number
}

const emptySession = (): WorkspaceSession => ({
  repository: null,
  indexResult: null,
  conversations: {},
})

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isRepository(value: unknown): value is RepositoryCreateResponse {
  return isRecord(value)
    && typeof value.repository_id === 'string'
    && typeof value.owner === 'string'
    && typeof value.name === 'string'
    && typeof value.url === 'string'
    && (typeof value.branch === 'string' || value.branch === null)
}

function isIndexResult(value: unknown): value is RepositoryIndexResponse {
  return isRecord(value)
    && typeof value.repository_id === 'string'
    && typeof value.status === 'string'
    && typeof value.analyzed_files === 'number'
    && typeof value.relationships === 'number'
    && typeof value.total_chunks === 'number'
    && typeof value.embedded_chunks === 'number'
    && typeof value.reused_chunks === 'number'
    && typeof value.deleted_chunks === 'number'
}

function isAskResponse(value: unknown): value is RepositoryAskResponse {
  return isRecord(value)
    && typeof value.repository_id === 'string'
    && typeof value.query === 'string'
    && typeof value.answer === 'string'
    && typeof value.model === 'string'
    && Array.isArray(value.citations)
    && Array.isArray(value.invalid_citations)
    && typeof value.citation_retry_used === 'boolean'
    && typeof value.citation_fallback_used === 'boolean'
}

function isConversation(value: unknown): value is AskConversationState {
  return isRecord(value)
    && typeof value.draft === 'string'
    && Array.isArray(value.entries)
    && value.entries.every(
      entry => isRecord(entry) && typeof entry.query === 'string' && isAskResponse(entry.response),
    )
}

export function loadWorkspaceSession(): WorkspaceSession {
  if (typeof window === 'undefined') return emptySession()
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return emptySession()
    const stored: unknown = JSON.parse(raw)
    if (!isRecord(stored) || stored.version !== VERSION) return emptySession()
    const conversations: Record<string, AskConversationState> = isRecord(stored.conversations)
      ? Object.fromEntries(
          Object.entries(stored.conversations).filter(([, value]) => isConversation(value)),
        ) as Record<string, AskConversationState>
      : {}
    return {
      repository: isRepository(stored.repository) ? stored.repository : null,
      indexResult: isIndexResult(stored.indexResult) ? stored.indexResult : null,
      conversations,
    }
  } catch {
    return emptySession()
  }
}

export function saveWorkspaceSession(session: WorkspaceSession): void {
  if (typeof window === 'undefined') return
  try {
    const payload: StoredWorkspaceSession = { version: VERSION, ...session }
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Storage can be disabled or full; the in-memory workspace remains usable.
  }
}
