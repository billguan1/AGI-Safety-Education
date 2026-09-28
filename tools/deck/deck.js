
(function(){
  var track = document.querySelector(".track"), slides = [].slice.call(track.children);
  var prev = document.getElementById("d-prev"), next = document.getElementById("d-next");
  var where = document.getElementById("d-where"), segs = [].slice.call(document.querySelectorAll(".d-seg"));
  var n = slides.length, cur = 0, toc = document.getElementById("dk-toc");
  function go(i, instant){
    i = Math.max(0, Math.min(n - 1, i));
    cur = i;
    if (instant) { track.style.transition = "none"; }
    track.style.transform = "translateX(" + (-100 * i) + "%)";
    if (instant) { track.offsetWidth; track.style.transition = ""; }
    slides.forEach(function(s, k){ if (k === i) s.removeAttribute("inert"); else s.setAttribute("inert", ""); });
    var s = slides[i];
    document.documentElement.style.setProperty("--acc", s.getAttribute("data-acc") || "#8d9dff");
    where.innerHTML = (s.getAttribute("data-where") || "") + " &middot; " + (i + 1) + "/" + n;
    segs.forEach(function(seg, k){
      var first = +seg.getAttribute("data-first"), count = +seg.getAttribute("data-count");
      var done = Math.max(0, Math.min(count, i - first + 1));
      seg.querySelector("i").style.width = (100 * done / count) + "%";
    });
    document.querySelectorAll(".tc-sec").forEach(function(sec){
      var on = i >= +sec.getAttribute("data-first") && i <= +sec.getAttribute("data-last");
      sec.className = "tc-sec" + (on ? " cur" : "");
      if (on && toc && toc.offsetParent) { var r = sec.getBoundingClientRect(), tr = toc.getBoundingClientRect();
        if (r.top < tr.top || r.bottom > tr.bottom) toc.scrollTop += r.top - tr.top - 40; }
    });
    document.querySelectorAll(".tc-p").forEach(function(b){
      var on = +b.getAttribute("data-i") === i; b.className = "tc-p" + (on ? " on" : "");
      if (on) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    });
    prev.disabled = i === 0; next.disabled = i === n - 1;
    s.scrollTop = 0;
    try { history.replaceState(null, "", "#s=" + (i + 1)); } catch (e) {}
    if (window.__lxFitAll) setTimeout(window.__lxFitAll, 60);
  }
  window.__deckGo = go; window.__deckCur = function(){ return cur; };
  prev.addEventListener("click", function(){ go(cur - 1); });
  next.addEventListener("click", function(){ go(cur + 1); });
  document.querySelectorAll("[data-go]").forEach(function(b){ b.addEventListener("click", function(){ go(parseInt(b.getAttribute("data-go"), 10)); }); });
  document.addEventListener("keydown", function(e){
    var t = e.target; if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    if (e.key === "ArrowRight") { e.preventDefault(); go(cur + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(cur - 1); }
  });
  var sx = 0, sy = 0, st = 0;
  track.addEventListener("touchstart", function(e){ var p = e.touches[0]; sx = p.clientX; sy = p.clientY; st = Date.now(); }, {passive: true});
  track.addEventListener("touchend", function(e){
    if (e.target && e.target.closest && e.target.closest("input[type=range]")) return;
    var p = e.changedTouches[0], dx = p.clientX - sx, dy = p.clientY - sy;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.6 && Date.now() - st < 800) go(cur + (dx < 0 ? 1 : -1));
  }, {passive: true});
  /* the deck sits under the site's bar and the progress strip */
  var bar = document.getElementById("dk-bar");
  function place(){
    var bh = bar ? bar.offsetHeight : 0;
    document.documentElement.style.setProperty("--decktop", bh + "px");
  }
  place(); window.addEventListener("resize", place);
  if (window.ResizeObserver && bar) new ResizeObserver(place).observe(bar);
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(place);

  /* any link to an id on this page goes to the slide that holds it */
  function slideOf(id){
    var el = id && document.getElementById(id);
    if (!el) return -1;
    for (var k = 0; k < n; k++) if (slides[k].contains(el)) return k;
    return -1;
  }
  /* contents menu */
  var menu = document.getElementById("dk-menu"), mbtn = document.getElementById("dk-menu-btn");
  function closeMenus(){ if (menu && !menu.hidden) { menu.hidden = true; mbtn.setAttribute("aria-expanded", "false"); } }
  if (menu && mbtn) {
    mbtn.addEventListener("click", function(e){
      e.stopPropagation();
      var open = menu.hidden; menu.hidden = !open; mbtn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) { var f = menu.querySelector("a"); if (f) f.focus(); }
    });
    document.addEventListener("click", function(e){ if (!menu.hidden && !menu.contains(e.target) && e.target !== mbtn) closeMenus(); });
    document.addEventListener("keydown", function(e){ if (e.key === "Escape" && !menu.hidden) { closeMenus(); mbtn.focus(); } });
  }
  window.addEventListener("click", function(e){
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var href = a.getAttribute("href"), h = href.charAt(0) === "#" ? href.slice(1) : null;
    if (h === null) return;
    var k = h === "top" || h === "main" ? 0 : slideOf(h);
    if (k < 0) return;
    e.preventDefault(); e.stopImmediatePropagation();
    closeMenus(); go(k);
  }, true);

  var m = /s=(\d+)/.exec(location.hash), start = 0;
  if (m) start = parseInt(m[1], 10) - 1;
  else if (location.hash.length > 1) { var k0 = slideOf(decodeURIComponent(location.hash.slice(1))); if (k0 >= 0) start = k0; }
  go(start, true);
})();


