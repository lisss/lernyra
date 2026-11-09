import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchTodoList, removeResourceFeedback } from '@/lib/api'
import { setDocumentMeta } from '@/lib/documentMeta'
import {
  type TodoItem,
  listTodoLocal,
  markTodoDoneLocal,
  mergeServerTodo,
  removeTodoLocal,
} from '@/lib/todoStore'

export function TodoPage() {
  const [items, setItems] = useState<TodoItem[]>(() => listTodoLocal())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function reload() {
    setLoading(true)
    setError(null)
    const local = listTodoLocal()
    setItems(local)
    try {
      const remote = await fetchTodoList()
      setItems(mergeServerTodo(remote))
    } catch (err) {
      if (local.length === 0) {
        setError(err instanceof Error ? err.message : 'Failed to load TODO list')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setDocumentMeta({
      title: 'Learning list | Lernyra',
      description: 'Your saved Lernyra study materials — books, courses, and interview prep.',
      path: '/learning-list',
      robots: 'noindex, nofollow',
    })
  }, [])

  useEffect(() => {
    void reload()
    const sync = () => setItems(listTodoLocal())
    window.addEventListener('lernyra-todo-changed', sync)
    return () => window.removeEventListener('lernyra-todo-changed', sync)
  }, [])

  async function onRemove(url: string) {
    removeTodoLocal(url)
    setItems(listTodoLocal())
    try {
      await removeResourceFeedback(url)
    } catch {}
  }

  function onToggleDone(url: string, done: boolean) {
    markTodoDoneLocal(url, done)
    setItems(listTodoLocal())
  }

  const open = items.filter((i) => !i.done)
  const done = items.filter((i) => i.done)

  return (
    <main className="relative z-10 mx-auto min-h-screen max-w-5xl px-5 pb-20 pt-10 sm:px-8">
      <header className="mb-10">
        <Link to="/" className="todo-link">
          ← Back to insights
        </Link>
        <h1 className="mt-12 text-3xl font-semibold tracking-tight text-[var(--title)]">
          Learning list
        </h1>
        <p className="mt-2 max-w-xl text-sm text-[var(--muted)]">
          Your saved study materials — work through these when you have a block of time.
        </p>
      </header>

      {loading && items.length === 0 && (
        <p className="text-sm text-[var(--muted)]">Loading…</p>
      )}
      {error && (
        <p className="mb-4 rounded-md bg-[#f8eee6] px-4 py-3 text-sm text-[var(--warn)]">
          {error}
        </p>
      )}

      {!loading && items.length === 0 && (
        <p className="panel px-6 py-8 text-sm text-[var(--muted)]">
          No saved materials yet. On insights results, click <strong>'Save'</strong> to add
          something here.
        </p>
      )}

      {open.length > 0 && (
        <ul className="space-y-4">
          {open.map((item) => (
            <TodoRow
              key={item.id || item.url}
              item={item}
              onRemove={() => void onRemove(item.url)}
              onToggleDone={() => onToggleDone(item.url, true)}
            />
          ))}
        </ul>
      )}

      {done.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Done ({done.length})
          </h2>
          <ul className="space-y-3 opacity-70">
            {done.map((item) => (
              <TodoRow
                key={item.id || item.url}
                item={item}
                onRemove={() => void onRemove(item.url)}
                onToggleDone={() => onToggleDone(item.url, false)}
              />
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}

function TodoRow({
  item,
  onRemove,
  onToggleDone,
}: {
  item: TodoItem
  onRemove: () => void
  onToggleDone: () => void
}) {
  return (
    <li className="panel px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--accent)]">
            {item.kind || 'resource'}
            {item.provider ? ` · ${item.provider}` : ''}
          </p>
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className={`mt-1 inline-block text-lg font-semibold text-[var(--link)] underline decoration-[var(--link-underline)] underline-offset-4 hover:decoration-[var(--accent)] ${
              item.done ? 'line-through opacity-70' : ''
            }`}
          >
            {item.title || item.url}
          </a>
          <p className="mt-1 break-all text-xs text-[var(--muted)]">{item.url}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onToggleDone} className="btn btn-done">
            {item.done ? 'Undo' : 'Mark done'}
          </button>
          <button type="button" onClick={onRemove} className="btn btn-remove">
            Remove
          </button>
        </div>
      </div>
    </li>
  )
}
