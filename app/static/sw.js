self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('votingapp-cache-v7').then((cache) => {
            return cache.addAll([
                '/',
                '/static/style.css',
                '/static/main.js',
                '/static/manifest.json',
                '/static/icon.svg',
                '/admin',
            ]);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys => Promise.all(
            keys.filter(k => k !== 'votingapp-cache-v7').map(k => caches.delete(k))
        )).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});