import type { FeedbackItem } from '@/lib/api'

const TODO_KEY = 'lernyra.todo.v1'

export type TodoItem = FeedbackItem & {
  done?: boolean
}

function readAll(): TodoItem[] {
  try {
    const raw = localStorage.getItem(TODO_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as TodoItem[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeAll(items: TodoItem[]) {
  try {
    localStorage.setItem(TODO_KEY, JSON.stringify(items))
    window.dispatchEvent(new Event('lernyra-todo-changed'))
  } catch {}
}

export function listTodoLocal(): TodoItem[] {
  return readAll().filter((i) => i.verdict === 'useful')
}

export function todoOpenCount(): number {
  return listTodoLocal().filter((i) => !i.done).length
}

export type TodoProgress = 'empty' | 'none' | 'partial' | 'all'

export function todoProgress(): TodoProgress {
  const items = listTodoLocal()
  if (items.length === 0) return 'empty'
  const done = items.filter((i) => i.done).length
  if (done === 0) return 'none'
  if (done === items.length) return 'all'
  return 'partial'
}

export function upsertTodoLocal(item: TodoItem): TodoItem {
  const url = (item.url || '').replace(/\/$/, '')
  const items = readAll()
  const idx = items.findIndex((i) => (i.url || '').replace(/\/$/, '') === url)
  const next: TodoItem = {
    ...item,
    url,
    verdict: item.verdict || 'useful',
    done: item.done ?? (idx >= 0 ? items[idx].done : false),
  }
  if (idx >= 0) items[idx] = { ...items[idx], ...next }
  else items.unshift(next)
  writeAll(items)
  return next
}

export function markTodoDoneLocal(url: string, done: boolean): void {
  const key = url.replace(/\/$/, '')
  const items = readAll().map((i) =>
    (i.url || '').replace(/\/$/, '') === key ? { ...i, done } : i,
  )
  writeAll(items)
}

export function removeTodoLocal(url: string): void {
  const key = url.replace(/\/$/, '')
  writeAll(readAll().filter((i) => (i.url || '').replace(/\/$/, '') !== key))
}

/** Merge server useful items into local store (local done flags win). */
export function mergeServerTodo(serverItems: FeedbackItem[]): TodoItem[] {
  const byUrl = new Map<string, TodoItem>()
  for (const local of listTodoLocal()) {
    byUrl.set((local.url || '').replace(/\/$/, ''), local)
  }
  for (const remote of serverItems) {
    const key = (remote.url || '').replace(/\/$/, '')
    const existing = byUrl.get(key)
    byUrl.set(key, {
      ...remote,
      url: key,
      verdict: 'useful',
      done: existing?.done ?? false,
    })
  }
  const merged = Array.from(byUrl.values()).sort((a, b) =>
    (b.created_at || '').localeCompare(a.created_at || ''),
  )
  writeAll(merged)
  return merged
}
