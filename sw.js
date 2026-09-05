const C='pokevalor-v3';
self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['./manifest.json','./icon.svg']))));
self.addEventListener('fetch',e=>{ if(e.request.url.includes('dados.json')) return; e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request))); });
