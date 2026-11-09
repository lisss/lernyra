import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
} from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { setDocumentMeta } from '@/lib/documentMeta'
import {
  type InsightsResponse,
  type StoredCv,
  cvDownloadUrl,
  deleteCurrentCv,
  fetchCurrentCv,
  fetchInsights,
  filterSkillsForRole,
  parseCv,
  suggestRoles,
} from '@/lib/api'
import { InsightsPanel } from '@/components/InsightsPanel'
import { Logo, LernyraMark } from '@/components/Logo'
import { Typeahead } from '@/components/Typeahead'
import {
  clearCvFile,
  loadCvFile,
  loadCvMeta,
  saveCvFile,
  saveCvMeta,
} from '@/lib/cvStore'
import { todoOpenCount } from '@/lib/todoStore'

const STORAGE_KEY = 'lernyra.ui.v1'

type PersistedUi = {
  query?: string
  cvText?: string
  cvAllSkills?: string[]
  hasCvInput?: boolean
  insights?: InsightsResponse | null
}

function loadPersisted(): PersistedUi {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as PersistedUi
  } catch {
    return {}
  }
}

export function HomePage() {
  const saved = useRef(loadPersisted()).current
  const [searchParams] = useSearchParams()
  const urlRole = (searchParams.get('q') || searchParams.get('role') || '').trim()
  const [query, setQuery] = useState(urlRole || saved.query || '')
  const [cvText, setCvText] = useState(saved.cvText ?? '')
  const [cvAllSkills, setCvAllSkills] = useState<string[]>(saved.cvAllSkills ?? [])
  const [storedCv, setStoredCv] = useState<StoredCv | null>(() => loadCvMeta())
  const [cvParsing, setCvParsing] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [insights, setInsights] = useState<InsightsResponse | null>(saved.insights ?? null)
  const [hasCvInput, setHasCvInput] = useState(Boolean(saved.hasCvInput))
  const [todoCount, setTodoCount] = useState(() => todoOpenCount())
  const [resultKey, setResultKey] = useState(0)
  const [hydrated, setHydrated] = useState(false)
  const roleFilterSeq = useRef(0)
  const skipNextRoleFilter = useRef(Boolean(saved.cvText))
  const fileInputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const localCvUrlRef = useRef<string | null>(null)

  useEffect(() => {
    setDocumentMeta({
      title: 'Lernyra — role requirements, skills gaps & learning paths',
      description:
        'See what a job role typically needs, compare it to your CV or skills, and get a study plan with books, courses, and interview prep.',
      path: '/',
    })
  }, [])

  useEffect(() => {
    if (urlRole && urlRole !== query) {
      setQuery(urlRole)
    }
    // Only sync when the URL role changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlRole])

  const loadRoles = useCallback((q: string) => suggestRoles(q), [])

  function skillsFromTextarea(text: string): string[] {
    return Array.from(
      new Set(
        text
          .split(/[,;\n]/)
          .map((s) => s.trim())
          .filter(Boolean),
      ),
    )
  }

  useEffect(() => {
    setHydrated(true)
  }, [])

  useEffect(() => {
    const sync = () => setTodoCount(todoOpenCount())
    sync()
    window.addEventListener('lernyra-todo-changed', sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener('lernyra-todo-changed', sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  useEffect(() => {
    if (!hydrated) return
    const payload: PersistedUi = {
      query,
      cvText,
      cvAllSkills,
      hasCvInput,
      insights,
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
    } catch {}
  }, [query, cvText, cvAllSkills, hasCvInput, insights, hydrated])

  useEffect(() => {
    saveCvMeta(storedCv)
  }, [storedCv])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const localMeta = loadCvMeta()
      if (localMeta && !cancelled) {
        setStoredCv(localMeta)
        if ((localMeta.all_skills ?? []).length > 0) {
          setCvAllSkills((prev) => (prev.length > 0 ? prev : localMeta.all_skills ?? []))
        }
      }

      try {
        const remote = await fetchCurrentCv()
        if (cancelled) return
        if (remote) {
          setStoredCv(remote)
          saveCvMeta(remote)
          if ((remote.all_skills ?? []).length > 0) {
            setCvAllSkills((prev) => (prev.length > 0 ? prev : remote.all_skills ?? []))
          }
          return
        }
      } catch {}

      // Session cookie is gone — re-upload the local file so download still works.
      const file = await loadCvFile()
      if (cancelled || !file) return
      try {
        const role = query.trim()
        const { all_skills, cv } = await parseCv(file, role)
        if (cancelled) return
        if (cv) {
          setStoredCv(cv)
          saveCvMeta(cv)
        }
        if (all_skills.length > 0) {
          setCvAllSkills((prev) => (prev.length > 0 ? prev : all_skills))
        }
      } catch {}
    })()
    return () => {
      cancelled = true
    }
    // Only on mount — query used for optional re-filter at restore time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const role = query.trim()
    if (!role || cvAllSkills.length === 0) return
    // Don't overwrite restored textarea on first mount after refresh.
    if (skipNextRoleFilter.current) {
      skipNextRoleFilter.current = false
      return
    }

    const seq = ++roleFilterSeq.current
    let cancelled = false

    void (async () => {
      try {
        const skills = await filterSkillsForRole(role, cvAllSkills)
        if (cancelled || seq !== roleFilterSeq.current) return
        setCvText(skills.join(', '))
        if (skills.length === 0) {
          setError(
            'No skills from your CV match this role — add relevant ones manually.',
          )
        } else {
          setError(null)
        }
      } catch (err) {
        if (cancelled || seq !== roleFilterSeq.current) return
        setError(err instanceof Error ? err.message : 'Failed to update skills for role')
      }
    })()

    return () => {
      cancelled = true
    }
  }, [query, cvAllSkills])

  function cancelSearch() {
    abortRef.current?.abort()
    abortRef.current = null
    setLoading(false)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setLoading(true)
    setError(null)
    try {
      const skills = skillsFromTextarea(cvText)
      const data = await fetchInsights(
        { query, cv_skills: skills },
        { signal: controller.signal },
      )
      if (controller.signal.aborted) return
      setHasCvInput(skills.length > 0)
      setInsights(data)
      setResultKey((k) => k + 1)
    } catch (err) {
      if (controller.signal.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
        setError(null)
        return
      }
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setLoading(false)
    }
  }

  async function onCvUpload(file: File | null) {
    if (!file) return
    setError(null)
    setCvParsing(true)
    try {
      await saveCvFile(file)
      const role = query.trim()
      const { skills, all_skills, cv } = await parseCv(file, role)
      setCvAllSkills(all_skills)
      if (cv) {
        setStoredCv(cv)
        saveCvMeta(cv)
      } else {
        const meta: StoredCv = {
          id: `local-${Date.now()}`,
          filename: file.name,
          content_type: file.type || 'application/octet-stream',
          uploaded_at: new Date().toISOString(),
          download_url: '/api/cv/download',
          all_skills,
        }
        setStoredCv(meta)
        saveCvMeta(meta)
      }

      if (!role) {
        setCvText('')
        setError(null)
        return
      }

      if (skills.length === 0) {
        setCvText('')
        setError(
          'No skills in that CV match this role — add relevant ones manually below.',
        )
        return
      }
      setCvText(skills.join(', '))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'CV parse failed')
    } finally {
      setCvParsing(false)
    }
  }

  async function onRemoveCv() {
    try {
      await deleteCurrentCv()
    } catch {}
    await clearCvFile()
    if (localCvUrlRef.current) {
      URL.revokeObjectURL(localCvUrlRef.current)
      localCvUrlRef.current = null
    }
    setStoredCv(null)
    setCvAllSkills([])
    setCvText('')
    setHasCvInput(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function onDownloadCv(e: MouseEvent<HTMLAnchorElement>) {
    try {
      const remote = await fetchCurrentCv()
      if (remote) return
    } catch {}
    e.preventDefault()
    const file = await loadCvFile()
    if (!file) return
    if (localCvUrlRef.current) URL.revokeObjectURL(localCvUrlRef.current)
    const url = URL.createObjectURL(file)
    localCvUrlRef.current = url
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
  }

  return (
    <main className="relative z-10 mx-auto min-h-screen max-w-5xl px-5 pb-20 pt-10 sm:px-8">
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4">
        <Logo asHeading />
        <Link to="/learning-list" className="todo-link">
          <LernyraMark className="todo-link-mark" />
          <span className="todo-link-label">Learning list</span>
          {todoCount > 0 ? (
            <span className="todo-link-count" aria-label={`${todoCount} open items`}>
              {todoCount}
            </span>
          ) : null}
        </Link>
      </header>

      <section className="panel px-6 py-9 sm:px-9 sm:py-11">
        <p className="whitespace-nowrap text-[clamp(0.95rem,2.9vw,1.75rem)] font-semibold tracking-tight text-[var(--brand)]">
          See what a role needs — and what to learn next
        </p>
        <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-[var(--muted)] sm:text-base">
          Pick a position and your skills. We look up books, courses, and
          interview material online for that mix.
        </p>

        <form onSubmit={onSubmit} className="relative mt-8 space-y-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <Typeahead
              label="Role"
              value={query}
              onChange={setQuery}
              fetchSuggestions={loadRoles}
              placeholder="e.g. Software Engineer"
              required
            />
            <div className="flex items-end gap-2">
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="btn btn-primary w-full sm:w-auto"
              >
                {loading ? (
                  <>
                    <span className="spinner" aria-hidden />
                    Searching…
                  </>
                ) : (
                  'Plan your learning'
                )}
              </button>
              {loading && (
                <button type="button" onClick={cancelSearch} className="btn btn-ghost">
                  Cancel
                </button>
              )}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-sm text-[var(--muted)]">
                Your skills (comma-separated)
              </span>
              <textarea
                value={cvText}
                onChange={(e) => setCvText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    e.currentTarget.form?.requestSubmit()
                  }
                }}
                rows={3}
                placeholder={
                  cvParsing ? 'Reading skills from CV…' : 'Python, Docker, SQL…'
                }
                disabled={cvParsing || loading}
                className="w-full resize-y rounded-md border border-[var(--line)] bg-white px-3.5 py-2.5 text-[15px] text-[var(--ink)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)] disabled:opacity-60"
              />
              {cvAllSkills.length > 0 && (
                <p className="mt-1.5 text-xs text-[var(--muted)]">
                  From your CV — updates when you change role.
                </p>
              )}
            </label>
            <div className="block">
              <span className="mb-1.5 block text-sm text-[var(--muted)]">
                CV (PDF / TXT / DOC)
              </span>
              <div className="flex min-h-[5.5rem] flex-col justify-center gap-2 rounded-md border border-dashed border-[var(--line)] bg-[var(--surface-soft)] px-4 py-3">
                {storedCv ? (
                  <>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <a
                        href={cvDownloadUrl()}
                        onClick={(e) => void onDownloadCv(e)}
                        className="font-medium text-[var(--link)] underline decoration-[var(--link-underline)] underline-offset-4 hover:decoration-[var(--accent)]"
                      >
                        {storedCv.filename}
                      </a>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={cvParsing || loading}
                        onClick={() => fileInputRef.current?.click()}
                        className="btn btn-primary-sm"
                      >
                        Replace
                      </button>
                      <button
                        type="button"
                        disabled={cvParsing || loading}
                        onClick={() => void onRemoveCv()}
                        className="btn btn-ghost-sm"
                      >
                        Remove
                      </button>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-[var(--muted)]">
                    {cvParsing ? 'Uploading…' : 'No CV uploaded yet.'}
                  </p>
                )}
                {!storedCv && (
                  <button
                    type="button"
                    disabled={cvParsing || loading}
                    onClick={() => fileInputRef.current?.click()}
                    className="btn btn-primary-sm w-fit"
                  >
                    Upload CV
                  </button>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,application/pdf,text/plain"
                  disabled={cvParsing || loading}
                  className="sr-only"
                  onChange={(e) => {
                    void onCvUpload(e.target.files?.[0] ?? null)
                    e.target.value = ''
                  }}
                />
              </div>
              <p className="mt-2 text-xs text-[var(--muted)]">
                {storedCv && !query.trim()
                  ? 'CV saved — select a role to fill matching skills.'
                  : query.trim() && !storedCv
                    ? `Role selected — upload a CV to fill skills for “${query.trim()}”.`
                    : query.trim() && storedCv
                      ? `Skills below are filtered for “${query.trim()}”.`
                      : 'Upload a CV and select a role (either order) to auto-fill matching skills.'}
              </p>
              {cvParsing && (
                <p className="mt-1 text-sm text-[var(--muted)]">Extracting skills…</p>
              )}
            </div>
          </div>
        </form>

        {loading && (
          <div className="mt-4 flex items-center gap-3 rounded-md border border-[var(--accent-soft)] bg-[var(--accent-soft)]/40 px-4 py-3 text-sm text-[var(--accent)]">
            <span className="spinner spinner--accent" aria-hidden />
            Finding trusted books, courses, and a study plan…
          </div>
        )}

        {error && (
          <p className="mt-4 rounded-md bg-[#f8eee6] px-4 py-3 text-sm text-[var(--warn)]">
            {error}
          </p>
        )}
      </section>

      {insights && !loading && (
        <div key={resultKey} className="animate-fade mt-12">
          <InsightsPanel data={insights} showCvGaps={hasCvInput} />
        </div>
      )}

      <footer className="mt-16 border-t border-[var(--line)] pt-8 text-sm text-[var(--muted)]">
        <p className="font-medium text-[var(--title-soft)]">Popular role guides</p>
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
          {[
            ['software-engineer', 'Software Engineer'],
            ['python-developer', 'Python Developer'],
            ['frontend-engineer', 'Frontend Engineer'],
            ['data-engineer', 'Data Engineer'],
            ['devops-engineer', 'DevOps Engineer'],
            ['ml-engineer', 'ML Engineer'],
          ].map(([slug, label]) => (
            <li key={slug}>
              <a
                href={`/roles/${slug}`}
                className="text-[var(--link)] underline decoration-[var(--link-underline)] underline-offset-2 hover:text-[var(--accent)]"
              >
                {label}
              </a>
            </li>
          ))}
          <li>
            <a
              href="/roles"
              className="text-[var(--link)] underline decoration-[var(--link-underline)] underline-offset-2 hover:text-[var(--accent)]"
            >
              All role guides
            </a>
          </li>
        </ul>
        <p className="mt-4 max-w-2xl leading-relaxed">
          Lernyra is a free career learning planner: compare job role requirements to your
          skills or CV, then get books, courses, certifications, and interview prep in one
          roadmap.
        </p>
      </footer>
    </main>
  )
}
