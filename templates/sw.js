const CACHE_NAME = 'mtronix-offline-v3';
const STATIC_ASSETS = [
    '/static/css/app.css?v=3.1',
    '/static/js/app.js?v=3.1',
    '/static/js/chart.umd.min.js?v=4.4.3',
    '/static/js/html5-qrcode.min.js?v=3.0.0',
    '/static/img/logo.png',
    '/static/manifest.json',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    // Cache-first for static assets
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(req).then((cached) => {
                if (cached) return cached;
                return fetch(req).then((resp) => {
                    if (resp && resp.ok) {
                        const copy = resp.clone();
                        caches.open(CACHE_NAME).then((c) => c.put(req, copy));
                    }
                    return resp;
                });
            })
        );
        return;
    }

    // Network-first for HTML pages, falling back to cached copy if server is temporarily unreachable
    if (req.headers.get('accept') && req.headers.get('accept').includes('text/html')) {
        event.respondWith(
            fetch(req)
                .then((resp) => {
                    if (resp && resp.ok && (url.pathname === '/sales/new/' || url.pathname === '/')) {
                        const copy = resp.clone();
                        caches.open(CACHE_NAME).then((c) => c.put(req, copy));
                    }
                    return resp;
                })
                .catch(() => caches.match(req).then((cached) => cached || new Response(
                    '<html><body style="font-family:sans-serif;padding:40px;text-align:center;"><h2>Mtronix Offline</h2><p>Server is currently unreachable. Cached POS Terminal is available at <a href="/sales/new/">/sales/new/</a>.</p></body></html>',
                    { status: 503, headers: { 'Content-Type': 'text/html' } }
                )))
        );
    }
});
