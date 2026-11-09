import type { StoredCv } from '@/lib/api'

const CV_META_KEY = 'lernyra.cv.meta.v1'
const CV_DB = 'lernyra-cv'
const CV_STORE = 'files'
const CV_FILE_KEY = 'current'

export type StoredCvMeta = StoredCv

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(CV_DB, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(CV_STORE)) {
        db.createObjectStore(CV_STORE)
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB open failed'))
  })
}

export function loadCvMeta(): StoredCvMeta | null {
  try {
    const raw = localStorage.getItem(CV_META_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredCvMeta
    return parsed?.filename ? parsed : null
  } catch {
    return null
  }
}

export function saveCvMeta(cv: StoredCvMeta | null): void {
  try {
    if (!cv) localStorage.removeItem(CV_META_KEY)
    else localStorage.setItem(CV_META_KEY, JSON.stringify(cv))
  } catch {}
}

export async function saveCvFile(file: File): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(CV_STORE, 'readwrite')
    tx.objectStore(CV_STORE).put(
      {
        name: file.name,
        type: file.type,
        lastModified: file.lastModified,
        blob: file,
      },
      CV_FILE_KEY,
    )
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Failed to save CV file'))
  })
  db.close()
}

export async function loadCvFile(): Promise<File | null> {
  try {
    const db = await openDb()
    const record = await new Promise<{
      name: string
      type: string
      lastModified: number
      blob: Blob
    } | null>((resolve, reject) => {
      const tx = db.transaction(CV_STORE, 'readonly')
      const req = tx.objectStore(CV_STORE).get(CV_FILE_KEY)
      req.onsuccess = () => resolve((req.result as typeof record) ?? null)
      req.onerror = () => reject(req.error ?? new Error('Failed to load CV file'))
    })
    db.close()
    if (!record?.blob) return null
    return new File([record.blob], record.name || 'cv.pdf', {
      type: record.type || 'application/octet-stream',
      lastModified: record.lastModified || Date.now(),
    })
  } catch {
    return null
  }
}

export async function clearCvFile(): Promise<void> {
  saveCvMeta(null)
  try {
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(CV_STORE, 'readwrite')
      tx.objectStore(CV_STORE).delete(CV_FILE_KEY)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error ?? new Error('Failed to clear CV file'))
    })
    db.close()
  } catch {}
}