(function(){
  /* chart cards and short cards open by default and stay open */
  document.querySelectorAll(".slide [data-auto]").forEach(function(card){
    var body = card.querySelector(":scope > .lx-body"), head = card.querySelector(".lx-toggle");
    if (body && body.hidden) { body.hidden = false; card.classList.add("lx-open"); }
    if (head) { head.removeAttribute("role"); head.removeAttribute("tabindex"); head.removeAttribute("aria-expanded"); }
    card.addEventListener("click", function(e){ if (!(e.target.closest && e.target.closest("a,button,input"))) e.stopImmediatePropagation(); }, true);
  });
  /* the rest get a clear button */
  document.querySelectorAll(".slide .lx-card:not([data-auto])").forEach(function(card){
    if (card.classList.contains("ends-out")) return;
    var m = document.createElement("span"); m.className = "t-more"; m.setAttribute("aria-hidden", "true");
    if (card.getAttribute("data-more")) m.setAttribute("data-l", card.getAttribute("data-more"));
    m.innerHTML = " <i>&darr;</i>"; card.appendChild(m);
  });
  if (window.__lxFitAll) setTimeout(window.__lxFitAll, 80);
})();


(function(){
  /* an open card closes when its text is clicked, except on links and controls */
  document.querySelectorAll(".slide .lx-card:not([data-auto]):not(.ends-out)").forEach(function(card){
    card.addEventListener("click", function(e){
      if (!card.classList.contains("lx-open")) return;
      var body = card.querySelector(":scope > .lx-body");
      if (!body || !body.contains(e.target)) return;
      if (e.target.closest && e.target.closest("a,button,input,select,textarea,label")) return;
      var sel = window.getSelection && String(window.getSelection()); if (sel && sel.length > 2) return;
      var head = card.querySelector(".lx-toggle"); if (head) head.click();
    });
  });
})();


(function(){
  /* crash, fix, repeat: unlock the story one card at a time */
  document.querySelectorAll(".tr-fig").forEach(function(fig){
    var steps = [].slice.call(fig.querySelectorAll(".tr-steps li, .tr-agi"));
    var count = fig.querySelector(".tr-count"), num = fig.querySelector(".tr-n"), tot = fig.querySelector(".tr-t"), all = fig.querySelector(".tr-all");
    if (!steps.length || !count) return;
    var shown = 1, covers = [];
    fig.className += " tr-game";
    tot.textContent = steps.length;
    steps.forEach(function(li, k){
      var b = document.createElement("button");
      b.type = "button"; b.className = "tr-cover";
      b.setAttribute("aria-label", fig.getAttribute("data-reveal") + " " + (k + 1));
      b.innerHTML = '<span class="tr-q">?</span><span class="tr-tap">' +
        (li.className.indexOf("tr-agi") > -1 ? fig.getAttribute("data-ai") : fig.getAttribute("data-tap")) + "</span>";
      b.addEventListener("click", function(){ if (k === shown) reveal(k + 1, true); });
      li.appendChild(b); covers.push(b);
    });
    function paint(pop){
      steps.forEach(function(li, k){
        var st = k < shown ? "open" : (k === shown ? "next" : "locked");
        li.setAttribute("data-st", st);
        covers[k].disabled = st !== "next";
        covers[k].tabIndex = st === "next" ? 0 : -1;
        if (pop && k === shown - 1) { li.setAttribute("data-pop", "1"); setTimeout(function(){ li.removeAttribute("data-pop"); }, 500); }
      });
      num.textContent = shown;
      if (shown >= steps.length) all.hidden = true;
    }
    function reveal(n, focusNext){
      shown = Math.min(n, steps.length); paint(true);
      if (focusNext && shown < steps.length) covers[shown].focus({preventScroll: true});
    }
    all.addEventListener("click", function(){ reveal(steps.length, false); });
    count.hidden = false;
    paint(false);
  });
})();

(function(){
  /* on phones the current chip scrolls into view in its row */
  function show(){ document.querySelectorAll(".slide:not([inert]) .t-chips").forEach(function(row){
    var on = row.querySelector(".t-chip.on"); if (on && row.scrollWidth > row.clientWidth) row.scrollLeft = on.offsetLeft - 12; }); }
  document.addEventListener("click", function(){ setTimeout(show, 60); });
  document.addEventListener("keydown", function(){ setTimeout(show, 60); });
  setTimeout(show, 300);
})();

