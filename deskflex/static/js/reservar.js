/* Flujo de reserva: calendario → horario → mapa con disponibilidad en vivo. */
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

  const st = { fecha: D.inicial, modo: 'hora', a: null, b: null, esp: null, horas: [], estados: null, ventana: null, vista: parse(D.inicial) };
  const plano = form.querySelector('.plano');
  const sps = [...plano.querySelectorAll('.sp')];
  let ctl = null;

  /* ---- Calendario ---- */
  function drawCal() {
    const y = st.vista.getFullYear(), m = st.vista.getMonth();
    $('cal-title').textContent = `${MESES[m]} ${y}`;
    const grid = $('cal-grid'); grid.innerHTML = '';
    ['L','M','M','J','V','S','D'].forEach((l, i) => {
      const e = document.createElement('div'); e.className = 'dow'; e.textContent = l;
      e.setAttribute('aria-hidden', 'true'); grid.appendChild(e);
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
      b.addEventListener('click', () => { st.fecha = f; st.a = st.b = null; refresh(); drawCal(); });
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
    else {
      const n = st.b - st.a + 1;
      note.textContent = `${fmtH(st.a)} – ${fmtH(st.b + 1)} · ${n} ${n === 1 ? 'hora' : 'horas'}`;
    }
  }

  /* ---- Mapa ---- */
  function msg(text) { const m = $('map-msg'); m.hidden = !text; m.querySelector('span').textContent = text || ''; }
  function drawMap() {
    sps.forEach((g) => {
      const n = Number(g.dataset.num);
      const e = st.estados ? (st.estados[n] || 'nd') : 'nd';
      g.dataset.estado = e;
      g.dataset.sel = (st.esp === n && e === 'libre') ? 'true' : 'false';
      g.setAttribute('aria-pressed', g.dataset.sel);
      const txt = { libre: 'disponible', ocupado: 'reservado en ese horario', nd: 'elige fecha y horario' }[e];
      g.setAttribute('aria-label', `${g.dataset.nombre}, ${txt}`);
      g.setAttribute('aria-disabled', e === 'libre' ? 'false' : 'true');
      g.setAttribute('tabindex', e === 'libre' ? '0' : '-1');
      const t = g.querySelector('title'); if (t) t.textContent = `${g.dataset.nombre} · ${txt}`;
    });
  }
  function pickSpace(g) {
    if (g.dataset.estado !== 'libre') {
      if (g.dataset.estado === 'ocupado') msg(`${g.dataset.nombre} está reservado en ese horario. Prueba con otro espacio.`);
      return;
    }
    msg(''); const n = Number(g.dataset.num);
    st.esp = st.esp === n ? null : n; drawMap(); drawSummary();
  }
  sps.forEach((g) => {
    g.addEventListener('click', () => pickSpace(g));
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pickSpace(g); } });
  });

  /* ---- Resumen y envío ---- */
  function drawSummary() {
    const lista = st.estados && st.esp && st.estados[st.esp] === 'libre';
    const sp = sps.find((g) => Number(g.dataset.num) === st.esp);
    const e = $('sum-espacio'); e.textContent = lista && sp ? sp.dataset.nombre : 'Toca uno en el mapa'; e.classList.toggle('is-empty', !lista);
    $('sum-fecha').textContent = parse(st.fecha).toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
    const h = $('sum-horario'); h.textContent = st.ventana ? st.ventana.texto : 'Elige una hora'; h.classList.toggle('is-empty', !st.ventana);
    $('btn-confirm').disabled = !(lista && st.ventana);
    $('f-espacio').value = st.esp || ''; $('f-fecha').value = st.fecha; $('f-modo').value = st.modo;
    $('f-inicio').value = st.ventana ? st.ventana.inicio : ''; $('f-fin').value = st.ventana ? st.ventana.fin : '';
  }

  /* ---- Datos del servidor ---- */
  async function refresh() {
    if (ctl) ctl.abort(); ctl = new AbortController();
    const p = new URLSearchParams({ fecha: st.fecha, modo: st.modo });
    if (st.modo === 'hora' && st.a !== null) { p.set('inicio', st.a); p.set('fin', st.b + 1); }
    $('map-frame').classList.add('is-loading');
    try {
      const r = await fetch(`${D.url}?${p}`, { signal: ctl.signal, headers: { Accept: 'application/json' }, credentials: 'same-origin' });
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      st.horas = data.horas || [];
      if (st.modo === 'hora' && st.a === null) {            // preselecciona la primera hora libre
        const h = st.horas.find((x) => x.estado === 'ok');
        if (h) { st.a = st.b = h.h; return refresh(); }
      }
      st.estados = data.estados; st.ventana = data.estados ? data.ventana : null;
      if (st.esp && (!st.estados || st.estados[st.esp] !== 'libre')) {
        const sp = sps.find((g) => Number(g.dataset.num) === st.esp);
        if (st.estados) msg(`${sp ? sp.dataset.nombre : 'El espacio'} ya no está disponible en ese horario. Elige otro.`);
        st.esp = null;
      } else if (!data.estados) { msg(data.mensaje || ''); } else { msg(''); }
      drawHours(); drawMap(); drawSummary();
      $('map-frame').classList.remove('is-loading');
    } catch (err) {
      if (err.name === 'AbortError') return;
      $('map-frame').classList.remove('is-loading');
      msg('No pudimos actualizar la disponibilidad. Revisa tu conexión e inténtalo de nuevo.');
    }
  }

  form.querySelectorAll('input[name="modo_ui"]').forEach((r) => r.addEventListener('change', () => {
    st.modo = r.value; st.a = st.b = null; st.esp = null;
    $('hours-wrap').hidden = st.modo === 'dia'; $('day-note').hidden = st.modo !== 'dia';
    refresh();
  }));
  form.addEventListener('submit', (e) => { if ($('btn-confirm').disabled) e.preventDefault(); });

  drawCal(); drawMap(); drawSummary(); refresh();
})();
