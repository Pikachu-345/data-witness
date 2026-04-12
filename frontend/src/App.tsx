import { useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Database, Upload, Cpu, X, BookOpen, ChevronDown,
  Sparkles, GitBranch, BarChart3, Shield, Zap, Brain,
  Play, Target, Eye, MessageSquare, Search, Layers, Table2, PenTool, Clock,
  Download,
} from 'lucide-react'
import { uploadDataset, useSampleDataset, runQuery } from './api/client'
import type { DatasetInfo, QueryResponse, HistoryItem } from './types'
import { QueryInput } from './components/QueryInput'
import { ResultTabs } from './components/ResultTabs'
import { DatasetProfileView } from './components/DatasetProfileView'
import { SmartInsightsPanel } from './components/SmartInsightsPanel'
import { FiltersBar } from './components/FiltersBar'
import { QuickActions } from './components/QuickActions'
import { DataPreview } from './components/DataPreview'
import { ChartBuilder } from './components/ChartBuilder'

const FEATURES = [
  { icon: Brain,     label: 'Smart Intent',       desc: 'Auto-classifies your question type', color: '#7c3aed', cls: 'feature-purple' },
  { icon: BarChart3, label: 'Verified Numbers',   desc: 'Pandas computes, LLM only explains',  color: '#0ea5e9', cls: 'feature-teal' },
  { icon: GitBranch, label: 'Knowledge Graph',    desc: 'Interactive reasoning visualisation',  color: '#22c55e', cls: 'feature-green' },
  { icon: Zap,       label: 'What-If Engine',     desc: 'Counterfactual scenario analysis',     color: '#f59e0b', cls: 'feature-amber' },
  { icon: Shield,    label: 'Audit Trail',        desc: 'Every number fully traceable',         color: '#f43f5e', cls: 'feature-coral' },
]

const HOW_STEPS = [
  { n: '01', icon: Upload, title: 'Upload Any CSV', desc: 'Auto-detects columns, metrics & dimensions' },
  { n: '02', icon: MessageSquare, title: 'Ask in English', desc: 'No SQL, no code — just questions' },
  { n: '03', icon: Target, title: 'AI Reasons', desc: 'Classifies, computes, builds reasoning' },
  { n: '04', icon: Eye, title: 'Verified Answer', desc: 'Numbers + graph + audit trail' },
]

type DashTab = 'ask' | 'data' | 'build'

