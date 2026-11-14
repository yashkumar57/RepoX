'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  askRepository,
  createRepository,
  debugRepository,
  getApiHealth,
  getRepository,
  getRepositoryGraph,
  indexRepository,
  listRepositories,
  searchRepository,
  type RepositoryAskResponse,
  type RepositoryCreateResponse,
  type RepositoryDebugResponse,
  type RepositoryGraphResponse,
  type RepositoryIndexResponse,
  type RepositoryRecordResponse,
  type RepositorySearchResponse,
} from '@/lib/api'
import { expandGraphNodeIds, graphNodePositions, initialGraphNodeIds, MAX_GRAPH_NODE_LIMIT } from '@/lib/graph-explorer'
import {
  loadWorkspaceSession,
  saveWorkspaceSession,
  type AskConversationState,
} from '@/lib/workspace-session'
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bug as BugIcon,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Code2,
  Copy,
  Database,
  FileCode2,
  FolderGit2,
  GitBranch,
  GitCommitHorizontal,
  GitFork,
  LayoutDashboard,
  Lightbulb,
  Link2,
  Menu,
  Minus,
  Moon,
  Maximize2,
  Network,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
  Sun,
  TerminalSquare,
  Upload,
  X,
  Zap,
} from 'lucide-react'

type Screen = 'overview' | 'onboarding' | 'search' | 'ask' | 'debug' | 'graph' | 'settings'

const navItems: { id: Screen; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'search', label: 'Semantic search', icon: Search },
  { id: 'ask', label: 'Ask RepoX', icon: CircleHelp },
  { id: 'debug', label: 'Debug an issue', icon: BugIcon },
  { id: 'graph', label: 'Code graph', icon: Network },
]

type HealthStatus = 'checking' | 'connected' | 'disconnected'

function indexedRepositories(records: RepositoryRecordResponse[]): RepositoryRecordResponse[] {
  const seen = new Set<string>()
  return records.filter(record => {
    if (record.status !== 'indexed' || !record.index_result || seen.has(record.repository_id)) return false
    seen.add(record.repository_id)
    return true
  })
}

