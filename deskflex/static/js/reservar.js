/* Reservar: calendario → horario → mapa en vivo (escritorios, sillas individuales y salas completas). */
(() => {
  const form = document.getElementById('booking-form');
  if (!form) return;
  const D = form.dataset;
  const CERRADOS = JSON.parse(D.cerrados || '[]');
  const MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
  const $ = (id) => document.getElementById(id);
  const pad = (n) => String(n).padStart(2, '0');
  const iso = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;
  const fmtH = (h) => `${(h % 12) || 12}:00 ${h < 12 ? 'am' : 'pm'}`;
  const parse = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };

  // esp: número del espacio; asiento: silla (solo salas); todo: sala completa
  const st = { fecha: D.inicial, modo: 'hora', a: null, b: null, esp: null, asiento: null, todo: false,
               horas: [], estados: null, asientos: {}, ventana: null, vista: parse(D.inicial), firma: null };
  const plano = form.querySelector('.plano');
  const sps = [...plano.querySelectorAll('.sp')];
  const spBy = (n) => sps.find((g) => Number(g.dataset.num) === n);
  let ctl = null;

  /* ---- Calendario ---- */
  function drawCal() {
    const y = st.vista.getFullYear(), m = st.vista.getMonth();
    $('cal-title').textContent = `${MESES[m]} ${y}`;
    const grid = $('cal-grid'); grid.innerHTML = '';
    grid.classList.remove('swap'); void grid.offsetWidth; grid.classList.add('swap');
    ['L','M','M','J','V','S','D'].forEach((l) => {
      const e = document.createElement('div'); e.className = 'dow'; e.textContent = l; e.setAttribute('aria-hidden', 'true'); grid.appendChild(e);
    });
    const first = (new Date(y, m, 1).getDay() + 6) % 7;
    for (let i = 0; i < first; i++) grid.appendChild(document.createElement('span'));
    const n = new Date(y, m + 1, 0).getDate();
    for (let d = 1; d <= n; d++) {
      const f = iso(y, m, d), dow = (new Date(y, m, d).getDay() + 6) % 7;
      const b = document.createElement('button'); b.type = 'button'; b.className = 'cal-day'; b.textContent = d;
      b.disabled = f < D.hoy || f > D.max || CERRADOS.includes(dow);
      if (f === D.hoy) b.classList.add('is-today');
      b.setAttribute('aria-pressed', f === st.fecha ? 'true' : 'false');
      b.setAttribute('aria-label', parse(f).toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long' }) + (b.disabled ? ' (no disponible)' : ''));
      b.addEventListener('click', () => {
        st.fecha = f; st.a = st.b = null; clearSel();
        grid.querySelectorAll('.cal-day').forEach((x) => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true');
        refresh();
      });
      grid.appendChild(b);
    }
    $('cal-prev').disabled = (y === parse(D.hoy).getFullYear() && m <= parse(D.hoy).getMonth());
    const mx = parse(D.max); $('cal-next').disabled = (y > mx.getFullYear()) || (y === mx.getFullYear() && m >= mx.getMonth());
  }
  $('cal-prev').addEventListener('click', () => { st.vista.setMonth(st.vista.getMonth() - 1, 1); drawCal(); });
  $('cal-next').addEventListener('click', () => { st.vista.setMonth(st.vista.getMonth() + 1, 1); drawCal(); });

  /* ---- Horas ---- */
  const okH = (h) => (st.horas.find((x) => x.h === h) || {}).estado === 'ok';
  function pickHour(h) {
    if (st.a === null) { st.a = st.b = h; }
    else if (st.a === st.b && h === st.a) { st.a = st.b = null; }
    else if (st.a === st.b) {
      const lo = Math.min(st.a, h), hi = Math.max(st.a, h);
      let libre = true; for (let x = lo; x <= hi; x++) if (!okH(x)) libre = false;
      if (libre) { st.a = lo; st.b = hi; } else { st.a = st.b = h; }
    } else { st.a = st.b = h; }
    refresh();
  }
  function drawHours() {
    const box = $('hours'); box.innerHTML = '';
    st.horas.forEach((h) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chip'; b.textContent = h.texto;
      b.dataset.estado = h.estado; b.disabled = h.estado !== 'ok';
      if (h.estado === 'mia') b.title = 'Ya tienes una reserva en esta hora';
      if (h.estado === 'pasada') b.title = 'Esta hora ya pasó';
      b.setAttribute('aria-pressed', st.a !== null && h.h >= st.a && h.h <= st.b ? 'true' : 'false');
      b.addEventListener('click', () => pickHour(h.h));
      box.appendChild(b);
    });
    const note = $('range-note').querySelector('span');
    if (st.a === null) note.textContent = 'Elige la hora de entrada.';
    else { const n = st.b - st.a + 1; note.textContent = `${fmtH(st.a)} – ${fmtH(st.b + 1)} · ${n} ${n === 1 ? 'hora' : 'horas'}`; }
  }

  /* ---- Mapa ---- */
  function msg(text, tipo) {
    const m = $('map-msg'); m.hidden = !text; m.querySelector('span').textContent = text || '';
    m.className = 'alert mapmsg alert--' + (tipo || 'info');
  }
  const esSala = (g) => !!g.querySelector('.seat');
  function clearSel() { st.esp = null; st.asiento = null; st.todo = false; }
  function drawMap() {
    sps.forEach((g) => {
      const n = Number(g.dataset.num);
      const e = st.estados ? (st.estados[n] || 'nd') : 'nd';
      g.dataset.estado = e;
      const selSala = st.esp === n && st.todo;
      g.dataset.sel = (st.esp === n && (e === 'libre') && (!esSala(g) || st.todo)) ? 'true' : 'false';
      const txt = { libre: 'disponible', parcial: 'con lugares apartados', ocupado: 'apartado', nd: 'elige fecha y horario' }[e];
      if (!esSala(g)) {
        g.setAttribute('aria-pressed', g.dataset.sel);
        g.setAttribute('aria-label', `${g.dataset.nombre}, ${txt}`);
        g.setAttribute('aria-disabled', e === 'libre' ? 'false' : 'true');
        g.setAttribute('tabindex', e === 'libre' ? '0' : '-1');
      }
      g.querySelectorAll('.seat').forEach((s) => {
        const k = Number(s.dataset.asiento);
        const se = st.estados ? ((st.asientos[n] || {})[k] || 'libre') : 'nd';
        s.dataset.estado = se === 'nd' ? 'ocupado' : se;
        s.dataset.sel = (se === 'libre' && st.esp === n && (selSala || st.asiento === k)) ? 'true' : 'false';
        s.setAttribute('aria-pressed', s.dataset.sel);
        s.setAttribute('aria-label', `${g.dataset.nombre}, asiento ${k}, ${se === 'libre' ? 'disponible' : 'apartado'}`);
        s.setAttribute('aria-disabled', se === 'libre' ? 'false' : 'true');
        s.setAttribute('tabindex', se === 'libre' ? '0' : '-1');
      });
    });
    drawZones();
  }
  function drawZones() {
    const cnt = { salas: 0, fijo: 0, hot: 0 }, tot = { salas: 0, fijo: 0, hot: 0 };
    sps.forEach((g) => {
      const n = Number(g.dataset.num);
      if (esSala(g)) { g.querySelectorAll('.seat').forEach((s) => { tot.salas++; if (st.estados && s.dataset.estado === 'libre') cnt.salas++; }); }
      else { const z = n <= 9 ? 'fijo' : 'hot'; tot[z]++; if (st.estados && g.dataset.estado === 'libre') cnt[z]++; }
    });
    document.querySelectorAll('.zone-chip[data-zone]').forEach((c) => {
      const z = c.dataset.zone, b = c.querySelector('b'), v = st.estados ? `${cnt[z]}/${tot[z]}` : '–';
      if (b.textContent !== v) { b.textContent = v; c.classList.remove('bump'); void c.offsetWidth; c.classList.add('bump'); }
    });
  }
  function pickSpace(g, seat) {
    const n = Number(g.dataset.num);
    if (seat) {
      const k = Number(seat.dataset.asiento);
      if (seat.dataset.estado !== 'libre') { msg(`El asiento ${k} de ${g.dataset.nombre} ya está apartado. Elige otra silla.`, 'error'); return; }
      msg(''); const igual = st.esp === n && !st.todo && st.asiento === k;
      if (igual) clearSel(); else { st.esp = n; st.asiento = k; st.todo = false; }
    } else if (esSala(g)) {
      if (g.dataset.estado === 'parcial') { msg('Esa sala ya tiene sillas apartadas en ese horario. Toca una silla libre.', 'info'); return; }
      if (g.dataset.estado !== 'libre') { msg(`${g.dataset.nombre} está completamente apartada en ese horario.`, 'error'); return; }
      msg(''); if (st.esp === n && st.todo) clearSel(); else { st.esp = n; st.todo = true; st.asiento = null; }
    } else {
      if (g.dataset.estado !== 'libre') { msg(`${g.dataset.nombre} ya está apartado en ese horario. Prueba con otro espacio.`, 'error'); return; }
      msg(''); if (st.esp === n) clearSel(); else { st.esp = n; st.asiento = null; st.todo = false; }
    }
    drawMap(); drawSummary();
  }
  sps.forEach((g) => {
    g.addEventListener('click', (e) => { const s = e.target.closest('.seat'); pickSpace(g, s); });
    g.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return; e.preventDefault();
      pickSpace(g, e.target.closest('.seat'));
    });
  });

  /* ---- Tooltip ---- */
  const tip = $('map-tip');
  plano.addEventListener('mousemove', (e) => {
    const g = e.target.closest('.sp'); if (!g) { tip.classList.remove('on'); return; }
    const s = e.target.closest('.seat'), e0 = s ? s.dataset.estado : g.dataset.estado;
    const est = { libre: 'Disponible', parcial: 'Con sillas apartadas', ocupado: 'Apartado', nd: 'Elige fecha y hora' }[e0] || '';
    tip.innerHTML = `${g.dataset.nombre}${s ? ' · asiento ' + s.dataset.asiento : ''}<small>${est}${!s && esSala(g) && e0 === 'libre' ? ' · toca para sala completa' : ''}</small>`;
    tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 220) + 'px'; tip.style.top = (e.clientY + 16) + 'px'; tip.classList.add('on');
  });
  plano.addEventListener('mouseleave', () => tip.classList.remove('on'));

  /* ---- Resumen, pasos y envío ---- */
  function nombreSel() {
    const g = spBy(st.esp); if (!g) return '';
    return g.dataset.nombre + (esSala(g) ? (st.todo ? ' · sala completa' : ` · asiento ${st.asiento}`) : '');
  }
  function drawSummary() {
    let lista = false;
    if (st.estados && st.esp) {
      const g = spBy(st.esp);
      lista = esSala(g) ? (st.todo ? st.estados[st.esp] === 'libre' : ((st.asientos[st.esp] || {})[st.asiento] === 'libre')) : st.estados[st.esp] === 'libre';
    }
    const e = $('sum-espacio'), nuevo = lista ? nombreSel() : 'Toca uno en el mapa';
    if (e.textContent !== nuevo) { e.textContent = nuevo; e.classList.remove('flash'); void e.offsetWidth; e.classList.add('flash'); }
    e.classList.toggle('is-empty', !lista);
    $('sum-fecha').textContent = parse(st.fecha).toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
    const h = $('sum-horario'); h.textContent = st.ventana ? st.ventana.texto : 'Elige una hora'; h.classList.toggle('is-empty', !st.ventana);
    $('btn-confirm').disabled = !(lista && st.ventana);
    $('f-espacio').value = st.esp || ''; $('f-asiento').value = (!st.todo && st.asiento) ? st.asiento : '';
    $('f-fecha').value = st.fecha; $('f-modo').value = st.modo;
    $('f-inicio').value = st.ventana ? st.ventana.inicio : ''; $('f-fin').value = st.ventana ? st.ventana.fin : '';
    const paso = !st.ventana ? 1 : (!lista ? 2 : 3);
    document.querySelectorAll('#stepper li').forEach((li) => {
      const n = Number(li.dataset.s); li.classList.toggle('done', n < paso || (n === 3 && lista && false)); li.classList.toggle('now', n === paso);
    });
  }

  /* ---- Datos del servidor (con actualización en vivo) ---- */
  async function refresh(silent) {
    if (ctl) ctl.abort(); ctl = new AbortController();
    const p = new URLSearchParams({ fecha: st.fecha, modo: st.modo });
    if (st.modo === 'hora' && st.a !== null) { p.set('inicio', st.a); p.set('fin', st.b + 1); }
    if (!silent) $('map-frame').classList.add('is-loading');
    try {
      const r = await fetch(`${D.url}?${p}`, { signal: ctl.signal, headers: { Accept: 'application/json' }, credentials: 'same-origin' });
      if (r.status === 401 || r.redirected) { location.reload(); return; }
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      st.horas = data.horas || [];
      if (st.modo === 'hora' && st.a === null && !silent) {
        const h = st.horas.find((x) => x.estado === 'ok');
        if (h) { st.a = st.b = h.h; return refresh(); }
      }
      const firma = JSON.stringify([data.estados, data.asientos]);
      const cambio = st.firma !== null && st.firma !== firma && silent;
      st.firma = firma;
      st.estados = data.estados; st.asientos = data.asientos || {}; st.ventana = data.estados ? data.ventana : null;
      let perdido = false;
      if (st.esp) {
        const g = spBy(st.esp);
        const libre = st.estados && (esSala(g) ? (st.todo ? st.estados[st.esp] === 'libre' : (st.asientos[st.esp] || {})[st.asiento] === 'libre') : st.estados[st.esp] === 'libre');
        if (!libre) { perdido = true; const nom = nombreSel(); clearSel(); if (st.estados) msg(`${nom} acaba de ser apartado por otra persona. Elige otro lugar.`, 'error'); }
      }
      if (!perdido) { if (!data.estados) msg(data.mensaje || '', 'info'); else if (cambio) { msg('El mapa se actualizó: alguien acaba de apartar un lugar.', 'info'); setTimeout(() => { if ($('map-msg').textContent.startsWith('El mapa se')) msg(''); }, 4000); } else if (!silent) msg(''); }
      drawHours(); drawMap(); drawSummary();
      $('map-frame').classList.remove('is-loading');
    } catch (err) {
      if (err.name === 'AbortError') return;
      $('map-frame').classList.remove('is-loading');
      if (!silent) msg('No pudimos actualizar la disponibilidad. Revisa tu conexión e inténtalo de nuevo.', 'error');
    }
  }
  setInterval(() => { if (!document.hidden && st.estados) refresh(true); }, 4000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(true); });

  form.querySelectorAll('input[name="modo_ui"]').forEach((r) => r.addEventListener('change', () => {
    st.modo = r.value; st.a = st.b = null; clearSel();
    $('hours-wrap').hidden = st.modo === 'dia'; $('day-note').hidden = st.modo !== 'dia';
    refresh();
  }));
  form.addEventListener('submit', (e) => { if ($('btn-confirm').disabled) e.preventDefault(); });

  drawCal(); drawMap(); drawSummary(); refresh();
})();
