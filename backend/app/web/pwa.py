"""Funciona com internet fraca: PWA (instalar na tela inicial) + última orientação guardada no celular.

Service worker com escopo na raiz:
- páginas de orientação (/, /clima, /planejamento, /o-que-plantar): rede primeiro; sem rede, a última
  versão guardada (inclusive a última /clima aberta, mesmo sem parâmetros);
- arquivos de CDN (Tailwind, fontes, Leaflet): cache e atualiza em segundo plano;
- NÃO guarda perfil, login, cadastro nem respostas de POST (dados da conta não ficam em cache).
"""
from __future__ import annotations

from flask import Response, url_for

from app.web import bp

CACHE_VERSION = "plantfacil-v1"

SW_JS = r"""
const CACHE = '__CACHE__';
const PAGES = ['/', '/consulta', '/clima', '/planejamento', '/o-que-plantar'];
const CDN = ['cdn.tailwindcss.com', 'fonts.googleapis.com', 'fonts.gstatic.com', 'unpkg.com'];

self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === location.origin && req.mode === 'navigate' && PAGES.includes(url.pathname)) {
    e.respondWith((async () => {
      const cache = await caches.open(CACHE);
      try {
        const resp = await fetch(req);
        if (resp.ok) {
          cache.put(req, resp.clone());
          cache.put(url.pathname, resp.clone()); // "última versão" da página, sem parâmetros
        }
        return resp;
      } catch (err) {
        return (await cache.match(req)) || (await cache.match(url.pathname)) || (await cache.match('/clima')) ||
          new Response('<meta charset="utf-8"><body style="font-family:sans-serif;padding:24px">' +
            '<h2>Sem internet</h2><p>Abra o Plant+Facil uma vez com internet para guardar a orientação no celular.</p>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      }
    })());
    return;
  }
  if (CDN.includes(url.hostname)) {
    e.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const hit = await cache.match(req);
      const net = fetch(req).then((r) => { if (r.ok || r.type === 'opaque') cache.put(req, r.clone()); return r; })
        .catch(() => hit);
      return hit || net;
    })());
  }
});
""".replace("__CACHE__", CACHE_VERSION)

OFFLINE_JS = r"""
(() => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
  const show = () => {
    if (navigator.onLine || document.getElementById('aviso-offline')) return;
    const d = document.createElement('div');
    d.id = 'aviso-offline';
    d.setAttribute('role', 'status');
    d.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:#ffdad6;color:#93000a;' +
      'padding:8px 16px;font:600 14px sans-serif;text-align:center';
    d.textContent = 'Sem internet: mostrando a última orientação guardada neste celular. Confira de novo quando tiver sinal.';
    document.body.prepend(d);
  };
  window.addEventListener('offline', show);
  window.addEventListener('online', () => document.getElementById('aviso-offline')?.remove());
  show();
})();
"""

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#016d30"/>
<path d="M50 15 C30 35 25 55 25 70 C25 82 36 90 50 90 C64 90 75 82 75 70 C75 55 70 35 50 15 Z" fill="#92f5a4"/>
<path d="M50 30 L50 78 M50 48 Q62 46 64 42 M50 60 Q38 58 36 54" fill="none" stroke="#016d30" stroke-linecap="round" stroke-width="6"/></svg>"""


@bp.get("/sw.js")
def service_worker():
    resp = Response(SW_JS, mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.get("/offline.js")
def offline_js():
    return Response(OFFLINE_JS, mimetype="application/javascript", headers={"Cache-Control": "public, max-age=3600"})


@bp.get("/icon.svg")
def icon():
    return Response(ICON_SVG, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@bp.get("/manifest.webmanifest")
def manifest():
    data = {
        "name": "Plant+Facil — quando plantar com dados oficiais",
        "short_name": "Plant+Facil",
        "lang": "pt-BR",
        "start_url": url_for("web.inicio"),
        "display": "standalone",
        "background_color": "#f9f9ff",
        "theme_color": "#016d30",
        "icons": [{"src": url_for("web.icon"), "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
    }
    from flask import jsonify

    resp = jsonify(data)
    resp.mimetype = "application/manifest+json"
    return resp
