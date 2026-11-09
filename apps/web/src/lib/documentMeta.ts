const SITE = 'https://getbeacon.duckdns.org'

export function setDocumentMeta({
  title,
  description,
  path = '/',
  robots = 'index,follow,max-image-preview:large,max-snippet:-1',
}: {
  title: string
  description?: string
  path?: string
  robots?: string
}) {
  document.title = title

  const desc =
    description ??
    'Lernyra shows what a job role typically needs, compares it to your skills, and builds a study plan.'
  let meta = document.querySelector('meta[name="description"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.setAttribute('name', 'description')
    document.head.appendChild(meta)
  }
  meta.setAttribute('content', desc)

  let robotsMeta = document.querySelector('meta[name="robots"]')
  if (!robotsMeta) {
    robotsMeta = document.createElement('meta')
    robotsMeta.setAttribute('name', 'robots')
    document.head.appendChild(robotsMeta)
  }
  robotsMeta.setAttribute('content', robots)

  const canonicalHref = `${SITE}${path.startsWith('/') ? path : `/${path}`}`
  let link = document.querySelector('link[rel="canonical"]')
  if (!link) {
    link = document.createElement('link')
    link.setAttribute('rel', 'canonical')
    document.head.appendChild(link)
  }
  link.setAttribute('href', canonicalHref)

  const ogTitle = document.querySelector('meta[property="og:title"]')
  ogTitle?.setAttribute('content', title)
  const ogDesc = document.querySelector('meta[property="og:description"]')
  ogDesc?.setAttribute('content', desc)
  const ogUrl = document.querySelector('meta[property="og:url"]')
  ogUrl?.setAttribute('content', canonicalHref)
}
