/* sunum-site — tüm etkileşim tek dosyada. */
(function () {
  var q = new URLSearchParams(location.search);
  var body = document.body;
  if (q.has('capture')) body.classList.add('capture');
  if (q.has('light')) body.classList.add('light');

  // L tuşu: tema
  document.addEventListener('keydown', function (e) {
    if (e.key === 'l' || e.key === 'L') body.classList.toggle('light');
  });

  // Hero başlığını harflere böl
  document.querySelectorAll('.hero h1[data-split]').forEach(function (h) {
    var text = h.textContent, i = 0; h.textContent = '';
    var words = text.split(' ');
    words.forEach(function (word, wi) {
      var w = document.createElement('span'); w.className = 'w';
      word.split('').forEach(function (ch) {
        var s = document.createElement('span');
        s.textContent = ch;
        s.style.setProperty('--i', i++);
        w.appendChild(s);
      });
      h.appendChild(w);
      if (wi < words.length - 1) h.appendChild(document.createTextNode(' '));
      i++;
    });
  });

  // Ray navigasyonu bölüm id'lerinden türetilir
  var nav = document.querySelector('.rail nav');
  var secs = Array.prototype.slice.call(document.querySelectorAll('main > section[id]'));
  if (nav) {
    secs.forEach(function (s, i) {
      var a = document.createElement('a');
      a.href = '#' + s.id;
      var n = document.createElement('span'); n.className = 'n';
      n.textContent = String(i).padStart(2, '0');
      a.appendChild(n);
      var h = s.querySelector('h1,h2');
      a.appendChild(document.createTextNode(s.getAttribute('data-nav') || (h ? h.textContent : s.id)));
      nav.appendChild(a);
    });
    var links = nav.querySelectorAll('a');
    var spy = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (l) { l.classList.toggle('active', l.getAttribute('href') === '#' + e.target.id); });
      });
    }, { threshold: 0.4 });
    secs.forEach(function (s) { spy.observe(s); });
  }

  // Scroll-reveal
  var ro = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('in'); ro.unobserve(e.target); }
    });
  }, { threshold: 0.18, rootMargin: '0px 0px -40px 0px' });
  document.querySelectorAll('.rv').forEach(function (el) { ro.observe(el); });

  // Sayaçlar: <span data-count="15" data-suffix="+">
  function ease(t) { return 1 - Math.pow(1 - t, 3); }
  var co = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      var el = e.target, to = parseFloat(el.getAttribute('data-count')), suf = el.getAttribute('data-suffix') || '';
      var dec = (String(to).split('.')[1] || '').length, t0 = null;
      co.unobserve(el);
      if (body.classList.contains('capture')) { el.textContent = to.toFixed(dec) + suf; return; }
      function step(ts) {
        if (!t0) t0 = ts;
        var p = Math.min(1, (ts - t0) / 1100);
        el.textContent = (to * ease(p)).toFixed(dec) + suf;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }, { threshold: 0.6 });
  document.querySelectorAll('[data-count]').forEach(function (el) { co.observe(el); });

  // Diyagram lightbox: figure.fig içindeki svg'ye tıklayınca tam ekran açılır
  var lightbox = null;
  function openLightbox(fig) {
    var svg = fig.querySelector('svg');
    if (!svg) return;
    if (!lightbox) {
      lightbox = document.createElement('dialog');
      lightbox.className = 'fig-lightbox';
      var close = document.createElement('button');
      close.type = 'button'; close.className = 'fig-lightbox-close'; close.textContent = 'Esc / kapat';
      close.addEventListener('click', function () { lightbox.close(); });
      var bodyEl = document.createElement('div');
      bodyEl.className = 'fig-lightbox-body';
      var cap = document.createElement('figcaption');
      lightbox.appendChild(close); lightbox.appendChild(bodyEl); lightbox.appendChild(cap);
      lightbox.addEventListener('click', function (e) { if (e.target === lightbox) lightbox.close(); });
      lightbox.addEventListener('close', function () { body.classList.remove('has-lightbox'); });
      document.body.appendChild(lightbox);
    }
    var bodyEl = lightbox.querySelector('.fig-lightbox-body');
    bodyEl.innerHTML = '';
    var clone = svg.cloneNode(true);
    clone.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    bodyEl.appendChild(clone);
    var srcCap = fig.querySelector('figcaption');
    lightbox.querySelector('figcaption').textContent = srcCap ? srcCap.textContent : '';
    body.classList.add('has-lightbox');
    lightbox.showModal();
  }
  document.querySelectorAll('.fig').forEach(function (fig) {
    if (!fig.querySelector('svg')) return;
    fig.setAttribute('role', 'button');
    fig.setAttribute('tabindex', '0');
    fig.setAttribute('aria-label', 'Diyagramı büyüt');
    fig.addEventListener('click', function () { openLightbox(fig); });
    fig.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLightbox(fig); }
    });
  });

  // Ok tuşları ile bölüm gezme
  document.addEventListener('keydown', function (e) {
    if (lightbox && lightbox.open) return;
    var down = e.key === 'ArrowDown' || e.key === 'PageDown', upk = e.key === 'ArrowUp' || e.key === 'PageUp';
    if (!down && !upk) return;
    var y = window.scrollY + window.innerHeight / 2, idx = 0;
    secs.forEach(function (s, i) { if (s.offsetTop <= y) idx = i; });
    var next = down ? idx + 1 : idx - 1;
    if (secs[next]) { e.preventDefault(); secs[next].scrollIntoView({ behavior: body.classList.contains('capture') ? 'auto' : 'smooth' }); }
  });
})();
