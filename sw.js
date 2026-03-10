// LinkedIn Agent — Service Worker
// Caches the dashboard shell so it loads instantly on any device,
// even with a flaky connection. GitHub API calls always go to network.

const CACHE    = 'li-agent-v2';
const SHELL    = [
  './dashboard.html',
  './manifest.json',
  'https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=DM+Mono:wght@400;500&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js',
];

// ── Install: pre-cache shell ──────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

// ── Activate: evict old caches ────────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: network-first for API, cache-first for shell ───────────────────────
self.addEventListener('fetch', e => {
  const url = e.request.url;

  // Always go to network for GitHub API calls
  if (url.includes('api.github.com') || url.includes('fonts.gstatic')) {
    e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 })));
    return;
  }

  // Cache-first for shell assets
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(resp => {
        if (!resp || resp.status !== 200 || resp.type === 'opaque') return resp;
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return resp;
      }).catch(() => caches.match('./dashboard.html'));
    })
  );
});

// ── Background sync placeholder (future: queue failed posts) ─────────────────
self.addEventListener('sync', e => {
  if (e.tag === 'post-queue') {
    console.log('[SW] Background sync: post-queue');
  }
});
