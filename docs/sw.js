// Offline support for the dashboard.
//
// The page is one self-contained HTML file plus a few pinned CDN files, so the
// cache is small:
//  - the page itself is network-first: fresh results when online, the last
//    copy when not;
//  - everything else (pinned Chart.js, the date adapter, the font, the icons)
//    is cache-first, since those URLs never change content.
//
// Bump VERSION if PRECACHE changes. Registered from template.html.
const VERSION = 'v1';
const CACHE = `parkrun-bates-${VERSION}`;
const SCOPE = new URL('./', self.location).pathname;   // '/parkrun-bates/' on GitHub Pages
const PAGE = SCOPE;
const CDN_HOSTS = ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'];
const PRECACHE = [
  PAGE,
  SCOPE + 'manifest.webmanifest',
  SCOPE + 'favicon.png', SCOPE + 'icon-180.png', SCOPE + 'icon-192.png', SCOPE + 'icon-512.png',
  SCOPE + 'parkrun-logo.svg',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',
  'https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js',
  'https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&display=swap',
];

self.addEventListener('install', event => {
  // allSettled: one unreachable icon shouldn't stop the rest being saved
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => Promise.allSettled(PRECACHE.map(url => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('parkrun-bates-') && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const isPage = req.mode === 'navigate' ||
    (url.origin === self.location.origin && (url.pathname === SCOPE || url.pathname === SCOPE + 'index.html'));

  if (isPage) {
    // every query (?celebrate, ?v=…) is the same page, so one cache entry serves all
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(PAGE, copy)); }
          return res;
        })
        .catch(() => caches.match(PAGE))
    );
    return;
  }

  if (url.origin !== self.location.origin && !CDN_HOSTS.includes(url.hostname)) return;
  event.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }))
  );
});
