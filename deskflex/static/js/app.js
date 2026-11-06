/* Comportamientos compartidos: mostrar/ocultar contraseña, confirmaciones, menú y diálogos. */
(() => {
  // Contraseña visible
  document.querySelectorAll('[data-toggle-pass]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.togglePass);
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', show);
      btn.setAttribute('aria-label', show ? 'Ocultar contraseña' : 'Mostrar contraseña');
      btn.querySelector('.i-on').hidden = show; btn.querySelector('.i-off').hidden = !show;
    });
  });

  // Menú de usuario: cerrar al hacer clic fuera o con Escape
  const menu = document.querySelector('.userbtn');
  if (menu) {
    document.addEventListener('click', (e) => { if (!menu.contains(e.target)) menu.open = false; });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') menu.open = false; });
  }

  // Confirmación de acciones destructivas
  const dlg = document.getElementById('confirm-dialog');
  document.querySelectorAll('form[data-confirm]').forEach((f) => {
    f.addEventListener('submit', (e) => {
      if (f.dataset.confirmed) return;
      e.preventDefault();
      document.getElementById('confirm-title').textContent = f.dataset.confirmTitle || '¿Confirmas?';
      document.getElementById('confirm-text').textContent = f.dataset.confirm;
      document.getElementById('confirm-ok').textContent = f.dataset.confirmOk || 'Confirmar';
      dlg.returnValue = ''; dlg.showModal();
      dlg.addEventListener('close', () => {
        if (dlg.returnValue === 'ok') { f.dataset.confirmed = '1'; f.requestSubmit(); }
      }, { once: true });
    });
  });

  // Diálogos de edición (admin)
  document.querySelectorAll('dialog [data-close]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));
  document.querySelectorAll('dialog').forEach((d) => d.addEventListener('click', (e) => { if (e.target === d) d.close(); }));

  const er = document.getElementById('edit-reserva');
  if (er) {
    const f = er.querySelector('form'), modo = er.querySelector('#er-modo'), horas = er.querySelector('#er-horas');
    const sync = () => { horas.hidden = modo.value === 'dia'; };
    modo.addEventListener('change', sync);
    document.querySelectorAll('[data-edit-reserva]').forEach((b) => b.addEventListener('click', () => {
      f.action = b.dataset.action; er.querySelector('#er-folio').textContent = b.dataset.folio;
      er.querySelector('#er-espacio').value = b.dataset.espacio; er.querySelector('#er-fecha').value = b.dataset.fecha;
      modo.value = b.dataset.modo; er.querySelector('#er-ini').value = b.dataset.ini; er.querySelector('#er-fin').value = b.dataset.fin;
      sync(); er.showModal();
    }));
  }
  const eu = document.getElementById('edit-usuario');
  if (eu) {
    const f = eu.querySelector('form');
    document.querySelectorAll('[data-edit-usuario]').forEach((b) => b.addEventListener('click', () => {
      f.action = b.dataset.action; eu.querySelector('#eu-correo').textContent = b.dataset.correo;
      eu.querySelector('#eu-nombre').value = b.dataset.nombre; eu.querySelector('#eu-tel').value = b.dataset.telefono;
      eu.querySelector('#eu-activo').value = b.dataset.activo; eu.showModal();
    }));
  }

  // Botón con indicador de carga al enviar
  document.querySelectorAll('form').forEach((f) => f.addEventListener('submit', () => {
    setTimeout(() => { if (!f.hasAttribute('data-confirm') || f.dataset.confirmed) { const b = f.querySelector('button[type=submit].btn'); if (b && !b.disabled) b.classList.add('is-busy'); } }, 0);
  }));
  window.addEventListener('pageshow', () => document.querySelectorAll('.is-busy').forEach((b) => b.classList.remove('is-busy')));

  // Números que cuentan hacia arriba (KPIs)
  document.querySelectorAll('[data-count]').forEach((el) => {
    const to = Number(el.dataset.count); if (!to) return; const t0 = performance.now();
    const tick = (t) => { const k = Math.min(1, (t - t0) / 900); el.firstChild.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });

  // Filtros que se aplican al cambiar
  document.querySelectorAll('[data-autosubmit]').forEach((el) => el.addEventListener('change', () => el.form.submit()));
})();
