self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('votingapp-cache-v1').then((cache) => {
            return cache.addAll([
                '/',
                '/static/style.css',
                '/static/main.js',
                '/static/manifest.json',
                '/admin',
            ]);
        })
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});