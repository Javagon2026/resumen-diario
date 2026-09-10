(function () {
  'use strict';

  /* ---------- modo "solo títulos" ---------- */
  var modo = document.getElementById('modo');
  function setCompacto(on) {
    document.body.classList.toggle('compacto', on);
    if (modo) modo.setAttribute('aria-pressed', on ? 'true' : 'false');
    try { localStorage.setItem('rd-compacto', on ? '1' : '0'); } catch (e) {}
  }
  try { if (localStorage.getItem('rd-compacto') === '1') setCompacto(true); } catch (e) {}
  if (modo) modo.addEventListener('click', function () {
    setCompacto(!document.body.classList.contains('compacto'));
  });

  /* ---------- reproductor ---------- */
  var player = document.getElementById('player');
  if (!player) return;
  var play = document.getElementById('play');
  var stop = document.getElementById('stop');
  var status = document.getElementById('player-status');
  var audio = document.getElementById('audio');
  var mp3 = player.getAttribute('data-audio');
  var mins = player.getAttribute('data-min');
  var guion = (document.getElementById('guion-texto') || {}).textContent || '';

  function setStatus(t) { if (status) status.textContent = t; }

  /* 1) MP3 generado en el servidor (edge-tts) */
  function usarMp3() {
    // El control nativo ya trae play/pausa, barra de progreso y velocidad.
    audio.src = mp3;
    audio.controls = true;
    audio.classList.add('visible');
    player.classList.add('con-audio');
    play.hidden = true;
    stop.hidden = true;
  }

  /* 2) Voz del navegador (Web Speech API) como respaldo */
  function usarVoz() {
    if (!('speechSynthesis' in window) || !guion.trim()) {
      setStatus('Audio no disponible en este dispositivo');
      play.disabled = true;
      return;
    }
    setStatus('≈ ' + mins + ' min · voz del navegador');
    var synth = window.speechSynthesis;
    var partes = guion.replace(/\s+/g, ' ').match(/[^.!?…]+[.!?…]+["»)]?\s*|[^.!?…]+$/g) || [guion];
    var i = 0, activo = false, pausado = false;

    function elegirVoz() {
      var voces = synth.getVoices();
      var pref = ['es-AR', 'es-MX', 'es-US', 'es-ES', 'es'];
      for (var p = 0; p < pref.length; p++) {
        for (var v = 0; v < voces.length; v++) {
          var lang = (voces[v].lang || '').replace('_', '-');
          if (lang === pref[p] || (pref[p] === 'es' && lang.indexOf('es') === 0)) return voces[v];
        }
      }
      return null;
    }
    function hablar() {
      if (i >= partes.length) { terminar(); return; }
      var u = new SpeechSynthesisUtterance(partes[i]);
      var voz = elegirVoz();
      if (voz) u.voice = voz;
      u.lang = (voz && voz.lang) || 'es-AR';
      u.rate = 1.02;
      u.onend = function () { if (activo && !pausado) { i++; hablar(); } };
      u.onerror = function () { if (activo) { i++; hablar(); } };
      synth.speak(u);
      setStatus('Reproduciendo ' + Math.round((i / partes.length) * 100) + '%');
    }
    function terminar() {
      activo = false; pausado = false; i = 0;
      synth.cancel();
      play.textContent = '▶';
      stop.hidden = true;
      setStatus('≈ ' + mins + ' min · voz del navegador');
    }
    play.addEventListener('click', function () {
      if (!activo) {
        activo = true; pausado = false; i = 0;
        synth.cancel();
        play.textContent = '❚❚'; stop.hidden = false;
        hablar();
      } else if (!pausado) {
        pausado = true; synth.pause(); play.textContent = '▶'; setStatus('En pausa');
      } else {
        pausado = false; play.textContent = '❚❚';
        synth.resume();
        if (!synth.speaking) hablar();
      }
    });
    stop.addEventListener('click', terminar);
    window.addEventListener('beforeunload', function () { synth.cancel(); });
  }

  fetch(mp3, { method: 'HEAD' }).then(function (r) {
    var tipo = r.headers.get('content-type') || '';
    if (r.ok && tipo.indexOf('audio') === 0) usarMp3(); else usarVoz();
  }).catch(usarVoz);
})();
