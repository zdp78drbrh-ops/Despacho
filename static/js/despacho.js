/* Comportamiento de la interfaz (equivalente a openModal/formModal/confirmModal/toast del prototipo).
   Los datos y reglas viven en el servidor; aquí solo se abren modales y se envían formularios. */
(function () {
  const $ = s => document.querySelector(s);
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';

  function toast(msg) { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 2200); }
  window.toast = toast;

  function closeModal() { $('#modal').innerHTML = ''; }
  function openModal(html) {
    $('#modal').innerHTML = `<div class="ov" id="ov"><div class="md" role="dialog" aria-modal="true">${html}</div></div>`;
    $('#ov').addEventListener('click', e => { if (e.target.id === 'ov') closeModal(); });
    const first = $('#modal').querySelector('input:not([type=hidden]),select,textarea'); if (first) first.focus();
    initModal();
  }
  function confirmModal(msg, onOk, label) {
    const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    openModal(`<h2>Confirmar</h2><p style="font-size:13.5px">${esc(msg)}</p><div class="macts"><button class="btn" data-cerrar>Cancelar</button><button class="btn danger" id="cyes">${esc(label || 'Eliminar')}</button></div>`);
    $('#cyes').onclick = () => { closeModal(); onOk(); };
  }
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  async function manejarRespuesta(r) {
    const dest = r.headers.get('X-Despacho-Redirect');
    if (dest) { if (dest === location.pathname + location.search) location.reload(); else location.href = dest; return; }
    if (r.status === 403) { toast('No tienes permiso para esta acción'); return; }
    const html = await r.text();
    if ($('#modal .md')) { $('#modal .md').innerHTML = html; initModal(); } else openModal(html);
  }
  async function pedirModal(url) {
    const r = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
    await manejarRespuesta(r);
  }
  async function postear(url, datos) {
    const fd = datos || new FormData();
    if (!fd.has('csrfmiddlewaretoken')) fd.append('csrfmiddlewaretoken', csrf());
    const r = await fetch(url, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'fetch' } });
    await manejarRespuesta(r);
  }

  // Selección de tipo de recurso → etapas y órgano (recAfter del prototipo)
  function initModal() {
    const f = $('#modal form.mf'); if (!f) return;
    const data = $('#recursos-json');
    if (data && f.tipo && f.etapa) {
      const R = JSON.parse(data.textContent);
      const sync = () => {
        const c = R[f.tipo.value] || { etapas: [] }; const cur = f.etapa.value;
        f.etapa.innerHTML = ''; c.etapas.forEach(t => { const o = document.createElement('option'); o.value = o.textContent = t; if (t === cur) o.selected = true; f.etapa.appendChild(o); });
        if (!c.etapas.includes(cur)) f.etapa.selectedIndex = 0;
        if (!f.organo.dataset.touched) f.organo.value = c.organo || '';
      };
      f.tipo.addEventListener('change', sync);
      f.organo.addEventListener('input', () => { f.organo.dataset.touched = '1'; });
    }
  }

  document.addEventListener('click', async e => {
    const t = e.target.closest('[data-modal],[data-post],[data-cerrar],[data-copiar],[data-calc-plazo],[data-href]');
    if (!t) return;
    if (t.hasAttribute('data-cerrar')) { e.preventDefault(); closeModal(); return; }
    if (t.hasAttribute('data-modal')) { e.preventDefault(); pedirModal(t.dataset.modal); return; }
    if (t.hasAttribute('data-href')) { if (e.target.closest('a,button,.lnk')) return; location.href = t.dataset.href; return; }
    if (t.hasAttribute('data-post')) {
      e.preventDefault();
      const run = () => postear(t.dataset.post);
      if (t.dataset.confirm) { closeModal(); confirmModal(t.dataset.confirm, run, t.dataset.confirmLabel); } else run();
      return;
    }
    if (t.hasAttribute('data-copiar')) {
      const ta = $(t.dataset.copiar);
      try { await navigator.clipboard.writeText(ta.value); } catch (err) { ta.select(); document.execCommand('copy'); }
      toast('Copiado'); return;
    }
    if (t.hasAttribute('data-calc-plazo')) {
      const f = t.closest('form'); const n = prompt('¿Cuántos días hábiles? (se cuentan desde hoy, sin sábados ni domingos; ajusta manualmente si hay días inhábiles del tribunal)');
      if (!n || Number(n) <= 0) return;
      const r = await fetch(`/plazo/calcular/?dias=${encodeURIComponent(n)}`); const j = await r.json();
      if (j.fecha) f.plazo.value = j.fecha; else toast(j.error || 'No se pudo calcular');
    }
  });

  // Formularios dentro de modales → fetch; formularios con data-confirm → confirmación previa
  document.addEventListener('submit', e => {
    const f = e.target;
    if (f.matches('#modal form.mf')) { e.preventDefault(); postear(f.action, new FormData(f)); return; }
    if (f.dataset.confirm && !f._ok) {
      e.preventDefault();
      confirmModal(f.dataset.confirm, () => { f._ok = true; f.submit(); }, f.dataset.confirmLabel || 'Aceptar');
    }
  });

  $('#tbMenu') && ($('#tbMenu').onclick = () => $('#side').classList.toggle('open'));
  try { JSON.parse($('#mensajes').textContent).forEach((m, i) => setTimeout(() => toast(m), i * 2300)); } catch (e) { }

  // Tema (Configuración → Apariencia)
  window.setTema = v => { try { localStorage.setItem('despacho_tema', v); } catch (e) { } if (v) document.documentElement.setAttribute('data-theme', v); else document.documentElement.removeAttribute('data-theme'); };
  const ts = $('#temaSel'); if (ts) { try { ts.value = localStorage.getItem('despacho_tema') || ''; } catch (e) { } }
})();
