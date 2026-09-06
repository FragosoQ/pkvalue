const C='pokevalor-v4';
self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['./manifest.json','./icon.svg']))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k))))));
self.addEventListener('fetch',e=>{ if(e.request.url.includes('dados.json')) return; e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request))); });
