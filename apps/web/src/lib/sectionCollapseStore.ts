/** Bump when default open/closed rules change so old prefs don't stick. */
const KEY = 'lernyra.sections.v4'

type CollapseMap = Record<string, boolean>

function read(): CollapseMap {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as CollapseMap
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function write(map: CollapseMap) {
  try {
    localStorage.setItem(KEY, JSON.stringify(map))
  } catch {}
}

export function isSectionOpen(id: string, defaultOpen = false): boolean {
  const map = read()
  if (Object.prototype.hasOwnProperty.call(map, id)) {
    return map[id] === true
  }
  return defaultOpen
}

export function setSectionOpen(id: string, open: boolean): void {
  const map = read()
  map[id] = open
  write(map)
}
