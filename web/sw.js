// Service worker for the Vercel deployment of the HMS QR mobile app.
//
// Two differences from apps/static/sw.js, both forced by the split root:
//   1. the manifest lives at /manifest.json here, not /static/manifest.json
//   2. each asset is cached on its own, so one missing file cannot abort the
//      whole install the way cache.addAll does
const CACHE_NAME = 'hms-qr-vercel-v1';
const STATIC_ASSETS = [
  '/manifest.json',
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
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k))
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
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json') {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