export default function App() {
  const [dataset,     setDataset]     = useState<DatasetInfo | null>(null)
  const [result,      setResult]      = useState<QueryResponse | null>(null)
  const [history,     setHistory]     = useState<HistoryItem[]>([])
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState<string | null>(null)
  const [eli5,        setEli5]        = useState(false)
  const [uploading,   setUploading]   = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [dashTab,     setDashTab]     = useState<DashTab>('ask')
  const [filters,     setFilters]     = useState<Record<string, string>>({})
  const [dateRange,   setDateRange]   = useState<{ start: string; end: string } | null>(null)
  const featRef = useRef<HTMLDivElement>(null)
  const howRef  = useRef<HTMLDivElement>(null)

  const handleSample = useCallback(async () => {
    setUploading(true); setError(null)
    try { const info = await useSampleDataset(); setDataset(info); setResult(null); setShowProfile(false); setDashTab('ask') }
    catch (e: any) { setError(e.response?.data?.detail || 'Failed to load sample.') }
    finally { setUploading(false) }
  }, [])

  const handleUpload = useCallback(async (file: File) => {
    setUploading(true); setError(null)
    try { const info = await uploadDataset(file); setDataset(info); setResult(null); setShowProfile(true); setDashTab('ask') }
    catch (e: any) { setError(e.response?.data?.detail || 'Upload failed.') }
    finally { setUploading(false) }
  }, [])

  const handleQuery = useCallback(async (question: string) => {
    if (!dataset) return
    setLoading(true); setError(null); setDashTab('ask')
    try {
      const res = await runQuery(question, dataset.session_id, eli5, filters, dateRange)
      setResult(res)
      setHistory(h => [{ question, intent: res.intent, narrative: res.narrative, timestamp: new Date().toLocaleTimeString() }, ...h.slice(0, 19)])
    } catch (e: any) { setError(e.response?.data?.detail || 'Query failed.') }
    finally { setLoading(false) }
  }, [dataset, eli5, filters, dateRange])

  const suggestions = dataset?.suggested_queries ?? []
  const profile = dataset?.profile ?? {}

  /* ═══════════════════════════════════════════════════════════════ */
  /*  DASHBOARD                                                     */
  /* ═══════════════════════════════════════════════════════════════ */
  if (dataset) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--bg-deep)' }}>
        {/* Header */}
        <header className="hero-gradient sticky top-0 z-50 flex items-center justify-between px-6 h-14">
          <div className="flex items-center gap-3">
            <Cpu size={18} className="text-white/80" />
            <span className="font-extrabold text-white text-sm tracking-tight">DataWitness</span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold"
              style={{ background: 'rgba(255,255,255,0.12)', color: 'white' }}>
              <Database size={11} /> {dataset.row_count.toLocaleString()} rows
            </div>
            <button onClick={() => setEli5(v => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold"
              style={{ background: 'rgba(255,255,255,0.15)', color: 'white', cursor: 'pointer', border: 'none' }}>
              <BookOpen size={11} /> {eli5 ? 'Simple' : 'Analyst'}
            </button>
            <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer"
              style={{ background: 'rgba(255,255,255,0.2)', color: 'white' }}>
              <Upload size={11} /> Upload
              <input type="file" accept=".csv" className="hidden" onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])} />
            </label>
            <button onClick={() => { setDataset(null); setResult(null); setHistory([]); setFilters({}); setDateRange(null) }}
              className="text-white/40 hover:text-white/80" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
              <X size={15} />
            </button>
          </div>
        </header>

        {/* Dashboard tabs */}
        {!showProfile && (
          <div className="max-w-5xl mx-auto px-6 pt-5">
            <div className="flex gap-1 p-1 rounded-2xl mb-5" style={{ background: '#f3f0ff', display: 'inline-flex' }}>
              {([
                { id: 'ask' as DashTab,   icon: Search,   label: 'Ask AI' },
                { id: 'data' as DashTab,  icon: Table2,   label: 'Data' },
                { id: 'build' as DashTab, icon: PenTool,  label: 'Chart Builder' },
              ]).map(t => (
                <button key={t.id} onClick={() => setDashTab(t.id)}
                  className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-sm font-bold transition-all"
                  style={{
                    background: dashTab === t.id ? 'linear-gradient(135deg, #42145F, #7c3aed)' : 'transparent',
                    color: dashTab === t.id ? 'white' : '#7c6b96',
                    boxShadow: dashTab === t.id ? '0 2px 10px rgba(66,20,95,0.2)' : 'none',
                    border: 'none', cursor: 'pointer',
                  }}>
                  <t.icon size={14} /> {t.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Profile view */}
        {showProfile && (
          <div className="max-w-5xl mx-auto px-6 py-8">
            <DatasetProfileView dataset={dataset} onStartQuerying={() => setShowProfile(false)} />
          </div>
        )}

        {/* Tab: Ask AI */}
        {!showProfile && dashTab === 'ask' && (
          <div className="max-w-5xl mx-auto px-6 pb-10">
            {/* Smart Insights */}
            <SmartInsightsPanel sessionId={dataset.session_id} onExplore={handleQuery} />

            {/* Filters */}
            <FiltersBar profile={profile} filters={filters} dateRange={dateRange}
              datasetDateRange={dataset.date_range}
              onFiltersChange={setFilters} onDateRangeChange={setDateRange} />

            {/* Query input */}
            <div className="glass p-1.5 mb-5" style={{ borderRadius: 20 }}>
              <QueryInput onSubmit={handleQuery} loading={loading} disabled={!dataset} />
            </div>
            {error && <p className="text-sm font-semibold mb-4" style={{ color: 'var(--error)' }}>{error}</p>}

            {/* Quick Actions + Suggestions (when no result) */}
            {!result && !loading && (
              <>
                <QuickActions sessionId={dataset.session_id} />
                {suggestions.length > 0 && (
                  <div className="mb-6">
                    <p className="text-xs font-bold uppercase tracking-widest mb-3" style={{ color: 'var(--text-dim)' }}>
                      💬 Try asking
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {suggestions.map(q => (
                        <button key={q} onClick={() => handleQuery(q)} disabled={loading}
                          className="text-sm px-4 py-2.5 rounded-xl font-medium transition-all"
                          style={{ background: '#f3f0ff', color: '#42145F', border: '1px solid #e2d9f3', cursor: 'pointer' }}
                          onMouseEnter={e => { e.currentTarget.style.background = '#e8e0f8' }}
                          onMouseLeave={e => { e.currentTarget.style.background = '#f3f0ff' }}>
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {history.length > 0 && (
                  <div className="mb-6">
                    <p className="text-xs font-bold uppercase tracking-widest mb-3 flex items-center gap-1.5" style={{ color: 'var(--text-dim)' }}>
                      <Clock size={11} /> Recent
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {history.slice(0, 5).map((h, i) => (
                        <button key={i} onClick={() => handleQuery(h.question)}
                          className="text-xs px-3 py-2 rounded-xl font-medium flex items-center gap-2 transition-all"
                          style={{ background: 'white', border: '1px solid var(--border)', color: 'var(--text-muted)', cursor: 'pointer' }}>
                          <span className={`badge ${h.intent === 'change' ? 'badge-change' : h.intent === 'compare' ? 'badge-compare' : 'badge-general'}`}
                            style={{ padding: '1px 6px', fontSize: 8 }}>{h.intent}</span>
                          {h.question.slice(0, 45)}{h.question.length > 45 ? '…' : ''}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Loading */}
            <AnimatePresence>
              {loading && (
                <motion.div key="ld" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="glass p-6 flex items-center gap-5 mb-6" style={{ borderRadius: 20 }}>
                  <div className="spinner" />
                  <div>
                    <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Reasoning through your question…</p>
                    <p className="text-xs mt-1 font-medium" style={{ color: 'var(--text-dim)' }}>
                      Intent → Computation → Knowledge Graph → Narrative
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results */}
            <AnimatePresence mode="wait">
              {result && !loading && (
                <motion.div key={result.narrative ?? 'r'}
                  initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  <ResultTabs result={result} eli5={eli5} onFollowUp={handleQuery} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Tab: Data */}
        {!showProfile && dashTab === 'data' && (
          <div className="max-w-5xl mx-auto px-6 pb-10">
            <DataPreview sessionId={dataset.session_id} columns={dataset.columns} />
          </div>
        )}

        {/* Tab: Chart Builder */}
        {!showProfile && dashTab === 'build' && (
          <div className="max-w-5xl mx-auto px-6 pb-10">
            <ChartBuilder sessionId={dataset.session_id} profile={profile} />
          </div>
        )}
      </div>
    )
  }

  /* ═══════════════════════════════════════════════════════════════ */
  /*  LANDING PAGE                                                  */
  /* ═══════════════════════════════════════════════════════════════ */
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-deep)' }}>
      {/* Nav */}
      <nav className="sticky top-0 z-50 flex items-center justify-between px-8 h-16"
        style={{ background: 'rgba(255,255,255,0.96)', backdropFilter: 'blur(16px)', borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center hero-gradient">
              <Cpu size={17} className="text-white" />
            </div>
            <span className="font-extrabold text-lg gradient-text tracking-tight">DataWitness</span>
          </div>
          <div className="hidden md:flex items-center gap-6">
            {['Features', 'How It Works'].map(l => (
              <button key={l} onClick={() => (l === 'Features' ? featRef : howRef).current?.scrollIntoView({ behavior: 'smooth' })}
                className="text-sm font-semibold hover:text-purple-700 transition-colors"
                style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}>
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-ghost gap-2 text-sm" onClick={handleSample} disabled={uploading}>
            <Play size={14} /> {uploading ? 'Loading…' : 'Try Demo'}
          </button>
          <label className="btn-primary gap-2 text-sm cursor-pointer">
            <Upload size={14} /> Upload CSV
            <input type="file" accept=".csv" className="hidden" onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])} />
          </label>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero-gradient relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '40px 40px' }} />
        <div className="relative max-w-5xl mx-auto px-8 py-28 text-center">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <div className="inline-flex items-center gap-2 px-5 py-2 rounded-full mb-10 text-xs font-bold"
              style={{ background: 'rgba(255,255,255,0.15)', color: 'white', border: '1px solid rgba(255,255,255,0.2)' }}>
              <Sparkles size={14} /> NatWest Code for Purpose 2026
            </div>
            <h1 className="text-5xl sm:text-6xl md:text-7xl font-black text-white mb-6 leading-[1.05] tracking-tight">
              Talk to Your Data.<br/><span className="text-white/60">Understand the Why.</span>
            </h1>
            <p className="text-lg md:text-xl text-white/60 max-w-2xl mx-auto mb-12 leading-relaxed font-medium">
              Upload any dataset. Ask in plain English. Get verified, explainable answers.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button onClick={handleSample} disabled={uploading}
                className="inline-flex items-center justify-center gap-2.5 px-12 py-4 rounded-2xl font-bold text-base transition-all"
                style={{ background: 'white', color: '#42145F', boxShadow: '0 4px 24px rgba(0,0,0,0.12)' }}
                onMouseEnter={e => (e.currentTarget.style.transform = 'translateY(-3px)')}
                onMouseLeave={e => (e.currentTarget.style.transform = 'none')}>
                {uploading ? 'Loading…' : <><Play size={18} /> Try Sample Data</>}
              </button>
              <label className="inline-flex items-center justify-center gap-2.5 px-12 py-4 rounded-2xl font-bold text-base cursor-pointer transition-all"
                style={{ background: 'rgba(255,255,255,0.12)', color: 'white', border: '2px solid rgba(255,255,255,0.25)' }}>
                <Upload size={18} /> Upload CSV
                <input type="file" accept=".csv" className="hidden" onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])} />
              </label>
            </div>
            <button onClick={() => featRef.current?.scrollIntoView({ behavior: 'smooth' })}
              className="mt-12 animate-bounce text-white/30" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
              <ChevronDown size={28} />
            </button>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section ref={featRef} className="max-w-6xl mx-auto px-8 py-24">
        <div className="text-center mb-16">
          <p className="text-sm font-extrabold uppercase tracking-[0.2em] mb-3" style={{ color: '#7c3aed' }}>Capabilities</p>
          <h2 className="text-4xl md:text-5xl font-black gradient-text mb-5">Five Layers of Intelligence</h2>
          <p className="text-base max-w-xl mx-auto" style={{ color: 'var(--text-muted)' }}>
            Every answer goes through a multi-layer reasoning pipeline.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => (
            <motion.div key={f.label} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.1 }}
              className={`glass glass-hover p-8 ${f.cls}`}>
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5" style={{ background: `${f.color}12` }}>
                <f.icon size={28} style={{ color: f.color }} />
              </div>
              <h3 className="text-lg font-bold mb-2">{f.label}</h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section ref={howRef} style={{ background: 'white' }} className="py-24">
        <div className="max-w-5xl mx-auto px-8">
          <div className="text-center mb-16">
            <p className="text-sm font-extrabold uppercase tracking-[0.2em] mb-3" style={{ color: '#7c3aed' }}>Process</p>
            <h2 className="text-4xl md:text-5xl font-black gradient-text mb-5">How It Works</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {HOW_STEPS.map((s, i) => (
              <motion.div key={s.n} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.15 }}
                className="text-center">
                <div className="text-6xl font-black mb-5" style={{ color: '#f3f0ff' }}>{s.n}</div>
                <div className="w-16 h-16 rounded-2xl mx-auto mb-5 flex items-center justify-center"
                  style={{ background: 'linear-gradient(135deg, #f3f0ff, #e8e0f8)' }}>
                  <s.icon size={30} style={{ color: '#42145F' }} />
                </div>
                <h3 className="text-base font-bold mb-2">{s.title}</h3>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="hero-gradient py-20">
        <div className="max-w-3xl mx-auto px-8 text-center">
          <h2 className="text-3xl md:text-4xl font-black text-white mb-5">Ready to explore your data?</h2>
          <p className="text-base text-white/50 mb-10">Upload any CSV and start asking questions in seconds.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button onClick={handleSample} disabled={uploading}
              className="inline-flex items-center justify-center gap-2 px-10 py-4 rounded-2xl font-bold text-sm"
              style={{ background: 'white', color: '#42145F' }}>
              <Sparkles size={16} /> Try Sample Data
            </button>
            <label className="inline-flex items-center justify-center gap-2 px-10 py-4 rounded-2xl font-bold text-sm cursor-pointer"
              style={{ background: 'rgba(255,255,255,0.15)', color: 'white', border: '2px solid rgba(255,255,255,0.25)' }}>
              <Upload size={16} /> Upload CSV
              <input type="file" accept=".csv" className="hidden" onChange={e => e.target.files?.[0] && handleUpload(e.target.files[0])} />
            </label>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 text-center" style={{ background: '#1e1033' }}>
        <div className="flex items-center justify-center gap-2.5 mb-3">
          <Cpu size={16} className="text-white/40" />
          <span className="font-bold text-white/60 text-sm">DataWitness</span>
        </div>
        <p className="text-xs text-white/30">NatWest Code for Purpose 2026 · AI-Powered Data Intelligence</p>
      </footer>

      {error && (
        <div className="fixed bottom-6 right-6 z-50 glass p-4 rounded-2xl shadow-lg flex items-center gap-3">
          <p className="text-sm font-semibold" style={{ color: 'var(--error)' }}>{error}</p>
          <button onClick={() => setError(null)} style={{ color: 'var(--text-dim)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
