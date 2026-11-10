'use client'

import { useEffect, useMemo, useState } from 'react'
import { createRepository, indexRepository, listRepositories, type RepositoryCreateResponse, type RepositoryIndexResponse } from '@/lib/api'
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
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
  Moon,
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

type Screen = 'overview' | 'onboarding' | 'search' | 'ask' | 'graph' | 'settings'

const navItems: { id: Screen; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'search', label: 'Semantic search', icon: Search },
  { id: 'ask', label: 'Ask RepoX', icon: CircleHelp },
  { id: 'graph', label: 'Code graph', icon: Network },
]

const searchResults = [
  { path: 'src/indexer/embeddings.ts', symbol: 'createEmbedding', type: 'Function', lang: 'TypeScript', lines: '42–68', score: '0.96', code: 'export async function createEmbedding\n  (content: string): Promise<number[]> {\n  const response = await embeddings.embed({\n    model: EMBEDDING_MODEL, input: content,\n  })\n  return response.embedding\n}' },
  { path: 'src/search/vector-store.ts', symbol: 'searchSimilarChunks', type: 'Function', lang: 'TypeScript', lines: '18–57', score: '0.91', code: 'export async function searchSimilarChunks(\n  query: string, topK = 8\n): Promise<SearchResult[]> {\n  const vector = await createEmbedding(query)\n  return vectorStore.query({ vector, topK })\n}' },
  { path: 'src/models/repository.py', symbol: 'RepositoryStatus', type: 'Enum', lang: 'Python', lines: '9–16', score: '0.84', code: 'class RepositoryStatus(str, Enum):\n    PENDING = "pending"\n    CLONING = "cloning"\n    INDEXING = "indexing"\n    READY = "ready"'
  },
]

const graphNodes = [
  { id: 'RepositoryIndexer', kind: 'class', x: 20, y: 37, tone: 'primary' },
  { id: 'createEmbedding', kind: 'function', x: 53, y: 20, tone: 'violet' },
  { id: 'VectorStore', kind: 'class', x: 78, y: 38, tone: 'success' },
  { id: 'searchSimilarChunks', kind: 'function', x: 48, y: 68, tone: 'warning' },
  { id: 'Repository', kind: 'model', x: 82, y: 73, tone: 'muted' },
]

