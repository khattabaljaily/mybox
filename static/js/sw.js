/* MyBox Service Worker — app-shell only, no document data caching. */
// v2: also purges caches from v1, which could hold copies of private files.
const CACHE = 'mybox-shell-v2';
const SHELL = [
    '/static/img/icon-192.png',
    '/static/img/icon-512.png',
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const { request } = e;
    const url = new URL(request.url);

    // Only same-origin GET requests.
    if (request.method !== 'GET' || url.origin !== self.location.origin) return;

    // Static assets (CSS/JS/img, including cache-busted ?v= URLs) —
    // stale-while-revalidate: serve the cached copy instantly if there is
    // one, but always refetch in the background so the NEXT load picks up
    // fresh assets after a change instead of being stuck on a stale copy.
    if (url.pathname.startsWith('/static/')) {
        e.respondWith(
            caches.open(CACHE).then(cache =>
                cache.match(request).then(cached => {
                    const fetchPromise = fetch(request).then(res => {
                        cache.put(request, res.clone());
                        return res;
                    }).catch(() => cached);
                    return cached || fetchPromise;
                })
            )
        );
        return;
    }

    // HTML pages — network first (documents change often), fall back to
    // cache so the app still opens (to whatever was last viewed) offline.
    // Only HTML is kept: uploaded files (PDF/images, sent with Cache-Control:
    // no-store) must never be copied into the browser's cache storage.
    e.respondWith(
        fetch(request)
            .then(res => {
                const type = res.headers.get('Content-Type') || '';
                const noStore = (res.headers.get('Cache-Control') || '').includes('no-store');
                if (res.ok && type.includes('text/html') && !noStore) {
                    caches.open(CACHE).then(cache => cache.put(request, res.clone()));
                }
                return res;
            })
            .catch(() => caches.match(request))
    );
});