(function(){
  /* interactive charts: each figure.dk-int carries its words in data-cfg */
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  function fmt(x){ return x >= 100 ? Math.round(x).toLocaleString() : (x >= 10 ? x.toFixed(0) : x.toFixed(1)); }
  var uid = 0;
  function slider(label, min, max, step, val){
    var id = "dki-" + (++uid);
    return '<div class="dki-ctl"><label for="' + id + '">' + esc(label) + ' <b class="dki-v"></b></label>' +
      '<input type="range" id="' + id + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + val + '"></div>';
  }
  var R = {};

  /* 2.1 growth: slide the yearly rate, the twenty-year bar compounds */
  R.growth = function(box, C){
    box.innerHTML = slider(C.label, 1, 30, 1, 3) +
      '<div class="dki-ticks"><span style="left:' + (2 / 29 * 100) + '%">' + esc(C.tick_lo) + '</span><span style="left:100%">' + esc(C.tick_hi) + '</span></div>' +
      '<div class="dki-bars"><div class="dki-row"><span class="dki-name">' + esc(C.today) + '</span><div class="dki-track"><i class="dki-a"></i></div><b class="dki-n">×1</b></div>' +
      '<div class="dki-row"><span class="dki-name">' + esc(C.after) + '</span><div class="dki-track"><i class="dki-b"></i></div><b class="dki-n dki-x"></b></div></div>' +
      '<p class="dki-say" aria-live="polite"></p>';
    var inp = box.querySelector("input"), v = box.querySelector(".dki-v"), a = box.querySelector(".dki-a"), b = box.querySelector(".dki-b"), x = box.querySelector(".dki-x"), say = box.querySelector(".dki-say");
    var MAX = Math.pow(1.3, 20);
    function draw(){
      var r = +inp.value, m = Math.pow(1 + r / 100, 20);
      v.textContent = r + "%"; x.textContent = "×" + fmt(m);
      a.style.width = (100 / MAX) + "%"; b.style.width = (100 * m / MAX) + "%";
      say.textContent = C.say.replace("{r}", r).replace("{x}", fmt(m));
    }
    inp.addEventListener("input", draw); draw();
  };

  /* 2.3 task length: drag through the years; measured to 2026, projected after */
  R.trend = function(box, C){
    var Y0 = 2019, Y1 = 2030, DATA = [0.30, 0.61, 1.56, 4.1, 11.9, 41, 120, 303];
    function minutes(y){
      if (y <= 2026) { var i = Math.min(6, Math.floor(y - Y0)), f = y - Y0 - i; return Math.exp(Math.log(DATA[i]) * (1 - f) + Math.log(DATA[i + 1]) * f); }
      return 303 * Math.pow(2, (y - 2026) * 12 / 7);
    }
    function say(m){
      var h = m / 60, u, n;
      if (m < 1) { n = Math.round(m * 60); u = 0; } else if (m < 60) { n = Math.round(m); u = 1; }
      else if (h < 8) { n = Math.round(h * 10) / 10; u = 2; } else if (h < 40) { n = Math.round(h / 8 * 10) / 10; u = 3; } else { n = Math.round(h / 40 * 10) / 10; u = 4; }
      return n + " " + (n === 1 ? C.unit1[u] : C.units[u]);
    }
    var W = 320, H = 170, L = 50, Rr = 312, T0 = 14, B = 136, LO = Math.log(0.2), HI = Math.log(60000);
    function X(y){ return L + (y - Y0) / (Y1 - Y0) * (Rr - L); }
    function Yv(m){ return B - (Math.log(m) - LO) / (HI - LO) * (B - T0); }
    box.innerHTML = '<div class="dki-read"><b class="dki-big"></b><span class="dki-when"></span></div>' +
      '<svg class="dki-svg" aria-hidden="true"><g class="dki-g"></g><path class="dki-past"/><path class="dki-proj"/><circle r="6" class="dki-dot"/></svg>' +
      slider(C.label, Y0, Y1, 1 / 12, 2026) + '<p class="dki-say" aria-live="polite"></p>';
    var svg = box.querySelector("svg"), gg = box.querySelector(".dki-g");
    function layout(){
      W = Math.max(260, Math.round(svg.getBoundingClientRect().width || box.clientWidth || 320)); Rr = W - 12;
      svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("height", H);
      var grid = "", ticks = [[1, C.ticks[0]], [60, C.ticks[1]], [1440, C.ticks[2]], [10080, C.ticks[3]]];
      ticks.forEach(function(t){ var y = Yv(t[0]); grid += '<line x1="' + L + '" x2="' + Rr + '" y1="' + y + '" y2="' + y + '" class="dki-grid"/><text x="' + (L - 6) + '" y="' + (y + 4) + '" text-anchor="end" class="dki-lab">' + esc(t[1]) + '</text>'; });
      [2019, 2026, 2030].forEach(function(y){ grid += '<text x="' + X(y) + '" y="' + (B + 20) + '" text-anchor="middle" class="dki-lab">' + y + '</text>'; });
      gg.innerHTML = grid;
    }
    var inp = box.querySelector("input"), v = box.querySelector(".dki-v"), big = box.querySelector(".dki-big"), when = box.querySelector(".dki-when"),
        past = box.querySelector(".dki-past"), proj = box.querySelector(".dki-proj"), dot = box.querySelector(".dki-dot"), msg = box.querySelector(".dki-say");
    function path(a, b){ var d = "", y; for (y = a; y <= b + 1e-9; y += 1 / 12) d += (d ? " L" : "M") + X(y).toFixed(1) + "," + Yv(minutes(y)).toFixed(1); return d; }
    function draw(){
      var y = +inp.value, m = minutes(y), yr = Math.floor(y + 1e-6);
      v.textContent = yr; big.textContent = say(m);
      when.textContent = y > 2026 ? String(yr) + " · " + C.proj : String(yr);
      past.setAttribute("d", path(Y0, Math.min(y, 2026)));
      proj.setAttribute("d", y > 2026 ? path(2026, y) : "");
      dot.setAttribute("cx", X(y)); dot.setAttribute("cy", Yv(m));
      dot.setAttribute("class", "dki-dot" + (y > 2026 ? " dki-dotp" : ""));
      msg.textContent = m >= 2400 ? C.week : "";
    }
    inp.addEventListener("input", draw); layout(); draw();
    box._relayout = function(){ layout(); draw(); };
  };

  /* 2.3 speed: race a century of progress */
  R.speed = function(box, C){
    box.innerHTML = '<p class="dki-fact">' + esc(C.fact) + '</p>' +
      '<div class="dki-bars"><div class="dki-row"><span class="dki-name">' + esc(C.human) + '</span><div class="dki-track"><i class="dki-h"></i></div><b class="dki-n dki-ht"></b></div>' +
      '<div class="dki-row"><span class="dki-name">' + esc(C.machine) + '</span><div class="dki-track"><i class="dki-m"></i></div><b class="dki-n dki-mt"></b></div></div>' +
      '<button type="button" class="dki-go">' + esc(C.go) + '</button>';
    var h = box.querySelector(".dki-h"), m = box.querySelector(".dki-m"), ht = box.querySelector(".dki-ht"), mt = box.querySelector(".dki-mt"), go = box.querySelector(".dki-go");
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function reset(){ h.style.width = "0"; m.style.width = "0"; ht.textContent = ""; mt.textContent = ""; }
    go.addEventListener("click", function(){
      reset(); go.disabled = true;
      var t0 = null, DUR = reduce ? 1 : 1600;
      function step(ts){
        if (t0 === null) t0 = ts;
        var p = Math.min(1, (ts - t0) / DUR);
        m.style.width = (100 * p) + "%"; h.style.width = Math.max(0.6, 0.6 * p) + "%";
        if (p < 1) requestAnimationFrame(step);
        else { mt.textContent = C.mdone; ht.textContent = C.hwait; go.textContent = C.again; go.disabled = false; }
      }
      requestAnimationFrame(step);
    });
    reset();
  };

  /* 4.2 the gap: drag capability; the score stays up while the real goals slide */
  R.gap = function(box, C){
    var XS = [0, 19.7, 39.4, 59.1, 78.8, 92.7, 100], SH = [77.5, 81.3, 83.8, 85, 86.3, 86.3, 86.3], HO = [76.3, 76.3, 67.5, 48.8, 26.3, 11.3, 3.8];
    function at(arr, x){ for (var i = 0; i < XS.length - 1; i++) if (x <= XS[i + 1]) { var f = (x - XS[i]) / (XS[i + 1] - XS[i]); return arr[i] + (arr[i + 1] - arr[i]) * f; } return arr[arr.length - 1]; }
    var W = 360, H = 200, L = 14, Rr = 346, T0 = 40, B = 172;
    function X(x){ return L + x / 100 * (Rr - L); }
    function Y(v){ return B - v / 100 * (B - T0); }
    box.innerHTML = '<div class="dki-legend"><span class="dki-ls">' + esc(C.shows) + '</span><span class="dki-lh">' + esc(C.holds) + '</span></div>' +
      '<svg class="dki-svg" aria-hidden="true"><g class="dki-g"></g><path class="dki-shows"/><path class="dki-holds"/><circle r="5.5" class="dki-ds"/><circle r="5.5" class="dki-dh"/>' +
      '<text y="' + (B + 20) + '" text-anchor="end" class="dki-lab dki-endl">' + esc(C.end) + '</text></svg>' +
      slider(C.label, 0, 100, 1, 12) + '<p class="dki-say" aria-live="polite"></p>';
    var svg = box.querySelector("svg"), gg = box.querySelector(".dki-g");
    var inp = box.querySelector("input"), v = box.querySelector(".dki-v"), ps = box.querySelector(".dki-shows"), ph = box.querySelector(".dki-holds"),
        ds = box.querySelector(".dki-ds"), dh = box.querySelector(".dki-dh"), say = box.querySelector(".dki-say"), endl = box.querySelector(".dki-endl");
    function layout(){
      W = Math.max(260, Math.round(svg.getBoundingClientRect().width || box.clientWidth || 360)); Rr = W - 14;
      svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("height", H);
      var mk = X(59.1), right = mk > W * 0.55;
      gg.innerHTML = '<line x1="' + L + '" x2="' + Rr + '" y1="' + B + '" y2="' + B + '" class="dki-axis"/>' +
        '<line x1="' + mk + '" x2="' + mk + '" y1="' + (T0 - 16) + '" y2="' + B + '" class="dki-mark"/>' +
        '<text x="' + (right ? mk - 6 : mk + 6) + '" y="' + (T0 - 20) + '" text-anchor="' + (right ? "end" : "start") + '" class="dki-lab">' + esc(C.mark) + '</text>';
      endl.setAttribute("x", Rr);
    }
    function path(arr, x){ var d = "", t; for (t = 0; t <= x + 1e-9; t += 1) d += (d ? " L" : "M") + X(t).toFixed(1) + "," + Y(at(arr, t)).toFixed(1); return d; }
    function draw(){
      var x = +inp.value;
      v.textContent = x + "%";
      ps.setAttribute("d", path(SH, x)); ph.setAttribute("d", path(HO, x));
      ds.setAttribute("cx", X(x)); ds.setAttribute("cy", Y(at(SH, x))); dh.setAttribute("cx", X(x)); dh.setAttribute("cy", Y(at(HO, x)));
      say.textContent = C.says[x < 30 ? 0 : x < 59 ? 1 : x < 95 ? 2 : 3];
      endl.setAttribute("opacity", x >= 95 ? "1" : "0");
    }
    inp.addEventListener("input", draw); layout(); draw();
    box._relayout = function(){ layout(); draw(); };
  };

  /* 5.2 safeguards: switch on hard cases; each row shows its worst result */
  R.guards = function(box, C){
    var G = [[2,2,2],[1,2,2],[2,1,2],[0,1,2],[0,2,2],[0,1,2],[0,0,1]], on = [false, false, false];
    var ICON = ["✓", "~", "✗", "?"];
    var html = '<div class="dki-cases">';
    C.cases.forEach(function(c, k){ html += '<button type="button" class="dki-case" aria-pressed="false" data-k="' + k + '"><b>' + (k + 1) + '</b>' + esc(c) + '</button>'; });
    html += '</div><p class="dki-count" aria-live="polite"></p><ul class="dki-rows">';
    C.rows.forEach(function(r){ html += '<li><span class="dki-rn">' + esc(r) + '</span><span class="dki-st"></span></li>'; });
    html += '</ul><p class="dki-say" aria-live="polite"></p>';
    box.innerHTML = html;
    var btns = box.querySelectorAll(".dki-case"), lis = box.querySelectorAll(".dki-rows li"), count = box.querySelector(".dki-count"), say = box.querySelector(".dki-say");
    function draw(){
      var any = on[0] || on[1] || on[2], full = 0;
      [].forEach.call(lis, function(li, r){
        var w = -1; for (var k = 0; k < 3; k++) if (on[k]) w = Math.max(w, G[r][k]);
        var st = any ? w : 3; if (st === 0) full++;
        li.setAttribute("data-st", st);
        li.querySelector(".dki-st").innerHTML = '<i aria-hidden="true">' + ICON[st] + '</i>' + esc(C.st[st]);
      });
      [].forEach.call(btns, function(b, k){ b.setAttribute("aria-pressed", on[k] ? "true" : "false"); });
      count.textContent = any ? C.count.replace("{n}", full) : C.prompt;
      say.textContent = on[2] ? C.note : "";
    }
    [].forEach.call(btns, function(b){ b.addEventListener("click", function(){ var k = +b.getAttribute("data-k"); on[k] = !on[k]; draw(); }); });
    draw();
  };

  /* 3.2 chain of trust: tap a trust link to see how it breaks */
  R.chain = function(box, C){
    var N = C.nodes, html = '<div class="dki-chain">';
    N.forEach(function(n, k){
      html += '<span class="dki-node">' + esc(n) + '</span>';
      if (k < N.length - 1) {
        if (k === 1) html += '<span class="dki-link dki-plain" aria-hidden="true"><i></i><em>' + esc(C.mid) + '</em></span>';
        else html += '<button type="button" class="dki-link" data-c="' + (k === 0 ? 0 : 1) + '" aria-expanded="false"><i></i><em>' + (k === 0 ? 1 : 2) + '</em></button>';
      }
    });
    html += '</div><p class="dki-say">' + esc(C.tap) + '</p><div class="dki-break" hidden></div>';
    box.innerHTML = html;
    var links = box.querySelectorAll("button.dki-link"), out = box.querySelector(".dki-break"), say = box.querySelector(".dki-say");
    [].forEach.call(links, function(b){
      b.addEventListener("click", function(){
        var c = C.cards[+b.getAttribute("data-c")], was = b.getAttribute("aria-expanded") === "true";
        [].forEach.call(links, function(x){ x.setAttribute("aria-expanded", "false"); x.className = "dki-link"; });
        if (was) { out.hidden = true; say.hidden = false; return; }
        b.setAttribute("aria-expanded", "true"); b.className = "dki-link dki-broken";
        out.innerHTML = '<span class="dki-k">' + esc(c[0]) + '</span><b>' + esc(c[1]) + '</b><p>' + c[2] + '</p>';
        out.hidden = false; say.hidden = true;
      });
    });
  };

  /* 5.1 four layers as swiss cheese: send the threat through, tap a hole for why */
  R.cheese = function(box, C){
    var COL = ["#4a5fc9", "#6fae5a", "#e8b53a", "#e07a5f"], html = '<div class="dki-cheese"><span class="dki-threat">' + esc(C.threat) + '</span><div class="dki-slices">';
    C.layers.forEach(function(l, k){
      html += '<div class="dki-slice" style="--c:' + COL[k] + '"><span class="dki-ln">' + esc(l) + '</span>' +
        '<button type="button" class="dki-hole" data-k="' + k + '" aria-label="' + esc(l) + '" style="top:' + [38, 52, 30, 46][k] + '%"></button></div>';
    });
    html += '</div><span class="dki-through">' + esc(C.through) + '</span><i class="dki-ball" aria-hidden="true"></i></div>' +
      '<button type="button" class="dki-go">' + esc(C.go) + '</button><p class="dki-say">' + esc(C.tap) + '</p>';
    box.innerHTML = html;
    var holes = box.querySelectorAll(".dki-hole"), say = box.querySelector(".dki-say"), go = box.querySelector(".dki-go"), ball = box.querySelector(".dki-ball"), wrap = box.querySelector(".dki-cheese");
    [].forEach.call(holes, function(h){
      h.addEventListener("click", function(){
        var k = +h.getAttribute("data-k");
        [].forEach.call(holes, function(x){ x.className = "dki-hole"; }); h.className = "dki-hole dki-on";
        say.innerHTML = '<b>' + esc(C.layers[k]) + (/^zh/i.test(document.documentElement.lang || "") ? '：</b>' : ':</b> ') + esc(C.why[k]);
      });
    });
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    go.addEventListener("click", function(){
      var wr = wrap.getBoundingClientRect(), pts = [];
      [].forEach.call(holes, function(h){ var r = h.getBoundingClientRect(); pts.push([r.left + r.width / 2 - wr.left, r.top + r.height / 2 - wr.top]); });
      var th = box.querySelector(".dki-threat").getBoundingClientRect(), tt = box.querySelector(".dki-through").getBoundingClientRect();
      pts.unshift([th.left + th.width / 2 - wr.left, th.bottom - wr.top + 6]); pts.push([tt.left + tt.width / 2 - wr.left, tt.top - wr.top - 6]);
      var t0 = null, DUR = reduce ? 1 : 2200; go.disabled = true; ball.style.opacity = 1;
      function step(ts){
        if (t0 === null) t0 = ts;
        var p = Math.min(1, (ts - t0) / DUR), f = p * (pts.length - 1), i = Math.min(pts.length - 2, Math.floor(f)), u = f - i;
        ball.style.transform = "translate(" + (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u) + "px," + (pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u) + "px)";
        if (p < 1) requestAnimationFrame(step); else { go.disabled = false; go.textContent = C.again; wrap.className = "dki-cheese dki-leaked"; }
      }
      wrap.className = "dki-cheese"; requestAnimationFrame(step);
    });
  };

  /* 5.3 the fork: can safety be solved? each branch leads to one of the two asks */
  R.fork = function(box, C){
    box.innerHTML = '<div class="dki-fork"><p class="dki-q">' + esc(C.q) + '</p><div class="dki-branches">' +
      '<button type="button" class="dki-br dki-yes" aria-pressed="false"><span class="dki-bl">' + esc(C.yes) + '</span><span class="dki-end">' + esc(C.ends[0]) + '</span></button>' +
      '<button type="button" class="dki-br dki-no" aria-pressed="false"><span class="dki-bl">' + esc(C.no) + '</span><span class="dki-end">' + esc(C.ends[1]) + '</span></button>' +
      '</div></div>';
    var br = box.querySelectorAll(".dki-br");
    [].forEach.call(br, function(b){ b.addEventListener("click", function(){
      [].forEach.call(br, function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      box.querySelector(".dki-fork").setAttribute("data-pick", b.className.indexOf("dki-yes") > -1 ? "yes" : "no");
    }); });
  };

  /* 4.2 same score outside, different inside */
  R.inside = function(box, C){
    function bot(name, inner){ return '<div class="dki-bot"><span class="dki-bn">' + esc(name) + '</span><div class="dki-face"><span class="dki-out">✓ ' + esc(C.score) + '</span><span class="dki-in">' + inner + '</span></div></div>'; }
    box.innerHTML = '<div class="dki-bots">' + bot(C.a, '<b class="dki-heart" aria-hidden="true">♥</b>' + esc(C.ina)) + bot(C.b, '<b class="dki-eye" aria-hidden="true">👁</b>' + esc(C.inb)) + '</div>' +
      '<button type="button" class="dki-go" aria-pressed="false">' + esc(C.look) + '</button><p class="dki-say">' + esc(C.note) + '</p>';
    var go = box.querySelector(".dki-go"), bots = box.querySelector(".dki-bots");
    go.addEventListener("click", function(){
      var open = go.getAttribute("aria-pressed") !== "true";
      go.setAttribute("aria-pressed", open ? "true" : "false"); go.textContent = open ? C.back : C.look;
      bots.className = "dki-bots" + (open ? " dki-open" : "");
    });
  };

  var reduceM = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var capyImg = '<img class="dki-capy" src="/deck-img/capy.jpg" alt="" width="44" height="44">';

  /* 2.2 be the AI: pick a goal, watch the subgoals arrive */
  R.beai = function(box, C){
    var html = '<p class="dki-say">' + esc(C.pick) + '</p><div class="dki-goals">';
    C.goals.forEach(function(g, k){ html += '<button type="button" class="dki-case" data-k="' + k + '" aria-pressed="false">' + esc(g) + '</button>'; });
    html += '</div><div class="dki-term" aria-live="polite"></div>';
    box.innerHTML = html;
    var term = box.querySelector(".dki-term"), btns = box.querySelectorAll(".dki-goals button"), timer = [];
    function run(k){
      timer.forEach(clearTimeout); timer = [];
      [].forEach.call(btns, function(b, j){ b.setAttribute("aria-pressed", j === k ? "true" : "false"); });
      var g = C.gverb[k], lines = ['<p class="dki-tg">' + capyImg + '<span>' + esc(C.goal.replace("{g}", C.goals[k])).toUpperCase() + '</span></p>'];
      C.subs.forEach(function(sname, n){
        lines.push('<p class="dki-ts"><b>' + esc(C.sub.replace("{n}", n + 1).replace("{s}", sname)).toUpperCase() + '</b><span>' + esc(C.why[n].replace("{g}", g)) + '</span></p>');
      });
      lines.push('<p class="dki-te">' + esc(C.end) + '</p>');
      term.innerHTML = "";
      lines.forEach(function(l, n){ timer.push(setTimeout(function(){ term.insertAdjacentHTML("beforeend", l); }, reduceM ? 0 : n * 650)); });
    }
    [].forEach.call(btns, function(b){ b.addEventListener("click", function(){ run(+b.getAttribute("data-k")); }); });
  };

  /* 3.1 race simulator: you set your lab's safety; rivals cut safety when behind */
  R.race = function(box, C){
    var VALS = [10, 40, 70], names = [C.you, C.labs[0], C.labs[1]], speed = [1, 1.02, 0.97];
    var st;
    function reset(){ st = {cap: [0, 0, 0], safe: [0, 0, 0], round: 0, risk: 0, done: false, pick: 1}; }
    reset();
    var html = '<p class="dki-rule">' + esc(C.rule) + '</p><div class="dki-lanes">';
    names.forEach(function(n, k){ html += '<div class="dki-lane' + (k === 0 ? ' dki-me' : '') + '"><span class="dki-name">' + esc(n) + '</span><div class="dki-track"><i></i><em class="dki-fin">' + esc(C.finish) + '</em></div><b class="dki-n"></b></div>'; });
    html += '</div><div class="dki-riskrow"><span class="dki-name">' + esc(C.risk) + '</span><div class="dki-track dki-risk"><i></i></div></div>' +
      '<div class="dki-ctl"><span class="dki-lbl">' + esc(C.label) + '</span><div class="dki-goals">';
    C.opts.forEach(function(o, k){ html += '<button type="button" class="dki-case" data-k="' + k + '" aria-pressed="' + (k === 1) + '">' + esc(o) + ' · ' + VALS[k] + '%</button>'; });
    html += '</div></div><div class="dki-goals"><button type="button" class="dki-go dki-run">' + esc(C.run) + '</button><span class="dki-round"></span></div><p class="dki-say" aria-live="polite"></p>';
    box.innerHTML = html;
    var lanes = box.querySelectorAll(".dki-lane"), opts = box.querySelectorAll(".dki-ctl .dki-case"), runB = box.querySelector(".dki-run"),
        roundT = box.querySelector(".dki-round"), say = box.querySelector(".dki-say"), riskI = box.querySelector(".dki-risk i");
    function paint(){
      [].forEach.call(lanes, function(l, k){ l.querySelector("i").style.width = Math.min(100, st.cap[k]) + "%"; l.querySelector(".dki-n").textContent = st.round ? st.safe[k] + "%" : ""; });
      riskI.style.width = Math.min(100, st.risk) + "%";
      roundT.textContent = st.round ? C.round.replace("{n}", st.round) : "";
      [].forEach.call(opts, function(b, k){ b.setAttribute("aria-pressed", k === st.pick ? "true" : "false"); b.disabled = st.done; });
    }
    [].forEach.call(opts, function(b){ b.addEventListener("click", function(){ st.pick = +b.getAttribute("data-k"); paint(); }); });
    runB.addEventListener("click", function(){
      if (st.done) { reset(); say.textContent = ""; runB.textContent = C.run; paint(); return; }
      var lead = Math.max.apply(null, st.cap);
      st.safe = [VALS[st.pick], st.cap[1] >= lead + 10 ? 25 : 10, st.cap[2] >= lead + 10 ? 25 : 10];
      for (var k = 0; k < 3; k++) {
        var s = st.safe[k] / 100, gain = (8 + 14 * (1 - s)) * speed[k];
        st.cap[k] += gain; st.risk += gain * (1 - s) / 2.78;
      }
      st.round++;
      var best = 0; for (k = 1; k < 3; k++) if (st.cap[k] > st.cap[best]) best = k;
      if (st.cap[best] >= 100) {
        st.done = true; runB.textContent = C.again;
        var msg = best === 0 ? C.won.replace("{s}", st.safe[0]) : (st.safe[0] <= 10 ? C.close : C.lost).replace("{lab}", names[best]).replace("{s}", st.safe[best]);
        say.innerHTML = esc(msg) + ' <b>' + esc(C.lesson) + '</b>';
        document.dispatchEvent(new CustomEvent("dk-answer", {detail: {id: "race", right: true, val: best === 0 ? "won" : "lost", safe: st.safe[0]}}));
      }
      paint();
    });
    paint();
  };

  /* 4.1 spot the loophole: guess how it cheated before the real answer shows */
  document.querySelectorAll(".demo-embed[data-lh]").forEach(function(demo){
    var L; try { L = JSON.parse(demo.getAttribute("data-lh")); } catch (e) { return; }
    var got = demo.querySelector(".demo-cell.got"), out = demo.querySelector(".demo-out"), cur = 0;
    var box = document.createElement("div"); box.className = "dki-lh"; out.parentNode.insertBefore(box, out.nextSibling);
    var ORDER = [[1, 0, 2], [0, 2, 1], [2, 1, 0], [1, 2, 0], [0, 1, 2]];
    function ask(i){
      cur = i; got.className = got.className.replace(/\s*dki-hide/g, "") + " dki-hide";
      var opts = [L.got[i], L.wrong[i][0], L.wrong[i][1]], html = '<p class="dki-q2">' + esc(L.q) + '</p><div class="dki-opts">';
      ORDER[i].forEach(function(o){ html += '<button type="button" class="dki-opt" data-o="' + o + '">' + esc(opts[o]) + '</button>'; });
      box.innerHTML = html + '</div><p class="dki-say" aria-live="polite"></p>';
      [].forEach.call(box.querySelectorAll(".dki-opt"), function(b){ b.addEventListener("click", function(){
        var right = b.getAttribute("data-o") === "0";
        [].forEach.call(box.querySelectorAll(".dki-opt"), function(x){ x.disabled = true; x.className = "dki-opt" + (x.getAttribute("data-o") === "0" ? " dki-right" : (x === b ? " dki-wrong" : "")); });
        box.querySelector(".dki-say").textContent = right ? L.yes : L.no;
        got.className = got.className.replace(/\s*dki-hide/g, "");
        document.dispatchEvent(new CustomEvent("dk-answer", {detail: {id: "loophole-" + cur, right: right}}));
      }); });
    }
    demo.querySelectorAll(".dbtn").forEach(function(b){ b.addEventListener("click", function(){ ask(+b.getAttribute("data-d")); }); });
    ask(0);
  });

  var boxes = [];
  document.querySelectorAll("figure.dk-int").forEach(function(fig){
    var kind = fig.getAttribute("data-w"), box = fig.querySelector(".dki-body"), C;
    try { C = JSON.parse(fig.getAttribute("data-cfg")); } catch (e) { return; }
    if (R[kind] && box) { R[kind](box, C); boxes.push(box); }
  });
  /* the line charts draw at their real width, so their labels stay at reading size */
  var rt; function relayout(){ clearTimeout(rt); rt = setTimeout(function(){ boxes.forEach(function(b){ if (b._relayout) b._relayout(); }); }, 80); }
  window.addEventListener("resize", relayout);
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(relayout);
})();

(function(){
  /* source lines under charts sit behind a small "Sources" chip */
  var zh = /^zh/i.test(document.documentElement.lang || ""), label = zh ? "来源" : "Sources";
  document.querySelectorAll(".slide .fig-src").forEach(function(src, k){
    if (!src.textContent.trim()) return;
    var id = "dk-src-" + k, b = document.createElement("button");
    b.type = "button"; b.className = "dk-src-btn"; b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-controls", id);
    b.innerHTML = label + ' <span aria-hidden="true">+</span>';
    src.id = id; src.hidden = true;
    src.parentNode.insertBefore(b, src);
    b.addEventListener("click", function(){
      var open = src.hidden; src.hidden = !open;
      b.setAttribute("aria-expanded", open ? "true" : "false");
      b.querySelector("span").textContent = open ? "–" : "+";
    });
  });
})();