export function RepoXApp() {
  const [screen, setScreen] = useState<Screen>('overview')
  const [dark, setDark] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [repository, setRepository] = useState<RepositoryCreateResponse | null>(null)
  const [indexResult, setIndexResult] = useState<RepositoryIndexResponse | null>(null)
  const repo = repository ? `${repository.owner} / ${repository.name}` : 'No repository connected'
  const [query, setQuery] = useState('How are embeddings generated and stored?')
  const [searched, setSearched] = useState(false)
  const [question, setQuestion] = useState('')
  const [selectedNode, setSelectedNode] = useState('RepositoryIndexer')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function restoreWorkspace() {
      try {
        const repositories = await listRepositories()
        if (cancelled) return
        const active = repositories[0]
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
  }, [])

  const themeClass = dark ? 'dark' : 'light'
  const pageTitle = useMemo(() => ({ overview: 'Repository overview', onboarding: 'Connect a repository', search: 'Semantic code search', ask: 'Ask RepoX', graph: 'Code graph', settings: 'Settings' })[screen], [screen])

  return (
    <div className={themeClass}>
      <div className="repox-shell">
        <aside className={`repox-sidebar ${sidebarOpen ? 'is-open' : ''}`}>
          <div className="brand-row">
            <div className="brand-mark"><Code2 /></div>
            <div><div className="brand-name">RepoX</div><div className="brand-kicker">Repository intelligence</div></div>
            <button className="icon-button mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X /></button>
          </div>
          <div className="repo-switcher">
            <div className="repo-avatar"><GitFork /></div>
            <div className="repo-meta"><span className="eyebrow">ACTIVE REPOSITORY</span><strong>{repo}</strong><span className="mono muted">{repository ? `${repository.branch ?? 'default branch'} · ${indexResult ? 'indexed' : 'not indexed'}` : 'Connect a GitHub repository'}</span></div><ChevronDown className="muted" />
          </div>
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
          <header className="topbar"><button className="icon-button mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Menu /></button><div className="breadcrumbs"><span>acme</span><ChevronRight /><strong>{pageTitle}</strong></div><div className="top-actions"><button className="icon-button" aria-label="Activity"><Activity /></button><div className="avatar">JD</div></div></header>
          <div className="page-content">{screen === 'overview' && <Overview onNavigate={setScreen} repository={repository} indexResult={indexResult} />}{screen === 'onboarding' && <Onboarding onConnected={(value, result) => { setRepository(value); setIndexResult(result); setScreen('overview') }} />}{screen === 'search' && <SearchScreen query={query} setQuery={setQuery} searched={searched} onSearch={() => setSearched(true)} onCopy={() => { setCopied(true); setTimeout(() => setCopied(false), 1200) }} copied={copied} />}{screen === 'ask' && <AskScreen question={question} setQuestion={setQuestion} onAsk={() => setQuestion('')}/>} {screen === 'graph' && <GraphScreen selectedNode={selectedNode} setSelectedNode={setSelectedNode} />} {screen === 'settings' && <SettingsScreen dark={dark} setDark={setDark} />}</div>
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

function SearchScreen({ query, setQuery, searched, onSearch, onCopy, copied }: { query: string; setQuery: (s: string) => void; searched: boolean; onSearch: () => void; onCopy: () => void; copied: boolean }) { return <><PageHeader eyebrow="SEARCH / SEMANTIC" title="Semantic code search" description="Find concepts and implementations across the indexed repository." /><div className="search-bar"><Search /><input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') onSearch() }} /><span className="kbd">⌘ K</span><button className="button primary" onClick={onSearch}>Search</button></div><div className="search-toolbar"><span className="muted">{searched ? '3 results' : 'Try a natural-language query'}</span><div className="toolbar-actions"><label className="select-label">Top K <select defaultValue="8"><option>8</option><option>12</option><option>20</option></select></label><button className="button ghost"><Code2 /> All languages</button></div></div><div className="search-results">{searchResults.map((result, index) => <div className="result-card" key={result.path}><div className="result-heading"><div><span className="result-index">0{index + 1}</span><strong>{result.symbol}</strong><span className="type-chip">{result.type}</span></div><span className="relevance"><Sparkles /> {result.score} relevance</span></div><div className="result-meta"><span className="mono"><FileCode2 /> {result.path}</span><span className="mono">Lines {result.lines}</span><span className="lang-dot" /> {result.lang}</div><div className="code-preview"><div className="code-top"><span>source preview</span><button className="icon-button" onClick={onCopy} aria-label="Copy code">{copied ? <Check /> : <Copy />}</button></div><pre><code>{result.code}</code></pre></div></div>)}</div></> }

function AskScreen({ question, setQuestion, onAsk }: { question: string; setQuestion: (s: string) => void; onAsk: () => void }) { const [answered, setAnswered] = useState(false); return <><PageHeader eyebrow="ASK / REPOSITORY Q&A" title="Ask RepoX" description="Answers are generated from your repository and linked back to source evidence." /><div className="ask-layout"><div className="ask-answer panel"><div className="answer-top"><div className="assistant-avatar"><Sparkles /></div><div><strong>RepoX answer</strong>{answered && <span className="muted">Grounded in 3 source excerpts · just now</span>}</div>{answered && <span className="badge success"><Check /> Citations verified</span>}</div>{answered ? <div className="answer-body"><p>Embeddings are generated during the indexing pipeline in <Citation path="src/indexer/embeddings.ts" lines="42–68" />. The indexer sends normalized file chunks to the embedding model, then stores the resulting vectors alongside metadata.</p><p>Search uses the same embedding function to turn a natural-language query into a vector. <Citation path="src/search/vector-store.ts" lines="18–57" /> then queries the vector store with a configurable top-K value and returns the most similar chunks.</p><div className="evidence-box"><div className="eyebrow">RETRIEVED EVIDENCE</div><p className="mono">{'createEmbedding(content) → vectorStore.upsert({ vector, metadata })'}</p><span>Evidence fallback is shown separately from generated explanation.</span></div></div> : <div className="empty-answer"><Sparkles /><h2>Ask a question about your repository</h2><p>RepoX will retrieve relevant source, then explain the answer with verifiable citations.</p></div>}</div><div className="ask-composer panel"><div className="composer-label"><span>Repository question</span><span className="muted mono">⌘ Enter</span></div><textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="e.g. Where is authentication handled?" onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) { e.preventDefault(); setAnswered(true); onAsk() } }} /><div className="composer-footer"><span className="muted">Answers use the current <span className="mono">main</span> branch</span><button className="button primary" onClick={() => setAnswered(true)}><Send /> Ask RepoX</button></div></div></div></> }
function Citation({ path, lines }: { path: string; lines: string }) { return <button className="citation"><FileCode2 /> <span className="mono">{path}</span><span className="mono muted">:{lines}</span></button> }

