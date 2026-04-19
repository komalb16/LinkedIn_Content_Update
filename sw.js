// LinkedIn Agent — Service Worker
// Strategy:
//   dashboard.html  → network-first (always fresh, cached copy only for offline)
//   manifest.json   → network-first (same reason)
//   GitHub API      → always network, never cached
//   Fonts / CDN     → cache-first (static assets, safe to cache long-term)

// Bump this version any time dashboard.html changes — forces old cache eviction.
const CACHE = 'li-agent-v4';
const CDN_ASSETS = [
  'https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=DM+Mono:wght@400;500&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js',
];

// ── Install: pre-cache only static CDN assets (not dashboard.html) ────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(CDN_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: evict ALL old caches (li-agent-v1, v2, v3...) ──────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const url = e.request.url;

  // ① GitHub API — NEVER cache, always network
  if (url.includes('api.github.com')) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .catch(() => new Response(JSON.stringify({ error: 'offline' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        }))
    );
    return;
  }

  // ② dashboard.html + manifest.json — network-first, cached copy only as offline fallback
  if (url.includes('dashboard.html') || url.includes('manifest.json')) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .then(resp => {
          // Cache a fresh copy for offline use
          if (resp && resp.status === 200) {
            const clone = resp.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return resp;
        })
        .catch(() => caches.match(e.request))  // offline fallback
    );
    return;
  }

  // ③ Google Fonts DNS / gstatic — network-first (font data changes rarely)
  if (url.includes('fonts.gstatic') || url.includes('fonts.googleapis')) {
    e.respondWith(
      fetch(e.request)
        .then(resp => {
          if (resp && resp.status === 200 && resp.type !== 'opaque') {
            const clone = resp.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return resp;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // ④ CDN assets (qrcode.js etc.) — cache-first (truly static, safe to cache)
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(resp => {
        if (resp && resp.status === 200 && resp.type !== 'opaque') {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      });
    })
  );
});

// ── Background sync placeholder (future: queue failed posts) ─────────────────
self.addEventListener('sync', e => {
  if (e.tag === 'post-queue') {
    console.log('[SW] Background sync: post-queue');
  }
});
