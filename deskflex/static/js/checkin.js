/* Check-in: validación por folio o por cámara (html5-qrcode). */
(() => {
  const form = document.getElementById('form-codigo');
  if (!form) return;
  const out = document.getElementById('scan-result');
  const csrf = form.querySelector('[name=csrf_token]').value;
  const url = form.action;
  let busy = false, scanner = null, last = '', lastAt = 0;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const ICON = {
    ok: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="m8 12.5 3 3 5-6"/></svg>',
    no: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="m9 9 6 6M15 9l-6 6"/></svg>',
  };

  function addRow(r) {
    const tb = document.querySelector('#tabla-accesos tbody'); if (!tb) return;
    const f = document.querySelector('[name=fecha]');
    const hoy = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Mexico_City' });
    if (f && f.value !== hoy) return;                       // el listado muestra otro día
    const [y, m, d] = hoy.split('-');
    const tr = document.createElement('tr');
    tr.innerHTML = `<td data-label="Usuario"><b>${esc(r.cliente || 'Sin identificar')}</b></td><td data-label="Espacio">${esc(r.espacio || '—')}</td>
      <td data-label="Fecha">${d}/${m}/${y}</td><td data-label="Hora">${esc(r.hora)}</td><td data-label="Acción">Entrada</td>
      <td data-label="Resultado"><span class="badge badge--${r.ok ? 'autorizado' : 'denegado'}">${r.ok ? 'Autorizado' : 'Denegado'}</span>${r.ok ? '' : `<br><small class="muted">${esc(r.motivo)}</small>`}</td>`;
    tb.prepend(tr); document.getElementById('sin-accesos').hidden = true;
  }

  function show(r) {
    out.hidden = false; out.className = 'scan-result ' + (r.ok ? 'ok' : 'no');
    out.innerHTML = `${r.ok ? ICON.ok : ICON.no}<div><b>${r.ok ? 'Acceso autorizado' : 'Acceso denegado'}</b>
      <p>${r.ok ? `${esc(r.cliente)} · ${esc(r.espacio)}<br>${esc(r.horario)} · entrada ${esc(r.hora)}` : `${esc(r.motivo)}${r.cliente ? `<br>${esc(r.cliente)} · ${esc(r.espacio)}` : ''}`}</p></div>`;
    addRow(r);
  }

  async function validar(codigo) {
    if (busy) return; busy = true;
    try {
      const body = new URLSearchParams({ csrf_token: csrf, codigo });
      const res = await fetch(url, { method: 'POST', body, headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' });
      if (!res.ok) throw new Error(res.status);
      show(await res.json());
    } catch (e) {
      show({ ok: false, motivo: 'No se pudo validar. Revisa la conexión e inténtalo de nuevo.' });
    } finally { busy = false; }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const inp = document.getElementById('codigo');
    validar(inp.value.trim()).then(() => { inp.value = ''; inp.focus(); });
  });

  // Cámara
  const btn = document.getElementById('btn-cam');
  btn.addEventListener('click', async () => {
    if (!window.Html5Qrcode) { show({ ok: false, motivo: 'El lector de cámara no se pudo cargar. Usa el folio.' }); return; }
    try {
      scanner = scanner || new Html5Qrcode('reader');
      await scanner.start({ facingMode: 'environment' }, { fps: 10, qrbox: { width: 220, height: 220 } }, (txt) => {
        const now = Date.now();
        if (txt === last && now - lastAt < 4000) return;      // evita doble lectura del mismo QR
        last = txt; lastAt = now; validar(txt);
      });
      document.getElementById('scanner-idle').hidden = true;
    } catch (e) {
      show({ ok: false, motivo: 'No pudimos abrir la cámara. Revisa el permiso del navegador o usa el folio.' });
    }
  });
})();