function GraphScreen({ selectedNode, setSelectedNode }: { selectedNode: string; setSelectedNode: (s: string) => void }) { const node = graphNodes.find(n => n.id === selectedNode) ?? graphNodes[0]; return <><PageHeader eyebrow="EXPLORE / RELATIONSHIPS" title="Code graph" description="Trace how symbols connect across the repository." action={<button className="button ghost"><Search /> Find symbol</button>} /><div className="graph-layout"><div className="panel graph-panel"><div className="graph-toolbar"><div className="legend"><span><i className="legend-dot primary" /> Classes</span><span><i className="legend-dot violet" /> Functions</span><span><i className="legend-dot success" /> Models</span></div><span className="muted mono">5 nodes · 6 edges</span></div><div className="graph-canvas"><svg className="edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><path d="M22 39 C35 32 39 25 52 23" /><path d="M56 24 C67 26 71 33 77 39" /><path d="M25 42 C31 55 40 63 49 68" /><path d="M55 69 C66 72 75 72 80 72" /><path d="M78 43 C80 54 81 61 82 70" /><path d="M50 65 C58 52 64 44 75 41" /></svg>{graphNodes.map(n => <button key={n.id} className={`graph-node ${n.tone} ${selectedNode === n.id ? 'selected' : ''}`} style={{ left: `${n.x}%`, top: `${n.y}%` }} onClick={() => setSelectedNode(n.id)}><span className="node-symbol">{n.kind === 'class' ? <Code2 /> : n.kind === 'model' ? <Database /> : <TerminalSquare />}</span><span>{n.id}</span><small>{n.kind}</small></button>)}</div></div><div className="panel node-details"><div className="eyebrow">SELECTED SYMBOL</div><h2>{node.id}</h2><span className="badge">{node.kind}</span><div className="detail-block"><span className="eyebrow">LOCATION</span><strong className="mono">src/indexer/indexer.ts:24</strong></div><div className="detail-block"><span className="eyebrow">RELATIONSHIPS</span><div className="relationship"><ArrowRight /> calls <span className="mono">createEmbedding</span></div><div className="relationship"><ArrowRight /> writes to <span className="mono">VectorStore</span></div><div className="relationship"><ArrowRight /> imported by <span className="mono">main.py</span></div></div><button className="button secondary full"><FileCode2 /> Open source</button></div></div></> }

function SettingsScreen({ dark, setDark }: { dark: boolean; setDark: (v: boolean) => void }) { return <><PageHeader eyebrow="WORKSPACE / PREFERENCES" title="Settings" description="Configure how RepoX looks and connects to your repository workspace." /><div className="settings-stack"><div className="panel settings-section"><div><h2>Appearance</h2><p>Choose a theme that works best for your environment.</p></div><div className="theme-options"><button className={`theme-option ${dark ? 'selected' : ''}`} onClick={() => setDark(true)}><Moon /><strong>Dark</strong><span>Low contrast for long sessions</span>{dark && <Check />}</button><button className={`theme-option ${!dark ? 'selected' : ''}`} onClick={() => setDark(false)}><Sun /><strong>Light</strong><span>Bright and clear during the day</span>{!dark && <Check />}</button></div></div><div className="panel settings-section"><div><h2>Backend connection</h2><p>RepoX frontend is connected to the existing FastAPI service.</p></div><div className="connection-status"><span className="status-dot" /><div><strong>Connected</strong><span className="mono">GET /health · 42ms</span></div><button className="button ghost">Test connection</button></div></div><div className="panel settings-section"><div><h2>Workspace preferences</h2><p>Defaults used across search and graph exploration.</p></div><div className="preference-row"><span>Default result count</span><select defaultValue="8"><option>8 results</option><option>12 results</option><option>20 results</option></select></div><div className="preference-row"><span>Show source previews</span><span className="toggle on"><span /></span></div></div></div></> }