function useApiHeartbeat(): HealthStatus {
  const [status, setStatus] = useState<HealthStatus>('checking')

  useEffect(() => {
    let active = true
    const check = async () => {
      if (active) setStatus('checking')
      try {
        const health = await getApiHealth()
        if (active) setStatus(health.status === 'ok' ? 'connected' : 'disconnected')
      } catch {
        if (active) setStatus('disconnected')
      }
    }
    void check()
    const interval = window.setInterval(() => void check(), 25_000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  return status
}

export function RepoXApp() {
  const [screen, setScreen] = useState<Screen>('overview')
  const [dark, setDark] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [repository, setRepository] = useState<RepositoryCreateResponse | null>(null)
  const [indexResult, setIndexResult] = useState<RepositoryIndexResponse | null>(null)
  const [repositories, setRepositories] = useState<RepositoryRecordResponse[]>([])
  const [repositoryError, setRepositoryError] = useState<string | null>(null)
  const [repositoryMenuOpen, setRepositoryMenuOpen] = useState(false)
  const [conversations, setConversations] = useState<Record<string, AskConversationState>>({})
  const [sessionReady, setSessionReady] = useState(false)
  const lastSessionPayload = useRef('')
  const heartbeat = useApiHeartbeat()
  const repo = repository ? `${repository.owner ? `${repository.owner} / ` : ''}${repository.name}` : 'No repository connected'
  const [selectedNode, setSelectedNode] = useState('')

  useEffect(() => {
    const stored = loadWorkspaceSession()
    setRepository(stored.repository)
    setIndexResult(stored.indexResult)
    setConversations(stored.conversations)
    setSessionReady(true)
  }, [])

  useEffect(() => {
    if (!sessionReady) return
    const payload = JSON.stringify({ repository, indexResult, conversations })
    if (payload === lastSessionPayload.current) return
    const timeout = window.setTimeout(() => {
      saveWorkspaceSession({ repository, indexResult, conversations })
      lastSessionPayload.current = payload
    }, 250)
    return () => window.clearTimeout(timeout)
  }, [conversations, indexResult, repository, sessionReady])

  useEffect(() => {
    if (!sessionReady) return
    let cancelled = false
    async function restoreWorkspace() {
      try {
        const available = indexedRepositories(await listRepositories())
        if (cancelled) return
        setRepositories(available)
        const active = available.find(item => item.repository_id === repository?.repository_id) ?? available[0]
        if (active) {
          setRepository({
            repository_id: active.repository_id,
            owner: active.owner,
            name: active.name,
            url: active.url,
            branch: active.branch,
            status: 'cloned',
          })
          setIndexResult(active.index_result)
        } else {
          setRepository(null)
          setIndexResult(null)
        }
      } catch (cause) {
        if (!cancelled) {
          console.error('RepoX workspace restoration failed:', cause)
        }
      } finally {
      }
    }
    void restoreWorkspace()
    return () => { cancelled = true }
  }, [repository?.repository_id, sessionReady])

  const conversation = repository
    ? conversations[repository.repository_id] ?? { draft: '', entries: [] }
    : { draft: '', entries: [] }
  const updateConversation = (value: AskConversationState) => {
    if (!repository) return
    setConversations(current => ({ ...current, [repository.repository_id]: value }))
  }
  const selectRepository = async (repositoryId: string) => {
    setRepositoryMenuOpen(false)
    if (repositoryId === repository?.repository_id) return
    setRepositoryError(null)
    try {
      const record = await getRepository(repositoryId)
      if (record.status !== 'indexed' || !record.index_result) {
        throw new Error('This repository no longer has an available index.')
      }
      setRepository(record)
      setIndexResult(record.index_result)
      setSelectedNode('')
    } catch (cause) {
      setRepositories(current => current.filter(item => item.repository_id !== repositoryId))
      setRepositoryError(cause instanceof Error ? cause.message : 'The selected repository is unavailable.')
    }
  }

  const themeClass = dark ? 'dark' : 'light'
  const pageTitle = useMemo(() => ({ overview: 'Repository overview', onboarding: 'Connect a repository', search: 'Semantic code search', ask: 'Ask RepoX', debug: 'Debug an issue', graph: 'Code graph', settings: 'Settings' })[screen], [screen])

  return (
    <div className={themeClass}>
      <div className="repox-shell">
        <aside className={`repox-sidebar ${sidebarOpen ? 'is-open' : ''}`}>
          <div className="brand-row">
            <img className="brand-mark" src="/branding/repox-mark.svg" alt="RepoX" />
            <div><div className="brand-name">RepoX</div><div className="brand-kicker">Repository intelligence</div></div>
            <button className="icon-button mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X /></button>
          </div>
          <div className="repo-switcher-wrap">
          <button className="repo-switcher" type="button" aria-haspopup="listbox" aria-expanded={repositoryMenuOpen} aria-controls="indexed-repository-menu" onClick={() => setRepositoryMenuOpen(open => !open)} onKeyDown={event => { if (event.key === 'Escape') setRepositoryMenuOpen(false) }} disabled={!repositories.length}>
            <div className="repo-avatar"><GitFork /></div>
            <div className="repo-meta"><span className="eyebrow">ACTIVE REPOSITORY</span><strong>{repository ? `${repository.owner}/${repository.name}` : 'No indexed repositories'} <ChevronDown aria-hidden="true" /></strong><span className="mono muted">{repository ? `${repository.branch ?? 'default branch'} · indexed` : 'Connect and index a GitHub repository'}</span></div>
          </button>
          {repositoryMenuOpen && <div id="indexed-repository-menu" className="repository-menu" role="listbox" aria-label="Indexed repositories">{repositories.map(item => <button type="button" role="option" aria-selected={item.repository_id === repository?.repository_id} className={`repository-option ${item.repository_id === repository?.repository_id ? 'active' : ''}`} key={item.repository_id} onClick={() => void selectRepository(item.repository_id)}><span>{item.owner}/{item.name}</span><small>{item.branch ?? 'default branch'} · {item.index_result?.analyzed_files.toLocaleString()} files</small></button>)}</div>}
          </div>
          {repositoryError && <div className="repo-switch-error" role="alert">{repositoryError}</div>}
          <div className="nav-section-label">Workspace</div>
          <nav className="side-nav" aria-label="Primary navigation">
            {navItems.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${screen === id ? 'active' : ''}`} onClick={() => { setScreen(id); setSidebarOpen(false) }}><Icon /><span>{label}</span>{id === 'ask' && <span className="nav-shortcut">⌘ K</span>}</button>)}
          </nav>
          <div className="sidebar-spacer" />
          <div className="index-status"><div className="status-heading"><span className="status-dot" /> {indexResult ? 'Index is ready' : 'Index not available'}</div><div className="progress-track"><span style={{ width: indexResult ? '100%' : '0%' }} /></div><span className="muted">{indexResult ? `${indexResult.analyzed_files} files · ${indexResult.total_chunks} chunks` : 'No indexing results yet'}</span></div>
          <button className={`nav-item ${screen === 'onboarding' ? 'active' : ''}`} onClick={() => setScreen('onboarding')}><Plus /><span>Add repository</span></button>
          <button className={`nav-item ${screen === 'settings' ? 'active' : ''}`} onClick={() => setScreen('settings')}><Settings /><span>Settings</span></button>
          <button className="theme-toggle" onClick={() => setDark(!dark)}>{dark ? <Sun /> : <Moon />}<span>{dark ? 'Light theme' : 'Dark theme'}</span><span className="mono">{dark ? '⌘ L' : '⌘ D'}</span></button>
        </aside>
        {sidebarOpen && <button className="sidebar-scrim mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />}
        <main className="repox-main">
          <header className="topbar"><button className="icon-button mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Menu /></button><div className="breadcrumbs"><span>{repository ? repo : 'Repository'}</span>{repository?.branch && <><ChevronRight /><span>{repository.branch}</span></>}<ChevronRight /><strong>{pageTitle}</strong></div><div className="top-actions"><button className={`icon-button heartbeat ${heartbeat}`} aria-label={`API status: ${heartbeat}`} title={heartbeat === 'checking' ? 'Checking RepoX API connection' : heartbeat === 'connected' ? 'RepoX API connected' : 'RepoX API disconnected'}><Activity /></button><a className="icon-button" href="https://github.com/yashkumar57/RepoX#readme" target="_blank" rel="noreferrer" aria-label="RepoX help and documentation" title="Help and documentation"><BookOpen /></a></div></header>
          <div className="page-content">{screen === 'overview' && <Overview onNavigate={setScreen} repository={repository} indexResult={indexResult} />}{screen === 'onboarding' && <Onboarding onConnected={(value, result) => { setRepository(value); setIndexResult(result); setScreen('overview') }} />}{screen === 'search' && <SearchScreen key={repository?.repository_id ?? 'none'} repositoryId={repository?.repository_id ?? null} initialQuery="" />}{screen === 'ask' && <AskScreen repositoryId={repository?.repository_id ?? null} conversation={conversation} onConversationChange={updateConversation} />}<div style={{ display: screen === 'debug' ? 'contents' : 'none' }}>
            <DebugScreen repositoryId={repository?.repository_id ?? null} />
          </div> {screen === 'graph' && <GraphScreen repositoryId={repository?.repository_id ?? null} selectedNode={selectedNode} setSelectedNode={setSelectedNode} />} {screen === 'settings' && <SettingsScreen dark={dark} setDark={setDark} />}</div><footer className="app-footer"><img src="/branding/repox-mark.svg" alt="" /><span>RepoX</span><a href="https://github.com/yashkumar57/RepoX" target="_blank" rel="noreferrer">GitHub</a><a href="mailto:ykverma5718@gmail.com">Contact</a><a href="https://github.com/yashkumar57/RepoX#readme" target="_blank" rel="noreferrer">Documentation</a></footer>
        </main>
      </div>
    </div>
  )
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) { return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div> }
function Overview({ onNavigate, repository, indexResult }: { onNavigate: (s: Screen) => void; repository: RepositoryCreateResponse | null; indexResult: RepositoryIndexResponse | null }) {
  const stats: [string, string, string, typeof FileCode2][] = indexResult
    ? [
        ['Files analyzed', indexResult.analyzed_files.toLocaleString(), 'Repository source files', FileCode2],
        ['Total chunks', indexResult.total_chunks.toLocaleString(), `${indexResult.embedded_chunks.toLocaleString()} embedded`, Database],
        ['Relationships', indexResult.relationships.toLocaleString(), 'Calls · imports · extends', Link2],
        ['Reused chunks', indexResult.reused_chunks.toLocaleString(), `${indexResult.deleted_chunks.toLocaleString()} deleted`, TerminalSquare],
      ]
    : [
        ['Files analyzed', '—', 'Awaiting indexing', FileCode2],
        ['Total chunks', '—', 'Awaiting indexing', Database],
        ['Relationships', '—', 'Awaiting indexing', Link2],
        ['Reused chunks', '—', 'Awaiting indexing', TerminalSquare],
      ]
  return <>
    <PageHeader eyebrow={repository ? `REPOSITORY / ${repository.owner.toUpperCase()} / ${repository.name.toUpperCase()}` : 'WORKSPACE / REPOSITORY INTELLIGENCE'} title="Repository overview" description="Structural intelligence for your codebase, grounded in source." action={<button className="button primary" onClick={() => onNavigate(repository ? 'search' : 'onboarding')}>{repository ? <Search /> : <Plus />} {repository ? 'Search code' : 'Add repository'}</button>} />
    <div className="overview-banner"><div className="banner-icon"><Zap /></div><div><strong>{indexResult ? 'Repository indexing completed' : repository ? 'Repository connected — indexing required' : 'Connect your first repository'}</strong><p>{indexResult ? `${indexResult.analyzed_files.toLocaleString()} files analyzed and ${indexResult.total_chunks.toLocaleString()} chunks processed.` : repository ? 'The repository has been cloned. Run indexing to analyze files and generate semantic chunks.' : 'Connect a public GitHub repository to begin structural analysis and semantic indexing.'}</p></div><span className={`badge ${indexResult ? 'success' : 'muted-badge'}`}>{indexResult ? 'Indexed' : repository ? 'Cloned' : 'Not connected'}</span></div>
    <div className="stats-grid">{stats.map(([label, value, sub, Icon]) => <div className="stat-card" key={label as string}><div className="stat-top"><span>{label as string}</span><Icon /></div><strong>{value as string}</strong><small>{sub as string}</small></div>)}</div>
    <div className="content-grid"><div className="panel"><div className="panel-heading"><div><h2>Indexing summary</h2><p>Results returned by the FastAPI indexing endpoint</p></div><Database /></div>{indexResult ? <div className="coverage-list">{[['Embedded chunks', indexResult.embedded_chunks], ['Reused chunks', indexResult.reused_chunks], ['Deleted chunks', indexResult.deleted_chunks]].map(([label, value]) => <div className="coverage-row" key={label as string}><div className="row-label"><span>{label as string}</span><span className="muted mono">{Number(value).toLocaleString()}</span></div></div>)}</div> : <p className="muted">No indexing report is available. Connect and index a repository to populate these metrics.</p>}</div>
    <div className="panel quick-actions"><div className="panel-heading"><div><h2>Explore your code</h2><p>Available after repository indexing.</p></div><Lightbulb /></div>{[['Semantic search','Find related implementations fast.','Search',Search,'search'],['Ask RepoX','Get evidence-backed explanations.','Ask a question',CircleHelp,'ask'],['Code graph','Trace relationships between symbols.','Open graph',Network,'graph']].map(([title, desc, cta, Icon, id]) => <button className="action-row" key={title as string} onClick={() => onNavigate(id as Screen)} disabled={!indexResult}><div className="action-icon"><Icon /></div><div><strong>{title as string}</strong><span>{desc as string}</span></div><span className="action-cta">{cta as string}<ArrowRight /></span></button>)}</div></div>
    <div className="panel repo-details"><div className="panel-heading"><div><h2>Repository details</h2><p>Connection and indexing metadata</p></div><button className="button ghost" onClick={() => onNavigate('settings')}><Settings /> Manage</button></div><div className="detail-grid"><div><span className="eyebrow">SOURCE</span><strong><GitFork /> {repository ? repository.url.replace(/^https:\/\//, '') : 'Not connected'}</strong></div><div><span className="eyebrow">BRANCH</span><strong><GitBranch /> {repository?.branch ?? '—'}</strong></div><div><span className="eyebrow">INDEX STATUS</span><strong><GitCommitHorizontal /> {indexResult ? 'Completed' : 'Not indexed'}</strong></div></div></div>
  </>
}

function Onboarding({ onConnected }: { onConnected: (repository: RepositoryCreateResponse, result: RepositoryIndexResponse) => void }) {
  const [url, setUrl] = useState('')
  const [branch, setBranch] = useState('')
  const [repository, setRepository] = useState<RepositoryCreateResponse | null>(null)
  const [status, setStatus] = useState<'idle' | 'connecting' | 'connected' | 'indexing' | 'ready'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [indexResult, setIndexResult] = useState<RepositoryIndexResponse | null>(null)

  async function handleConnect() {
    setError(null)
    setStatus('connecting')
    try {
      const created = await createRepository({ repository_url: url.trim(), ...(branch.trim() ? { branch: branch.trim() } : {}) })
      setRepository(created)
      setStatus('connected')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Repository connection failed.')
      setStatus('idle')
    }
  }

  async function handleIndex() {
    if (!repository) return
    setError(null)
    setStatus('indexing')
    try {
      const result = await indexRepository(repository.repository_id)
      setIndexResult(result)
      setStatus('ready')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Repository indexing failed.')
      setStatus('connected')
    }
  }

  return <><PageHeader eyebrow="WORKSPACE / NEW REPOSITORY" title="Connect a repository" description="Bring a GitHub repository into RepoX to unlock structural search and code intelligence." /><div className="onboarding-grid"><div className="panel form-panel"><div className="step-label"><span className={`step-number ${repository ? 'done' : 'active'}`}>{repository ? <Check /> : '1'}</span><div><h2>Repository source</h2><p>Connect from GitHub using a URL.</p></div></div><label className="field-label" htmlFor="repo-url">GitHub repository URL</label><div className="input-wrap"><GitFork /><input id="repo-url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://github.com/org/repository" disabled={!!repository || status === 'connecting' || status === 'indexing'} /></div><label className="field-label" htmlFor="branch">Branch <span className="muted">optional</span></label><div className="input-wrap"><GitBranch /><input id="branch" value={branch} onChange={e => setBranch(e.target.value)} placeholder="Default branch" disabled={!!repository || status === 'connecting' || status === 'indexing'} /></div><button className="button primary full" disabled={!url.trim() || !!repository || status === 'connecting'} onClick={handleConnect}>{status === 'connecting' ? <><Activity className="spin" /> Connecting…</> : repository ? <><Check /> Repository cloned</> : <><GitFork /> Connect repository</>}</button>{repository && <div className="connection-status"><span className="status-dot" /><div><strong>{repository.owner}/{repository.name}</strong><span className="mono">{repository.repository_id}</span></div></div>}{error && <div className="error-message" role="alert">{error}</div>}</div><div className="panel process-panel"><div className="step-label"><span className={`step-number ${status === 'ready' ? 'done' : repository ? 'active' : ''}`}>{status === 'ready' ? <Check /> : '2'}</span><div><h2>Clone and index</h2><p>Two separate steps keep status transparent.</p></div></div><div className={`process-item ${repository ? 'complete' : ''}`}><div className="process-icon"><DownloadIcon /></div><div><strong>Clone repository</strong><span>{repository ? `Cloned ${repository.owner}/${repository.name} successfully.` : 'Waiting for a repository connection.'}</span></div>{repository && <Check className="success-text" />}</div><div className="process-line" /><div className={`process-item ${status === 'ready' ? 'complete' : ''}`}><div className="process-icon"><Database /></div><div><strong>Index source</strong><span>{indexResult ? `${indexResult.analyzed_files.toLocaleString()} files · ${indexResult.total_chunks.toLocaleString()} chunks · ${indexResult.relationships.toLocaleString()} relationships` : repository ? 'Ready to analyze source and generate embeddings.' : 'Embeddings and relationships are created here.'}</span></div>{status === 'indexing' ? <span className="badge muted-badge"><Activity className="spin" /> Indexing…</span> : indexResult ? <Check className="success-text" /> : repository ? <button className="button secondary" onClick={handleIndex}>Start indexing <ArrowRight /></button> : <span className="badge muted-badge">Locked</span>}</div>{indexResult && <div className="index-result"><div className="eyebrow">INDEXING RESULT</div><div className="result-metrics"><span><strong>{indexResult.embedded_chunks.toLocaleString()}</strong> embedded</span><span><strong>{indexResult.reused_chunks.toLocaleString()}</strong> reused</span><span><strong>{indexResult.deleted_chunks.toLocaleString()}</strong> deleted</span></div><button className="button primary full" onClick={() => onConnected(repository!, indexResult)}>Open overview <ArrowRight /></button></div>}</div></div></>
}

function DownloadIcon() { return <Upload className="rotate-180" /> }

function SearchScreen({ repositoryId, initialQuery }: { repositoryId: string | null; initialQuery: string }) {
  const [query, setQuery] = useState(initialQuery || '')
  const [topK, setTopK] = useState('8')
  const [result, setResult] = useState<RepositorySearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)

  async function runSearch() {
    if (!repositoryId) { setError('Connect a repository before searching.'); return }
    if (!query.trim()) { setError('Enter a search query.'); return }
    setLoading(true)
    setError('')
    setResult(null)
    setHasSearched(true)
    try {
      const response = await searchRepository(repositoryId, { query: query.trim(), top_k: Number(topK) })
      setResult(response)
    } catch (cause) {
      setResult(null)
      setError(cause instanceof Error ? cause.message : 'Search failed. Check the backend logs.')
    } finally {
      setLoading(false)
    }
  }

  async function copyCode(content: string) {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(content)
      window.setTimeout(() => setCopied(null), 1200)
    } catch {
      setError('Clipboard access was blocked by the browser.')
    }
  }

  return <><PageHeader eyebrow="SEARCH / SEMANTIC" title="Semantic code search" description="Find concepts and implementations across the indexed repository." /><form className="search-bar" onSubmit={event => { event.preventDefault(); if (!loading) void runSearch() }}><Search /><input aria-label="Semantic search query" value={query} onChange={event => setQuery(event.target.value)} placeholder="Describe the code or concept you want to find" /><span className="kbd">↵ Enter</span><button type="submit" className="button primary" disabled={loading || !repositoryId || !query.trim()}>{loading ? <><Activity className="spin" /> Searching…</> : 'Search'}</button></form><div className="search-toolbar"><span className="muted">{result ? `${result.result_count} results for “${result.query}”` : hasSearched && !loading ? 'No results' : 'Search the active repository'}</span><div className="toolbar-actions"><label className="select-label">Top K <select value={topK} onChange={event => setTopK(event.target.value)}><option value="8">8</option><option value="12">12</option><option value="20">20</option></select></label><span className="muted">Active repository only</span></div></div>{error && <div className="error-message" role="alert">{error}</div>}{!repositoryId && <div className="empty-answer"><h2>No active repository</h2><p>Connect and index a repository before running semantic search.</p></div>}{loading && <div className="panel muted">Embedding query and retrieving source chunks…</div>}{result && result.results.length === 0 && !loading && <div className="panel empty-answer"><h2>No matching code found</h2><p>Try different wording or increase Top K.</p></div>}<div className="search-results">{result?.results.map((item, index) => <div className="result-card" key={`${item.file_path}:${item.start_line}:${item.symbol_id}`}><div className="result-heading"><div><span className="result-index">{String(index + 1).padStart(2, '0')}</span><strong>{item.symbol_name || item.file_path}</strong><span className="type-chip">{item.kind}</span></div><span className="relevance"><Sparkles /> {item.score.toFixed(3)} similarity</span></div><div className="result-meta"><span className="mono"><FileCode2 /> {item.file_path}</span><span className="mono">Lines {item.start_line}–{item.end_line}</span><span className="lang-dot" /> {item.language}</div><div className="code-preview"><div className="code-top"><span>indexed source</span><button className="icon-button" onClick={() => void copyCode(item.content)} aria-label="Copy source">{copied === item.content ? <Check /> : <Copy />}</button></div><pre><code>{item.content}</code></pre></div></div>)}</div></>
}

function AskScreen({ repositoryId, conversation, onConversationChange }: { repositoryId: string | null; conversation: AskConversationState; onConversationChange: (conversation: AskConversationState) => void }) {
  const question = conversation.draft
  const result = conversation.entries.at(-1)?.response ?? null
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function runAsk() {
    if (!repositoryId) { setError('Connect a repository before asking questions.'); return }
    if (!question.trim()) { setError('Enter a question about the repository.'); return }
    setLoading(true)
    setError('')
    try {
      const response = await askRepository(repositoryId, { query: question.trim(), top_k: 6, context_limit: 8 })
      onConversationChange({
        draft: '',
        entries: [...conversation.entries, { query: question.trim(), response }],
      })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The question could not be answered.')
    } finally {
      setLoading(false)
    }
  }

  return <><PageHeader eyebrow="ASK / REPOSITORY Q&A" title="Ask RepoX" description="Answers are generated from retrieved source in the active repository and linked to validated evidence." /><div className="ask-layout"><div className="ask-answer panel"><div className="answer-top"><div className="assistant-avatar"><Sparkles /></div><div><strong>RepoX conversation</strong>{result && <span className="muted">Latest answer by {result.model}</span>}</div>{result && <span className={`badge ${result.citations.length ? 'success' : 'muted-badge'}`}>{conversation.entries.length} answers</span>}</div>{loading ? <div className="empty-answer"><Activity className="spin" /><h2>Retrieving evidence and generating an answer…</h2><p>This may take a little while when the local model is loading.</p></div> : result ? <div className="conversation-history">{conversation.entries.map((entry, index) => <div className="answer-body conversation-entry" key={`${entry.query}:${index}`}><p className="conversation-question"><strong>You:</strong> {entry.query}</p><div className="answer-text" dangerouslySetInnerHTML={{ __html: renderDebugMarkdown(entry.response.answer) }} />{entry.response.citation_fallback_used && <div className="evidence-box"><strong>Evidence-only fallback</strong><p>The model did not produce a citation-compliant answer. The response contains retrieved source excerpts rather than a synthesized explanation.</p></div>}{entry.response.citations.length > 0 && <div className="evidence-box"><div className="eyebrow">VALIDATED SOURCE CITATIONS</div>{entry.response.citations.map(citation => <p className="mono" key={`${citation.file_path}:${citation.start_line}:${citation.end_line}`}>{citation.file_path}:{citation.start_line}–{citation.end_line}</p>)}</div>}</div>)}</div> : <div className="empty-answer"><Sparkles /><h2>Ask a question about your repository</h2><p>RepoX retrieves relevant source, then generates an answer with validated citations.</p></div>}</div><div className="ask-composer panel"><div className="composer-label"><span>Repository question</span><span className="muted mono">Ctrl / ⌘ + Enter</span></div><textarea value={question} onChange={event => onConversationChange({ ...conversation, draft: event.target.value })} placeholder="e.g. How is Dijkstra's shortest path algorithm implemented?" onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !loading) { event.preventDefault(); void runAsk() } }} /><div className="composer-footer"><span className="muted">Uses the currently selected repository</span><button className="button primary" onClick={() => void runAsk()} disabled={loading || !repositoryId}>{loading ? <><Activity className="spin" /> Asking…</> : <><Send /> Ask RepoX</>}</button></div>{error && <div className="error-message" role="alert">{error}</div>}</div></div></>
}

function DebugScreen({ repositoryId }: { repositoryId: string | null }) {
  const [description, setDescription] = useState('')
  const [traceback, setTraceback] = useState('')
  const [result, setResult] = useState<RepositoryDebugResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function investigate() {
    if (!repositoryId || (!description.trim() && !traceback.trim()) || loading) return
    setLoading(true); setError(''); setResult(null)
    try { setResult(await debugRepository(repositoryId, { description, traceback })) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Debug request failed.') }
    finally { setLoading(false) }
  }

  return <>
    <PageHeader eyebrow="DEBUG / PYTHON INVESTIGATION" title="Debug an issue" description="Combine a bug report and traceback with source-grounded repository evidence." />
    <div className="debug-layout">
      <section className="panel debug-form">
        <label className="field-label" htmlFor="bug-description">What went wrong?</label>
        <textarea id="bug-description" value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe the unexpected behavior, inputs, and what you expected instead." />
        <label className="field-label" htmlFor="bug-traceback">Python traceback <span className="muted">optional</span></label>
        <textarea id="bug-traceback" className="traceback-input" value={traceback} onChange={e => setTraceback(e.target.value)} placeholder={'Traceback (most recent call last):\n  File "src/app.py", line 42, in run\n    process()\nValueError: invalid input'} />
        {!repositoryId && <div className="error-message">Connect and index a repository before debugging.</div>}
        {error && <div className="error-message" role="alert">{error}</div>}
        <div className="composer-footer"><span className="muted">Traceback parsing is deterministic; diagnosis uses indexed source.</span><button className="button primary" disabled={!repositoryId || (!description.trim() && !traceback.trim()) || loading} onClick={investigate}>{loading ? <><Activity className="spin" /> Investigating…</> : <><BugIcon /> Investigate</>}</button></div>
      </section>
      <section className="panel debug-result">
        {!result ? <div className="empty-answer"><BugIcon /><h2>Investigation results</h2><p>Submit a description or traceback to inspect parsed frames, likely causes and supporting source citations.</p></div> : <>
          <div className="answer-top"><div className="assistant-avatar"><BugIcon /></div><div><strong>Debugging report</strong><span className="muted">Generated by {result.model}</span></div>{result.citation_fallback_used && <span className="badge muted-badge">Evidence fallback</span>}</div>
          <div className="debug-facts">
            <div><span className="eyebrow">EXCEPTION</span><strong>{result.exception_type ?? 'Not detected'}</strong><span>{result.exception_message || 'No exception message parsed'}</span></div>
            <div><span className="eyebrow">TRACEBACK FRAMES</span><strong>{result.frames.length}</strong><span>{result.innermost_frame ? `${result.innermost_frame.path}:${result.innermost_frame.line} · ${result.innermost_frame.function}` : 'No standard frames detected'}</span></div>
          </div>
          {result.frames.length > 0 && <div className="detail-block"><strong>Execution frames · outermost to innermost</strong>{result.frames.map((frame, index) => <div className="relationship" key={`${frame.path}:${frame.line}:${index}`}><span className="mono">{index + 1}. {frame.path}:{frame.line}</span><span>in {frame.function}</span></div>)}</div>}
          <div className="debug-answer" dangerouslySetInnerHTML={{ __html: renderDebugMarkdown(result.answer) }} />
          <div className="detail-block"><strong>Validated source citations ({result.citations.length})</strong>{result.citations.map(citation => <div className="relationship" key={`${citation.file_path}:${citation.start_line}:${citation.end_line}`}><FileCode2 /><span className="mono">{citation.file_path}:{citation.start_line}–{citation.end_line}</span></div>)}</div>
        </>}
      </section>
    </div>
  </>
}

function renderDebugMarkdown(markdown: string): string {
  const escapeHtml = (value: string) => value.replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char] ?? char)
  const inline = (value: string) => escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
  const blocks = markdown.split(/```([\w+-]*)\n([\s\S]*?)```/g)
  let html = ''
  for (let index = 0; index < blocks.length; index += 1) {
    if (index % 3 === 1) {
      const code = blocks[index + 1] ?? ''
      html += `<pre><code>${escapeHtml(code.trimEnd())}</code></pre>`
      index += 1
      continue
    }
    const lines = (blocks[index] ?? '').split('\n')
    let paragraph: string[] = []
    let list: string[] = []
    let listType: 'ul' | 'ol' | null = null
    const flushParagraph = () => { if (paragraph.length) { html += `<p>${paragraph.map(inline).join('<br />')}</p>`; paragraph = [] } }
    const flushList = () => { if (list.length && listType) { html += `<${listType}>${list.map(item => `<li>${inline(item)}</li>`).join('')}</${listType}>`; list = [] }; listType = null }
    for (const line of lines) {
      const heading = line.match(/^(#{1,3})\s+(.+)$/)
      const bullet = line.match(/^\s*[-*]\s+(.+)$/)
      const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/)
      if (heading) { flushParagraph(); flushList(); const level = heading[1].length; html += `<h${level}>${inline(heading[2])}</h${level}>` }
      else if (bullet || numbered) {
        flushParagraph()
        const nextType = bullet ? 'ul' : 'ol'
        if (listType && listType !== nextType) flushList()
        listType = nextType
        list.push((bullet ?? numbered)![1])
      } else if (!line.trim()) { flushParagraph(); flushList() }
      else { flushList(); paragraph.push(line) }
    }
    flushParagraph(); flushList()
  }
  return html
}

function Citation({ path, lines }: { path: string; lines: string }) { return <button className="citation"><FileCode2 /> <span className="mono">{path}</span><span className="mono muted">:{lines}</span></button> }

function GraphScreen({ repositoryId, selectedNode, setSelectedNode }: { repositoryId: string | null; selectedNode: string; setSelectedNode: (s: string) => void }) {
  const [graph, setGraph] = useState<RepositoryGraphResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [visibleIds, setVisibleIds] = useState<string[]>([])
  const [nodeTypes, setNodeTypes] = useState<string[]>(['file', 'class', 'function'])
  const [relationshipKinds, setRelationshipKinds] = useState<string[]>([])
  const [symbolQuery, setSymbolQuery] = useState('')
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const dragStart = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null)

  useEffect(() => {
    if (!repositoryId) {
      setGraph(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getRepositoryGraph(repositoryId)
      .then(value => { if (!cancelled) { const initial = initialGraphNodeIds(value); setGraph(value); setVisibleIds(initial); setRelationshipKinds(Object.keys(value.summary.relationship_kinds)); setSelectedNode(initial[0] ?? ''); setZoom(1); setPan({ x: 0, y: 0 }) } })
      .catch(cause => { if (!cancelled) setError(cause instanceof Error ? cause.message : 'Could not load repository graph.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [repositoryId, setSelectedNode])

  const allVisibleIds = useMemo(() => new Set(visibleIds), [visibleIds])
  const visibleNodes = useMemo(() => (graph?.nodes ?? []).filter(node => allVisibleIds.has(node.id) && nodeTypes.includes(node.kind)), [allVisibleIds, graph, nodeTypes])
  const displayedIds = useMemo(() => new Set(visibleNodes.map(node => node.id)), [visibleNodes])
  const visibleEdges = useMemo(() => (graph?.edges ?? []).filter(edge => displayedIds.has(edge.source) && displayedIds.has(edge.target) && relationshipKinds.includes(edge.kind)), [displayedIds, graph, relationshipKinds])
  const positions = useMemo(() => graphNodePositions(visibleNodes.map(node => node.id)), [visibleNodes])
  const selected = graph?.nodes.find(node => node.id === selectedNode) ?? visibleNodes[0]
  const outgoing = (graph?.edges ?? []).filter(edge => edge.source === selected?.id)
  const incoming = (graph?.edges ?? []).filter(edge => edge.target === selected?.id)
  const focusSymbol = () => {
    const query = symbolQuery.trim().toLowerCase()
    const match = graph?.nodes.find(node => node.name.toLowerCase().includes(query) || node.path.toLowerCase().includes(query) || node.id.toLowerCase().includes(query))
    if (!graph || !match) return
    setVisibleIds(current => expandGraphNodeIds(graph, current, match.id))
    setSelectedNode(match.id)
  }
  const toggle = (value: string, setValue: (next: string[]) => void, current: string[]) => setValue(current.includes(value) ? current.filter(item => item !== value) : [...current, value])

  return <>
    <PageHeader eyebrow="EXPLORE / RELATIONSHIPS" title="Code graph" description="Explore actual files, symbols and relationships extracted from the indexed repository." />
    {!repositoryId && <div className="panel"><p>Connect and index a repository to inspect its code graph.</p></div>}
    {loading && <div className="panel"><p className="muted">Building repository graph…</p></div>}
    {error && <div className="panel error-message" role="alert">{error}</div>}
    {graph && <>
      <div className="stats-grid">
        {[['Files', graph.summary.files], ['Symbols', graph.summary.symbols], ['Classes', graph.summary.classes], ['Functions', graph.summary.functions]].map(([label, value]) => <div className="stat-card" key={label as string}><div className="stat-top"><span>{label as string}</span><Network /></div><strong>{Number(value).toLocaleString()}</strong><small>Python analysis</small></div>)}
      </div>
      <div className="graph-layout">
      <div className="panel graph-panel">
        <div className="graph-toolbar">
          <div className="legend"><span><i className="legend-dot primary" /> Classes</span><span><i className="legend-dot violet" /> Functions</span><span><i className="legend-dot success" /> Files</span></div>
          <span className="muted mono">{visibleNodes.length} / {graph.nodes.length} nodes · {visibleEdges.length} / {graph.edges.length} edges</span>
        </div>
        <div className="graph-controls"><form onSubmit={event => { event.preventDefault(); focusSymbol() }}><input aria-label="Find graph symbol" value={symbolQuery} onChange={event => setSymbolQuery(event.target.value)} placeholder="Find a symbol or file" /><button className="icon-button" type="submit" aria-label="Focus graph symbol"><Search /></button></form><div className="graph-filters"><span>Nodes</span>{['file', 'class', 'function'].map(kind => <label key={kind}><input type="checkbox" checked={nodeTypes.includes(kind)} onChange={() => toggle(kind, setNodeTypes, nodeTypes)} />{kind}</label>)}<span>Edges</span>{Object.keys(graph.summary.relationship_kinds).map(kind => <label key={kind}><input type="checkbox" checked={relationshipKinds.includes(kind)} onChange={() => toggle(kind, setRelationshipKinds, relationshipKinds)} />{kind}</label>)}</div><div className="graph-zoom"><button className="icon-button" onClick={() => setZoom(value => Math.max(.5, value - .15))} aria-label="Zoom out"><Minus /></button><button className="icon-button" onClick={() => setZoom(value => Math.min(2, value + .15))} aria-label="Zoom in"><Plus /></button><button className="icon-button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} aria-label="Fit graph to view"><Maximize2 /></button></div></div>
        {visibleNodes.length === 0 ? <div className="graph-empty"><Network /><h2>No relationships match these filters</h2><p>Choose a node type or relationship filter with extracted graph data.</p></div> : <div className="graph-canvas" onPointerDown={event => { dragStart.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y }; event.currentTarget.setPointerCapture(event.pointerId) }} onPointerMove={event => { const start = dragStart.current; if (start) setPan({ x: start.panX + event.clientX - start.x, y: start.panY + event.clientY - start.y }) }} onPointerUp={() => { dragStart.current = null }}>
          <div className="graph-stage" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
          <svg className="edges" viewBox="0 0 1000 600" aria-hidden="true"><defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" /></marker></defs>
            {visibleEdges.map((edge, index) => {
              const from = positions.get(edge.source)
              const to = positions.get(edge.target)
              if (!from || !to) return null
              const x = (from.x + to.x) / 2
              const y = (from.y + to.y) / 2
              return <g key={`${edge.source}-${edge.target}-${edge.kind}-${index}`}><line x1={from.x} y1={from.y} x2={to.x} y2={to.y} markerEnd="url(#graph-arrow)" /><text x={x} y={y}>{edge.kind}</text></g>
            })}
          </svg>
          {visibleNodes.map(node => {
            const point = positions.get(node.id)
            if (!point) return null
            const tone = node.kind === 'class' ? 'primary' : node.kind === 'file' ? 'success' : 'violet'
            return <button key={node.id} title={`${node.path}${node.start_line ? `:${node.start_line}` : ''}`} className={`graph-node ${tone} ${selected?.id === node.id ? 'selected' : ''}`} style={{ left: point.x, top: point.y }} onPointerDown={event => event.stopPropagation()} onClick={() => setSelectedNode(node.id)}><span className="node-symbol">{node.kind === 'class' ? <Code2 /> : node.kind === 'file' ? <FolderGit2 /> : <TerminalSquare />}</span><span>{node.name}</span><small>{node.kind}</small></button>
          })}
          </div>
        </div>
        }
        <p className="muted graph-limit-note">Showing an explorable subset of the complete graph. Select a node then expand its actual neighbors; at most {MAX_GRAPH_NODE_LIMIT} nodes render at once.</p>
      </div>
      <div className="panel node-details">
        {selected ? <>
          <div className="eyebrow">SELECTED {selected.kind.toUpperCase()}</div>
          <h2>{selected.name}</h2>
          <span className="badge">{selected.language}</span>
          <button className="button secondary" onClick={() => graph && setVisibleIds(current => expandGraphNodeIds(graph, current, selected.id))} disabled={!graph || visibleIds.length >= MAX_GRAPH_NODE_LIMIT}>Expand neighbors</button>
          <div className="detail-block"><span className="eyebrow">SOURCE LOCATION</span><strong className="mono">{selected.path}{selected.start_line ? `:${selected.start_line}${selected.end_line && selected.end_line !== selected.start_line ? `–${selected.end_line}` : ''}` : ''}</strong></div>
          <div className="detail-block"><span className="eyebrow">OUTGOING RELATIONSHIPS ({outgoing.length})</span>{outgoing.slice(0, 8).map((edge, index) => <div className="relationship" key={`${edge.target}-${index}`}><ArrowRight /> {edge.kind} <span className="mono">{graph.nodes.find(node => node.id === edge.target)?.name ?? edge.target}</span></div>)}{outgoing.length === 0 && <span className="muted">No outgoing relationships.</span>}</div>
          <div className="detail-block"><span className="eyebrow">INCOMING RELATIONSHIPS ({incoming.length})</span>{incoming.slice(0, 8).map((edge, index) => <div className="relationship" key={`${edge.source}-${index}`}><ArrowRight /> {edge.kind} from <span className="mono">{graph.nodes.find(node => node.id === edge.source)?.name ?? edge.source}</span></div>)}{incoming.length === 0 && <span className="muted">No incoming relationships.</span>}</div>
        </> : <p className="muted">No graph nodes were extracted.</p>}
      </div>
      </div>
      <div className="panel repo-details"><div className="panel-heading"><div><h2>Repository composition</h2><p>Counts derived from the deterministic analysis graph.</p></div><BarChart3 /></div><div className="detail-grid">{Object.entries(graph.summary.languages).map(([language, count]) => <div key={language}><span className="eyebrow">{language.toUpperCase()}</span><strong>{count} files</strong></div>)}{Object.entries(graph.summary.relationship_kinds).map(([kind, count]) => <div key={kind}><span className="eyebrow">{kind.toUpperCase()}</span><strong>{count} relationships</strong></div>)}</div></div>
    </>}
  </>
}

function SettingsScreen({ dark, setDark }: { dark: boolean; setDark: (v: boolean) => void }) { return <><PageHeader eyebrow="WORKSPACE / PREFERENCES" title="Settings" description="Configure how RepoX looks and connects to your repository workspace." /><div className="settings-stack"><div className="panel settings-section"><div><h2>Appearance</h2><p>Choose a theme that works best for your environment.</p></div><div className="theme-options"><button className={`theme-option ${dark ? 'selected' : ''}`} onClick={() => setDark(true)}><Moon /><strong>Dark</strong><span>Low contrast for long sessions</span>{dark && <Check />}</button><button className={`theme-option ${!dark ? 'selected' : ''}`} onClick={() => setDark(false)}><Sun /><strong>Light</strong><span>Bright and clear during the day</span>{!dark && <Check />}</button></div></div><div className="panel settings-section"><div><h2>Backend connection</h2><p>RepoX frontend is connected to the existing FastAPI service.</p></div><div className="connection-status"><span className="status-dot" /><div><strong>Connected</strong><span className="mono">GET /health · 42ms</span></div><button className="button ghost">Test connection</button></div></div><div className="panel settings-section"><div><h2>Workspace preferences</h2><p>Defaults used across search and graph exploration.</p></div><div className="preference-row"><span>Default result count</span><select defaultValue="8"><option>8 results</option><option>12 results</option><option>20 results</option></select></div><div className="preference-row"><span>Show source previews</span><span className="toggle on"><span /></span></div></div></div></> }
