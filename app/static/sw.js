const STATIC_CACHE = 'votingapp-static-v13';
const RUNTIME_CACHE = 'votingapp-runtime-v13';
const PRECACHE_URLS = [
  '/',
  '/admin',
  '/static/style.css',
  '/static/main.js',
  '/static/manifest.json',
  '/static/icon.svg',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((k) => k.startsWith('votingapp-') && k !== STATIC_CACHE && k !== RUNTIME_CACHE)
        .map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// Broadcast helper
function broadcast(type, payload) {
  if (!self.clients || !self.clients.matchAll) return;
  self.clients.matchAll({ includeUncontrolled: true, type: 'window' }).then((clients) => {
    clients.forEach((client) => client.postMessage({ type, payload }));
  });
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // POST requests or non-GET: go straight to network
  if (req.method !== 'GET') {
    return; // let it pass-through
  }

  // Navigation requests: serve app shell (index or admin) when offline
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => {
        // offline fallback to cached shells
        if (url.pathname.startsWith('/admin')) {
          return caches.match('/admin');
        }
        return caches.match('/');
      })
    );
    return;
  }

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((resp) => {
          const respClone = resp.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(req, respClone)).catch(() => {});
          return resp;
        });
      })
    );
    return;
  }

  // API GET: network-first, fallback to cache if present
  if (url.pathname.startsWith('/poll') || url.pathname.startsWith('/admin')) {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const clone = resp.clone();
          caches.open(RUNTIME_CACHE).then((c) => c.put(req, clone)).catch(() => {});
          return resp;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Default: try cache, then network
  event.respondWith(caches.match(req).then((c) => c || fetch(req)));
});

// Background sync to flush queued votes (main.js will listen to this message)
self.addEventListener('sync', (event) => {
  if (event.tag === 'flushVotes') {
    event.waitUntil((async () => {
      broadcast('flushVotes');
    })());
  }
});