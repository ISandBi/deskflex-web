/* Check-in: folio manual + lector de QR con la cámara (getUserMedia + BarcodeDetector o jsQR). */
(() => {
  const form = document.getElementById('form-codigo');
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  const out = $('scan-result'), csrf = form.querySelector('[name=csrf_token]').value, url = form.action;
  let busy = false, last = '', lastAt = 0;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ICON = {
    ok: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="m8 12.5 3 3 5-6"/></svg>',
    no: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="m9 9 6 6M15 9l-6 6"/></svg>',
  };

  function addRow(r) {
    const tb = document.querySelector('#tabla-accesos tbody'); const f = document.querySelector('[name=fecha]');
    if (!tb || !r.cliente && !r.motivo) return;
    const hoy = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Mexico_City' });
    if (f && f.value !== hoy) return;
    const [y, m, d] = hoy.split('-'), tr = document.createElement('tr');
    tr.innerHTML = `<td data-label="Usuario"><b>${esc(r.cliente || 'Sin identificar')}</b></td><td data-label="Espacio">${esc(r.espacio || '—')}</td>
      <td data-label="Fecha">${d}/${m}/${y}</td><td data-label="Hora">${esc(r.hora)}</td><td data-label="Acción">Entrada</td>
      <td data-label="Resultado"><span class="badge badge--${r.ok ? 'autorizado' : 'denegado'}">${r.ok ? 'Autorizado' : 'Denegado'}</span>${r.motivo ? `<br><small class="muted">${esc(r.motivo)}</small>` : ''}</td>`;
    tb.prepend(tr); $('sin-accesos').hidden = true;
  }

  function show(r) {
    out.hidden = false; out.className = 'scan-result ' + (r.ok ? 'ok' : 'no');
    out.innerHTML = `${r.ok ? ICON.ok : ICON.no}<div><b>${r.ok ? 'Acceso autorizado' : 'Acceso denegado'}</b>
      <p>${r.ok ? `${esc(r.cliente)} · ${esc(r.espacio)}<br>${esc(r.horario)} · entrada ${esc(r.hora)}${r.motivo ? `<br><small>${esc(r.motivo)}</small>` : ''}`
        : `${esc(r.motivo)}${r.cliente ? `<br>${esc(r.cliente)} · ${esc(r.espacio)} · ${esc(r.horario)}` : ''}`}</p>
      ${r.forzable ? '<button type="button" class="btn btn--outline btn--sm force">Permitir entrada de todos modos</button>' : ''}</div>`;
    const fb = out.querySelector('.force');
    if (fb) fb.addEventListener('click', () => { fb.classList.add('is-busy'); validar(r.codigo, true); });
    out.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    addRow(r);
  }

  async function validar(codigo, forzar) {
    if (busy) return; busy = true;
    try {
      const body = new URLSearchParams({ csrf_token: csrf, codigo, forzar: forzar ? '1' : '0' });
      const res = await fetch(url, { method: 'POST', body, headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' });
      if (!res.ok) throw new Error(res.status);
      const r = await res.json(); show(r);
      const sc = $('scanner'); sc.classList.add('hit'); setTimeout(() => sc.classList.remove('hit'), 900);
      if (navigator.vibrate) navigator.vibrate(r.ok ? 80 : [60, 40, 60]);
    } catch (e) { show({ ok: false, motivo: 'No se pudo validar. Revisa la conexión e inténtalo de nuevo.' }); }
    finally { busy = false; }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault(); const inp = $('codigo');
    validar(inp.value.trim()).then(() => { inp.value = ''; inp.focus(); });
  });

  /* ---------- Cámara ---------- */
  const video = $('cam'), btn = $('btn-cam'), sel = $('cam-select'), status = $('cam-status'), box = $('scanner');
  let stream = null, raf = 0, decoder = null, canvas = null, ctx2d = null, lastTick = 0;

  function say(text, tipo) {
    status.hidden = !text; status.textContent = text || ''; status.className = 'cam-status' + (tipo ? ' ' + tipo : '');
  }
  const SOURCES = ['/static/vendor/jsQR.js', 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js',
                   'https://unpkg.com/jsqr@1.4.0/dist/jsQR.js', 'https://cdnjs.cloudflare.com/ajax/libs/jsQR/1.4.0/jsQR.min.js'];
  function loadScript(src) {
    return new Promise((ok, no) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); no(); }; document.head.appendChild(s); });
  }
  async function getDecoder() {
    if (decoder) return decoder;
    if ('BarcodeDetector' in window) {
      try {
        const fm = await BarcodeDetector.getSupportedFormats();
        if (fm.includes('qr_code')) {
          const det = new BarcodeDetector({ formats: ['qr_code'] });
          return (decoder = async () => { const r = await det.detect(video); return r.length ? r[0].rawValue : null; });
        }
      } catch (e) { /* sigue con jsQR */ }
    }
    if (!window.jsQR) { for (const s of SOURCES) { try { await loadScript(s); if (window.jsQR) break; } catch (e) { /* siguiente */ } } }
    if (!window.jsQR) return null;
    canvas = document.createElement('canvas'); ctx2d = canvas.getContext('2d', { willReadFrequently: true });
    return (decoder = async () => {
      const w = video.videoWidth, h = video.videoHeight; if (!w) return null;
      const k = Math.min(1, 720 / w); canvas.width = Math.round(w * k); canvas.height = Math.round(h * k);
      ctx2d.drawImage(video, 0, 0, canvas.width, canvas.height);
      const img = ctx2d.getImageData(0, 0, canvas.width, canvas.height);
      const r = window.jsQR(img.data, img.width, img.height, { inversionAttempts: 'attemptBoth' });
      return r ? r.data : null;
    });
  }

  function loop(t) {
    raf = requestAnimationFrame(loop);
    if (!decoder || t - lastTick < 120 || video.readyState < 2 || busy) return;
    lastTick = t;
    decoder().then((txt) => {
      if (!txt) return; const now = Date.now();
      if (txt === last && now - lastAt < 4000) return;
      last = txt; lastAt = now; validar(txt);
    }).catch(() => {});
  }

  function errMsg(e) {
    if (!window.isSecureContext || !navigator.mediaDevices) return 'El navegador solo permite la cámara en https:// o en http://localhost / 127.0.0.1. Abre el sistema con esa dirección.';
    switch (e && e.name) {
      case 'NotAllowedError': case 'SecurityError': return 'El permiso de cámara está bloqueado. Haz clic en el candado junto a la dirección, permite la cámara y vuelve a intentar.';
      case 'NotFoundError': case 'OverconstrainedError': return 'No se detectó ninguna cámara en este equipo.';
      case 'NotReadableError': case 'AbortError': return 'La cámara está en uso por otra aplicación (Zoom, Teams, otra pestaña). Ciérrala e inténtalo de nuevo.';
      default: return 'No se pudo abrir la cámara (' + (e && e.name || 'error') + '). Usa el folio mientras tanto.';
    }
  }

  async function listCams() {
    try {
      const devs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
      if (devs.length > 1) {
        const cur = stream && stream.getVideoTracks()[0].getSettings().deviceId;
        sel.innerHTML = devs.map((d, i) => `<option value="${esc(d.deviceId)}"${d.deviceId === cur ? ' selected' : ''}>${esc(d.label || 'Cámara ' + (i + 1))}</option>`).join('');
        sel.hidden = false;
      } else sel.hidden = true;
    } catch (e) { sel.hidden = true; }
  }

  async function startCam(deviceId) {
    stopCam(true); btn.classList.add('is-busy'); say('Abriendo la cámara… acepta el permiso si el navegador lo pide.');
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw { name: 'SecurityError' };
      const tries = deviceId ? [{ video: { deviceId: { exact: deviceId } } }]
        : [{ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } } }, { video: true }];
      let lastErr;
      for (const c of tries) { try { stream = await navigator.mediaDevices.getUserMedia(c); break; } catch (e) { lastErr = e; if (e.name === 'NotAllowedError') break; } }
      if (!stream) throw lastErr;
      video.srcObject = stream; video.hidden = false; await video.play();
      box.classList.add('live'); btn.querySelector('span').textContent = 'Detener cámara'; btn.classList.remove('btn--accent'); btn.classList.add('btn--outline');
      listCams(); say('Cámara activa. Mantén el código QR dentro del recuadro.', 'ok');
      const d = await getDecoder();
      if (!d) say('La cámara funciona, pero no se pudo cargar el decodificador de QR (revisa tu internet). Mientras tanto, captura el folio.', 'err');
      cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
    } catch (e) { stopCam(true); say(errMsg(e), 'err'); }
    finally { btn.classList.remove('is-busy'); }
  }
  function stopCam(silent) {
    cancelAnimationFrame(raf);
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    video.srcObject = null; video.hidden = true; box.classList.remove('live');
    btn.querySelector('span').textContent = 'Activar cámara'; btn.classList.add('btn--accent'); btn.classList.remove('btn--outline');
    if (!silent) say('');
  }
  btn.addEventListener('click', () => (stream ? stopCam() : startCam()));
  sel.addEventListener('change', () => startCam(sel.value));
  window.addEventListener('pagehide', () => stopCam(true));
})();
