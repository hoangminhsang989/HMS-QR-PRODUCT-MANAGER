// Service worker for the LAN deployment of the HMS QR mobile app.
//
// Same shape as web/sw.js, which is the Vercel deployment's copy. The only
// difference is where the manifest lives: /static/manifest.json here, because
// the LAN server mounts its assets under /static.
//
// Each asset is cached on its own rather than with cache.addAll, so one missing
// file cannot abort the whole install. The Vercel copy lost offline support
// exactly that way once - a single 404 took the worker down and nothing
// noticed, because a service worker that fails to install just does not.
const CACHE_NAME = 'hms-qr-v2';
const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/favicon.png',
  '/static/jsqr.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        STATIC_ASSETS.map((asset) =>
          cache.add(asset).catch(() => {
            // A missing asset must not take the whole worker down.
          })
        )
      )
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  // Serve static assets from cache first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        return cached || fetch(event.request);
      })
    );
  }
});
