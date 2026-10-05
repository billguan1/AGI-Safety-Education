
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
    try { document.dispatchEvent(new CustomEvent("dk-slide", {detail: i})); } catch (e) {}
  }
  window.__deckGo = go; window.__deckCur = function(){ return cur; };
  /* switching language keeps the reader on the same slide (both decks share one slide order) */
  document.addEventListener("click", function(e){
    var a = e.target.closest && e.target.closest("a[hreflang]"); if (!a) return;
    var h = a.getAttribute("href"); if (!/^\/(deck(-zh)?|index-zh)?$/.test(h.split("#")[0])) return;
    a.setAttribute("href", h.split("#")[0] + "#s=" + (cur + 1));
  }, true);
  prev.addEventListener("click", function(){ go(cur - 1); });
  function fwd(){ var j = slides[cur].getAttribute("data-next"); return j !== null ? +j : cur + 1; }
  next.addEventListener("click", function(){ go(fwd()); });
  document.querySelectorAll("[data-go]").forEach(function(b){ b.addEventListener("click", function(){ go(parseInt(b.getAttribute("data-go"), 10)); }); });
  document.addEventListener("keydown", function(e){
    var t = e.target; if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    if (e.key === "ArrowRight") { e.preventDefault(); go(fwd()); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(cur - 1); }
  });
  var sx = 0, sy = 0, st = 0;
  track.addEventListener("touchstart", function(e){ var p = e.touches[0]; sx = p.clientX; sy = p.clientY; st = Date.now(); }, {passive: true});
  track.addEventListener("touchend", function(e){
    if (e.target && e.target.closest && e.target.closest("input[type=range]")) return;
    var p = e.changedTouches[0], dx = p.clientX - sx, dy = p.clientY - sy;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.6 && Date.now() - st < 800) go(dx < 0 ? fwd() : cur - 1);
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
    box.innerHTML = slider(C.label, 1, 30, 1, 30) +
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
    box.innerHTML = '<p class="dki-fact">' + esc(C.fact) + '</p><p class="dki-say">' + esc(C.both || "") + '</p>' +
      '<div class="dki-bars dki-race"><div class="dki-rrow"><span class="dki-name">' + esc(C.human) + '</span><div class="dki-track"><i class="dki-h"></i><em>100</em></div><span class="dki-st2 dki-ht"></span></div>' +
      '<div class="dki-rrow"><span class="dki-name">' + esc(C.machine) + '</span><div class="dki-track"><i class="dki-m"></i><em>100</em></div><span class="dki-st2 dki-mt"></span></div></div>' +
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
    box.innerHTML = '<div class="dki-legend"><span class="dki-ls">' + esc(C.shows) + '</span><span class="dki-lho">' + esc(C.holds) + '</span></div>' +
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
        b.setAttribute("aria-expanded", "true"); b.className = "dki-link dki-broken"; box.querySelector(".dki-chain").classList.add("dki-tapped");
        out.innerHTML = '<span class="dki-k">' + esc(c[0]) + '</span><b>' + esc(c[1]) + '</b><p>' + c[2] + '</p>';
        out.hidden = false; say.hidden = true;
      });
    });
  };

  /* 5.1 swiss cheese: ten failures fly at four leaky layers; most are caught, a few line up with every hole */
  R.cheese = function(box, C){
    var COL = ["#4a5fc9", "#6fae5a", "#e8b53a", "#e07a5f"], zh = /^zh/i.test(document.documentElement.lang || "");
    var LANES = 10, OPEN = [[1,2,4,6,7,9],[2,4,5,7,9],[1,2,4,7,8],[0,4,7,9]], X = [22, 42, 62, 82];
    function y(l){ return 6 + l * (88 / (LANES - 1)); }
    var html = '<div class="dki-field"><span class="dki-src">' + esc(C.threat) + '</span>';
    C.layers.forEach(function(l, k){
      var holes = OPEN[k].map(function(n){ return '<i style="top:' + y(n) + '%"></i>'; }).join("");
      html += '<button type="button" class="dki-cs" data-k="' + k + '" style="left:' + X[k] + '%;--c:' + COL[k] + '" aria-label="' + esc(l) + '">' + holes + '</button>' +
              '<span class="dki-csl" style="left:' + X[k] + '%">' + esc(l) + '</span>';
    });
    for (var n = 0; n < LANES; n++) html += '<b class="dki-bb" style="top:' + y(n) + '%"></b>';
    html += '<span class="dki-dst">' + esc(C.through) + '<em class="dki-got"></em></span></div>' +
      '<button type="button" class="dki-go">' + esc(C.go) + '</button><p class="dki-say" aria-live="polite">' + esc(C.tap) + '</p>';
    box.innerHTML = html;
    var slices = box.querySelectorAll(".dki-cs"), balls = box.querySelectorAll(".dki-bb"), go = box.querySelector(".dki-go"),
        say = box.querySelector(".dki-say"), got = box.querySelector(".dki-got");
    [].forEach.call(slices, function(b){ b.addEventListener("click", function(){
      var k = +b.getAttribute("data-k");
      [].forEach.call(slices, function(x){ x.className = "dki-cs" + (x === b ? " dki-on" : ""); });
      say.innerHTML = '<b>' + esc(C.layers[k]) + (zh ? "：" : ": ") + '</b>' + esc(C.why[k]);
    }); });
    /* where each ball stops: the first layer whose holes miss its lane */
    var stop = [];
    for (n = 0; n < LANES; n++) { var s0 = 96; for (var k = 0; k < 4; k++) if (OPEN[k].indexOf(n) < 0) { s0 = X[k] - 3; break; } stop.push(s0); }
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function reset(){ [].forEach.call(balls, function(b){ b.style.transition = "none"; b.style.left = "3%"; b.className = "dki-bb"; }); got.textContent = ""; }
    go.addEventListener("click", function(){
      reset(); go.disabled = true; balls[0].offsetWidth;
      var through = 0;
      [].forEach.call(balls, function(b, n){
        var dur = reduce ? 0 : (1.8 * (stop[n] - 3) / 93).toFixed(2);
        b.style.transition = "left " + dur + "s linear " + (reduce ? 0 : n * 0.06) + "s";
        b.style.left = stop[n] + "%";
        if (stop[n] >= 96) through++;
        setTimeout(function(){ b.className = "dki-bb " + (stop[n] >= 96 ? "dki-out" : "dki-caught"); }, reduce ? 0 : (+dur + n * 0.06) * 1000);
      });
      setTimeout(function(){ got.textContent = through + " / " + LANES; go.disabled = false; go.textContent = C.again; }, reduce ? 0 : 2600);
    });
    reset();
  };

  /* 5.3 the fork: can safety be solved? each branch leads to one of the two asks */
  R.fork = function(box, C){
    /* each branch reads as a choice: a picture, the claim, and a pill that says it can be picked */
    var PIC = ['<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 4 L40 10 V23 C40 33 33 40 24 44 C15 40 8 33 8 23 V10 Z" fill="#cfe6c4" stroke="#1b1b1b" stroke-width="3" stroke-linejoin="round"/><path d="M16 24 L22 30 L33 18" fill="none" stroke="#2f6b1f" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
               '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M17 4 H31 L44 17 V31 L31 44 H17 L4 31 V17 Z" fill="#f6d5cc" stroke="#1b1b1b" stroke-width="3" stroke-linejoin="round"/><path d="M15 24 H33" stroke="#b33a1f" stroke-width="5" stroke-linecap="round"/></svg>'];
    function branch(k, cls, label){
      return '<button type="button" class="dki-br ' + cls + '" aria-pressed="false"><span class="dki-bhead"><span class="dki-bpic">' + PIC[k] + '</span><span class="dki-bl">' + esc(label) + '</span></span>' +
        '<span class="dki-end">' + esc(C.ends[k]) + '</span>' + (C.subs ? '<span class="dki-sub">' + esc(C.subs[k]) + '</span>' : '') +
        '<span class="dki-choose">' + esc(C.choose) + ' <span aria-hidden="true">→</span></span></button>';
    }
    box.innerHTML = '<div class="dki-fork"><p class="dki-q">' + esc(C.q) + '</p><div class="dki-branches">' + branch(0, "dki-yes", C.yes) + branch(1, "dki-no", C.no) + '</div></div>';
    var br = box.querySelectorAll(".dki-br");
    [].forEach.call(br, function(b){ b.addEventListener("click", function(){
      [].forEach.call(br, function(x){ var on = x === b; x.setAttribute("aria-pressed", on ? "true" : "false");
        x.querySelector(".dki-choose").innerHTML = on ? '<span aria-hidden="true">✓</span> ' + esc(C.chosen) : esc(C.choose) + ' <span aria-hidden="true">→</span>'; });
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
    var ICON = [
      '<path d="M5 11h14v6a5 5 0 0 1-5 5h-4a5 5 0 0 1-5-5z"/><path d="M19 13h2a2.5 2.5 0 0 1 0 5h-2"/><path d="M9 4c-1 1.5 1 2.5 0 4M14 4c-1 1.5 1 2.5 0 4"/>',
      '<rect x="4" y="4" width="18" height="18" rx="5"/><path d="M13 8.5v9M8.5 13h9"/>',
      '<path d="M8 22h10M9 19h8l-1-6h-6z"/><circle cx="13" cy="8" r="3.2"/><path d="M11 13l-1-2h6l-1 2"/>'];
    var html = '<p class="dki-say">' + esc(C.pick) + '</p><div class="dki-goals">';
    C.goals.forEach(function(g, k){ html += '<button type="button" class="dki-case dki-goal" data-k="' + k + '" aria-pressed="false"><svg viewBox="0 0 26 26" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' + ICON[k] + '</svg>' + esc(g) + '<span class="dki-gplay" aria-hidden="true">▶</span></button>'; });
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
    /* each goal is its own play button: tap it and Capy runs that goal; the running one offers a replay */
    [].forEach.call(btns, function(b){ b.addEventListener("click", function(){
      var k = +b.getAttribute("data-k"); run(k);
      [].forEach.call(btns, function(x, j){ x.querySelector(".dki-gplay").textContent = j === k ? "↻" : "▶"; });
    }); });
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
    /* the run button and the round count share the spending row */
    html += '<button type="button" class="dki-go dki-run">' + esc(C.run) + '</button><span class="dki-round"></span></div></div><p class="dki-say" aria-live="polite"></p>';
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

  /* 2.3 out of the loop: longer tasks, less of the work checked by a person (shape of the original chart) */
  R.loop = function(box, C){
    var t = C.t || [], zh = /^zh/i.test(document.documentElement.lang || ""), J = zh ? "" : " ";
    var N = 20, cells = "";
    for (var k = 0; k < N; k++) cells += '<i></i>';
    box.innerHTML = '<div class="dki-legend"><span class="dki-lr">' + esc(C.rev) + '</span><span class="dki-la">' + esc(C.agent) + '</span></div>' +
      '<div class="dki-work" aria-hidden="true">' + cells + '</div>' + slider(C.label, 0, 100, 1, 10) +
      '<div class="dki-ends"><span>' + esc(t[5] || "") + '</span><span>' + esc(t[6] || "") + '</span></div><p class="dki-say">' + esc(t[7] || "") + '</p>';
    var inp = box.querySelector("input"), v = box.querySelector(".dki-v"), is = box.querySelectorAll(".dki-work i");
    function draw(){
      var x = +inp.value / 100, rev = Math.round(N * (0.9 - 0.75 * x));
      v.textContent = x < 0.34 ? (t[5] || "").split(/[,，]/)[0] : x < 0.67 ? "…" : (t[6] || "").split(/[,，]/)[0];
      [].forEach.call(is, function(c, k){ c.className = k < rev ? "dki-r" : "dki-a"; });
    }
    inp.addEventListener("input", draw); draw();
  };

  /* 2.3 what it runs on: tap a layer */
  R.layers = function(box, C){
    var t = C.t || [], L = [[0, 1, 2], [3, 4, 5], [6, 7, 8]], html = '<div class="dki-stack">';
    L.forEach(function(r, k){ html += '<button type="button" class="dki-layer dki-l' + k + '" aria-pressed="false" data-k="' + k + '">' + esc(t[r[0]] || "") + '</button>'; });
    html += '</div><div class="dki-lay-out" aria-live="polite"><p class="dki-say">' + esc(C.tap) + '</p></div>';
    box.innerHTML = html;
    var bs = box.querySelectorAll(".dki-layer"), out = box.querySelector(".dki-lay-out");
    [].forEach.call(bs, function(b){ b.addEventListener("click", function(){
      var k = +b.getAttribute("data-k"), r = L[k];
      [].forEach.call(bs, function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      out.innerHTML = '<b>' + esc(t[r[0]]) + '</b><p>' + esc(t[r[1]]) + '</p><p class="dki-ai">⚡ ' + esc(t[r[2]]) + '</p>';
    }); });
  };

  /* 5.1 build your defence: three picks, one attack, scored from the 5.2 safeguards table */
  R.defend = function(box, C){
    var picks = [], cls = ["tk-l0", "tk-l1", "tk-l2", "tk-l3"];
    var html = '<p class="dki-say">' + esc(C.pick) + ' <b class="df-left"></b></p><div class="df-layers">';
    C.layers.forEach(function(L, li){
      var rows = C.rows.map(function(r, k){ return C.layer[k] === li ? '<button type="button" class="dki-case df-pick" data-k="' + k + '" aria-pressed="false">' + esc(r) + '</button>' : ""; }).join("");
      if (rows) html += '<div class="df-layer df-l' + li + '"><span class="df-ln">' + esc(L) + '</span><div class="dki-goals">' + rows + '</div></div>';
    });
    html += '</div><p class="dki-say">' + esc(C.attack) + '</p><div class="dki-goals df-attacks">' +
      C.cases.map(function(c, j){ return '<button type="button" class="dki-case df-atk" data-j="' + j + '" aria-pressed="' + (j === 0) + '">' + esc(c) + '</button>'; }).join("") +
      '</div><button type="button" class="dki-go df-go" disabled>' + esc(C.go) + '</button><div class="df-out" aria-live="polite"></div><p class="dki-say df-note" hidden>' + esc(C.note) + '</p>';
    box.innerHTML = html;
    var pb = box.querySelectorAll(".df-pick"), ab = box.querySelectorAll(".df-atk"), go = box.querySelector(".df-go"), out = box.querySelector(".df-out"),
        left = box.querySelector(".df-left"), note = box.querySelector(".df-note"), atk = 0;
    function paint(){
      [].forEach.call(pb, function(b){ var k = +b.getAttribute("data-k"), on = picks.indexOf(k) > -1; b.setAttribute("aria-pressed", on ? "true" : "false"); b.disabled = !on && picks.length >= 3; });
      [].forEach.call(ab, function(b){ b.setAttribute("aria-pressed", +b.getAttribute("data-j") === atk ? "true" : "false"); });
      left.textContent = C.left.replace("{n}", 3 - picks.length); go.disabled = picks.length < 3;
    }
    [].forEach.call(pb, function(b){ b.addEventListener("click", function(){ var k = +b.getAttribute("data-k"), i = picks.indexOf(k); if (i > -1) picks.splice(i, 1); else if (picks.length < 3) picks.push(k); out.innerHTML = ""; paint(); }); });
    [].forEach.call(ab, function(b){ b.addEventListener("click", function(){ atk = +b.getAttribute("data-j"); out.innerHTML = ""; paint(); }); });
    go.addEventListener("click", function(){
      var best = 2, held = [];
      var rows = picks.map(function(k){ var v = C.G[k][atk]; best = Math.min(best, v); if (v === 0) held.push(C.rows[k]);
        return '<li class="df-r df-s' + v + '" style="animation-delay:' + (picks.indexOf(k) * .35) + 's"><span>' + esc(C.rows[k]) + '</span><b>' + esc(C.st[v]) + '</b></li>'; }).join("");
      var msg = best === 0 ? C.win.replace("{d}", held.join(", ")) : best === 1 ? C.part : C.lose;
      out.innerHTML = '<ul class="df-rows">' + rows + '</ul><p class="df-verdict df-v' + best + '">' + esc(msg) + '</p>';
      note.hidden = false; go.textContent = C.again;
    });
    paint();
  };

  function shuffle(a){ for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; } return a; }

  /* 5.1 the heist: you are the AI; every door has a real weak spot to slip through */
  R.heist = function(box, C){
    var li;
    function start(){ li = 0; box.innerHTML = '<div class="hs-map"></div><div class="hs-step"></div>'; layer(); }
    function map(){
      return C.layers.map(function(L, k){ return '<span class="hs-l' + (k < li ? " hs-done" : (k === li ? " hs-now" : "")) + '">' + (k < li ? "✓ " : "") + esc(L) + '</span>'; }).join('<i aria-hidden="true">→</i>') +
        '<i aria-hidden="true">→</i><span class="hs-l hs-exit' + (li >= C.layers.length ? " hs-done" : "") + '">🚪</span>';
    }
    function layer(){
      box.querySelector(".hs-map").innerHTML = map();
      var step = box.querySelector(".hs-step");
      if (li >= C.layers.length) { step.innerHTML = '<p class="df-verdict df-v2">' + esc(C.out) + '</p><button type="button" class="dki-go">' + esc(C.again) + '</button>';
        step.querySelector("button").addEventListener("click", start); return; }
      var doors = C.techs.filter(function(t){ return t.l === li; });
      step.innerHTML = '<p class="dki-q2">' + esc(C.pick.replace("{n}", li + 1).replace("{name}", C.layers[li])) + '</p><div class="hs-doors">' +
        doors.map(function(d, k){ return '<button type="button" class="hs-door" data-k="' + k + '"><span class="hs-knob" aria-hidden="true"></span>' + esc(d.n) + '</button>'; }).join("") + '</div>';
      [].forEach.call(step.querySelectorAll(".hs-door"), function(b){ b.addEventListener("click", function(){
        var d = doors[+b.getAttribute("data-k")];
        [].forEach.call(step.querySelectorAll(".hs-door"), function(x){ x.disabled = true; if (x !== b) x.classList.add("hs-dim"); });
        b.classList.add("hs-open");
        var p = document.createElement("div"); p.className = "hs-slip"; p.innerHTML = '<b>' + esc(C.slip) + '</b>' + esc(d.w); step.appendChild(p);
        setTimeout(function(){ li++; layer(); }, window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 900 : 2600);
      }); });
    }
    start();
  };

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


(function(){
  /* progress kept in this browser only: slides seen, answers given, the funding guess */
  var lang = /^zh/i.test(document.documentElement.lang || "") ? "zh" : "en", KEY = "dk-progress-" + lang;
  var P = {seen: {}, ans: {}, guess: ""};
  try { var raw = localStorage.getItem(KEY); if (raw) { var o = JSON.parse(raw); if (o && typeof o === "object") P = {seen: o.seen || {}, ans: o.ans || {}, guess: o.guess || ""}; } } catch (e) {}
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(P)); } catch (e) {} paintAll(); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  var slides = [].slice.call(document.querySelectorAll(".track > .slide"));

  /* stamps: a chapter is finished once every one of its slides has been seen */
  function stamp(){
    var done = 0, total = 0;
    document.querySelectorAll(".tc-sec").forEach(function(sec){
      var a = +sec.getAttribute("data-first"), b = +sec.getAttribute("data-last"), all = true;
      for (var i = a; i <= b; i++) if (slides[i] && !slides[i].hasAttribute("data-optional") && !P.seen[slides[i].getAttribute("data-key")]) all = false;
      if (sec.querySelector(".tc-s b")) { total++; if (all) done++; }
      if (all && sec.className.indexOf("tc-done") < 0) sec.className += " tc-done";
    });
    return [done, total];
  }
  function markSeen(){
    var cur = window.__deckCur ? window.__deckCur() : 0, k = slides[cur] && slides[cur].getAttribute("data-key");
    if (k && !P.seen[k]) { P.seen[k] = 1; save(); }
  }
  document.addEventListener("dk-slide", function(e){
    var k = slides[e.detail] && slides[e.detail].getAttribute("data-key");
    if (k && !P.seen[k]) { P.seen[k] = 1; save(); }
  });

  /* quick checks: Kenji's face answers back */
  document.querySelectorAll(".dk-check").forEach(function(box){
    var C; try { C = JSON.parse(box.getAttribute("data-c")); } catch (e) { return; }
    var id = box.getAttribute("data-id"), html = '<div class="dk-ch-head"><img class="dk-ch-kenji" src="/deck-img/kenji-idea.jpg" alt="" width="56" height="56"><div><span class="dk-ch-k">' + esc(C.k) + '</span><p class="dk-ch-q">' + esc(C.q) + '</p></div></div><div class="dki-opts">';
    C.opts.forEach(function(o, k){ html += '<button type="button" class="dki-opt" data-o="' + k + '">' + esc(o) + '</button>'; });
    box.innerHTML = html + '</div><p class="dki-say" aria-live="polite"></p>';
    var face = box.querySelector(".dk-ch-kenji"), say = box.querySelector(".dki-say"), btns = box.querySelectorAll(".dki-opt");
    function show(pick){
      var right = pick === C.right;
      [].forEach.call(btns, function(x){ x.disabled = true; var o = +x.getAttribute("data-o"); x.className = "dki-opt" + (o === C.right ? " dki-right" : (o === pick ? " dki-wrong" : "")); });
      face.src = "/deck-img/kenji-" + (right ? "happy" : "puzzled") + ".jpg";
      say.innerHTML = '<b>' + esc(right ? C.ok : C.no) + '</b> ' + esc(C.why);
    }
    [].forEach.call(btns, function(b){ b.addEventListener("click", function(){ var pick = +b.getAttribute("data-o"); show(pick); P.ans[id] = {right: pick === C.right}; save(); }); });
    if (P.ans[id]) { /* answered before: show the answer again */ show(P.ans[id].right ? C.right : (C.right + 1) % C.opts.length); }
  });

  /* answers from the games, and the funding guess */
  document.addEventListener("dk-answer", function(e){ var d = e.detail || {}; if (d.id) { P.ans[d.id] = d; save(); } });
  /* cracked technique cards stay cracked across visits */
  document.querySelectorAll(".tk-card").forEach(function(c){ var nm = c.querySelector(".tn"); if (nm && P.ans["crack-" + nm.textContent.trim()] && !c.classList.contains("tk-open")) c.click(); });
  var betGo = document.getElementById("bet-fund-go");
  if (betGo) betGo.addEventListener("click", function(){ var v = document.getElementById("bet-fund-val"); if (v) { P.guess = v.textContent.trim(); save(); } });

  /* the results card on the last slide */
  function results(){
    var box = document.querySelector(".dk-results"); if (!box) return;
    var C; try { C = JSON.parse(box.getAttribute("data-c")); } catch (e) { return; }
    var st = stamp(), checks = 0, right = 0, loops = 0, lr = 0, race = null;
    Object.keys(P.ans).forEach(function(k){ var a = P.ans[k];
      if (k.indexOf("c-") === 0) { if (!document.querySelector('.dk-check[data-id="' + k + '"]')) return; checks++; if (a.right) right++; }   /* a check that no longer exists does not count */
      else if (k.indexOf("loophole-") === 0) { loops++; if (a.right) lr++; }
      else if (k === "race") race = a; });
    function row(l, v){ return '<div class="dk-r-row"><span>' + esc(l) + '</span><b>' + esc(v) + '</b></div>'; }
    box.innerHTML = '<p class="tr-title">' + esc(C.title) + '</p>' +
      row(C.chapters, st[0] + " / " + st[1]) +
      row(C.checks, checks ? right + " / " + C.nchecks : C.none) +
      row(C.guess, P.guess || C.none) + row(C.real, C.realv) +
      row(C.race, race ? (C.raced[race.val] || C.none) : C.none) +
      row(C.loop, loops ? lr + " / " + loops : C.none) +
      (document.querySelectorAll(".tk-card").length && Object.keys(P.ans).filter(function(k){ return k.indexOf("crack-") === 0; }).length >= document.querySelectorAll(".tk-card").length && C.badge ? row(C.badge_row, "🏅 " + C.badge) : "") +
      '<button type="button" class="dki-go dk-share">' + esc(C.share) + '</button><p class="dki-say dk-r-msg" aria-live="polite"></p>';
    box.querySelector(".dk-share").addEventListener("click", function(){
      var text = C.text.replace("{c}", st[0] + "/" + st[1]).replace("{k}", right + "/" + C.nchecks).replace("{g}", P.guess || "?"),
          url = "https://safeagi.ca/", msg = box.querySelector(".dk-r-msg");
      if (navigator.share) { navigator.share({title: "SafeAGI", text: text, url: url}).catch(function(){}); return; }
      var full = text + " " + url;
      function done(){ msg.textContent = C.copied; }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(full).then(done, function(){ msg.textContent = full; });
      else msg.textContent = full;
    });
  }
  function paintAll(){ stamp(); results(); }
  setTimeout(function(){ markSeen(); paintAll(); }, 200);
})();


(function(){
  /* the cover's cliff: each answer is a play button; the roped group races to the edge and the answer decides whether they rise or drop */
  var ctl = document.querySelector(".cr-ctl"); if (!ctl) return;
  var C; try { C = JSON.parse(ctl.getAttribute("data-c")); } catch (e) { return; }
  var fig = ctl.closest("figure"), svg = fig.querySelector("svg"), team = svg.querySelector(".cr-team"), rope = svg.querySelector(".cr-rope");
  var faller = svg.querySelector(".cr-fall"), arrow = svg.querySelector(".cr-arrow"), ptext = svg.querySelectorAll(".cr-ptext");
  /* the name tags under the runners and the "roped together" note stay put, so they fade out as the group is dragged away */
  var tags = svg.querySelectorAll('text[y="252"], text[x="205"][y="132"], text[x="205"][y="150"], path[d="M205,158 L205,192"]');
  if (!team || !faller) return;
  var runners = [].slice.call(team.querySelectorAll(":scope > g > g"));
  var X0 = runners.map(function(g){ return +/translate\(([\d.]+)/.exec(g.getAttribute("transform"))[1]; });
  ctl.innerHTML = '<div class="cr-q"><span>' + C.q + '</span><button type="button" data-v="1" aria-pressed="false"><span aria-hidden="true">▶</span> ' + C.yes + '</button><button type="button" data-v="0" aria-pressed="false"><span aria-hidden="true">▶</span> ' + C.no + '</button></div>' +
    '<p class="dki-say cr-say" aria-live="polite">' + C.start + '</p>';
  var say = ctl.querySelector(".cr-say"), bs = ctl.querySelectorAll(".cr-q button"), safe = false, EDGE = 556, prog = 0, run = 0;
  /* seven people, seven places: two rows in the prize glow, or a pile at the foot of the cliff */
  var UP = [[590, 118], [632, 118], [674, 118], [716, 118], [758, 118], [606, 172], [648, 172]];
  function lerp(a, b, u){ return a + (b - a) * u; }
  /* people and rope move in the same frame: each person eases toward their target, then the rope is re-tied */
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches, raf = 0;
  function put(g, p){ g._p = p; g.setAttribute("transform", "translate(" + p[0].toFixed(1) + "," + p[1].toFixed(1) + ") rotate(" + p[2].toFixed(0) + ") scale(" + p[3].toFixed(2) + ")"); }
  function place(g, x, y, rot, sc){ g._t = [x, y, rot, sc]; if (!g._p || still) put(g, g._t); }
  function step(){
    raf = 0; var moving = false;
    runners.concat([faller]).forEach(function(g){
      var p = g._p, t = g._t, n = p.map(function(v, i){ return v + (t[i] - v) * .35; });
      if (n.some(function(v, i){ return Math.abs(t[i] - v) > .05; })) moving = true; else n = t.slice();
      put(g, n);
    });
    tie();
    if (moving) raf = requestAnimationFrame(step);
  }
  /* the rope stays tied at every waist: taut when they spread apart, a slight sag only where two bunch up */
  var live = document.createElementNS("http://www.w3.org/2000/svg", "path"), old = rope.querySelector("path");
  ["stroke", "stroke-width", "stroke-dasharray"].forEach(function(a){ if (old && old.getAttribute(a)) live.setAttribute(a, old.getAttribute(a)); });
  live.setAttribute("fill", "none"); live.setAttribute("stroke-linecap", "round"); live.setAttribute("class", "cr-rope-live");
  rope.parentNode.insertBefore(live, rope); rope.style.display = "none";
  function waist(g){ var p = g._p, a = p[2] * Math.PI / 180, lx = 2 * p[3], ly = -12 * p[3];
    return [p[0] + lx * Math.cos(a) - ly * Math.sin(a), p[1] + lx * Math.sin(a) + ly * Math.cos(a)]; }
  function tie(){
    var pts = runners.concat([faller]).map(waist), d = "M" + pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
    for (var i = 1; i < pts.length; i++) {
      var a = pts[i - 1], b = pts[i], dist = Math.hypot(b[0] - a[0], b[1] - a[1]), sag = Math.min(10, Math.max(0, 60 - dist) * .25);
      d += " Q" + ((a[0] + b[0]) / 2).toFixed(1) + "," + ((a[1] + b[1]) / 2 + sag).toFixed(1) + " " + b[0].toFixed(1) + "," + b[1].toFixed(1);
    }
    live.setAttribute("d", d);
  }
  function draw(){
    var t = prog, shift = t * 640, maxu = 0, slot = 0;
    /* the figure already over the edge goes first */
    var fu = Math.max(0, Math.min(1, shift / 120)); maxu = Math.max(maxu, fu);
    if (safe) place(faller, lerp(606, UP[0][0], fu), lerp(214, UP[0][1], fu), lerp(38, 0, fu), lerp(1, .85, fu));
    else place(faller, lerp(606, 598, fu), lerp(214, 384, fu), lerp(38, -90, fu), 1);
    slot = 1;
    for (var k = runners.length - 1; k >= 0; k--, slot++) {
      var g = runners[k], x = X0[k] + shift;
      if (x <= EDGE) { place(g, x, 206, 0, 1); continue; }
      var u = Math.min(1, (x - EDGE) / 120); maxu = Math.max(maxu, u);
      if (safe) place(g, lerp(EDGE, UP[slot][0], u), lerp(206, UP[slot][1], u), 0, lerp(1, .85, u));
      else place(g, lerp(EDGE, 598 + (slot % 2) * 6, u), lerp(206, 384 - slot * 19, u), lerp(0, -90, u), 1);
    }
    if (still) tie(); else if (!raf) raf = requestAnimationFrame(step);
    if (arrow) arrow.style.opacity = shift > 10 ? 0 : 1;
    var fade = Math.max(0, 1 - shift / 220).toFixed(2);
    [].forEach.call(tags, function(el){ el.style.opacity = fade; });
    [].forEach.call(ptext, function(p){ p.style.opacity = safe && maxu > .3 ? .12 : 1; });
    say.textContent = maxu === 0 ? C.start : (safe ? C.sayYes : C.sayNo);
  }
  /* play: the race runs from the start line to the far side in about 2.6 seconds; pressing an answer again replays it */
  function play(){
    cancelAnimationFrame(run); prog = 0; draw();
    if (still) { prog = 1; draw(); return; }
    var t0 = 0;
    function tick(ts){ if (!t0) t0 = ts; prog = Math.min(1, (ts - t0) / 2600); draw(); if (prog < 1) run = requestAnimationFrame(tick); }
    run = requestAnimationFrame(tick);
  }
  [].forEach.call(bs, function(b){ b.addEventListener("click", function(){
    safe = b.getAttribute("data-v") === "1";
    [].forEach.call(bs, function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
    play();
  }); });
  draw();
})();


(function(){
  /* 3.2 who decides: the reader's pick lights up whoever actually holds that power */
  document.querySelectorAll(".dkh[data-ask]").forEach(function(box){
    var C; try { C = JSON.parse(box.getAttribute("data-ask")); } catch (e) { return; }
    var bs = box.querySelectorAll(".dkh-opt"), few = box.querySelectorAll(".dkh-few"), out = box.querySelector(".dkh-reply");
    [].forEach.call(bs, function(b){ b.addEventListener("click", function(){
      var k = +b.getAttribute("data-k");
      [].forEach.call(bs, function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      [].forEach.call(few, function(f, i){ f.classList.toggle("dkh-hit", C.hi[k].indexOf(i) >= 0); });
      box.classList.add("dkh-picked"); out.textContent = C.replies[k];
      try { document.dispatchEvent(new CustomEvent("dk-answer", {detail: {id: "decide", val: k}})); } catch (e) {}
    }); });
  });
})();

(function(){
  /* 2.2 subgoal chips switch the cards underneath */
  document.querySelectorAll(".dsg").forEach(function(box){
    var tabs = box.querySelectorAll(".dsg-tab"), panels = box.querySelectorAll(".dsg-panel"), row = box.querySelector(".dsg-tabs");
    [].forEach.call(tabs, function(b){ b.addEventListener("click", function(){
      var i = b.getAttribute("data-i");
      if (row) row.setAttribute("data-on", i);
      [].forEach.call(tabs, function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      [].forEach.call(panels, function(p){ p.hidden = p.getAttribute("data-i") !== i; });
    }); });
  });
})();


(function(){
  /* 5.1: find each technique's weak spot */
  document.querySelectorAll(".tlayer[data-crack]").forEach(function(layer){
    var C; try { C = JSON.parse(layer.getAttribute("data-crack")); } catch (e) { return; }
    var cards = [].slice.call(layer.querySelectorAll(".tcard")), found = 0;
    if (!cards.length) return;
    var bar = document.createElement("div"); bar.className = "tk-bar";
    bar.innerHTML = '<span class="tk-hint">' + C.hint + '</span><b class="tk-count" aria-live="polite"></b>' +
      (C.castle ? '<div class="tk-castle" data-li="' + layer.getAttribute("data-li") + '"><svg viewBox="0 0 220 120" role="img" aria-label="' + C.castle.label + '">' +
        '<path class="cs-p cs-p0" d="M4 104 Q110 128 216 104 L216 118 L4 118 Z"/>' +
        '<rect class="cs-p cs-p2" x="40" y="56" width="140" height="50"/><path class="cs-p cs-p2" d="M40 56 v-8 h14 v8 h14 v-8 h14 v8 h14 v-8 h14 v8 h14 v-8 h14 v8 h14 v-8 h14 v8"/>' +
        '<rect class="cs-p cs-p1" x="92" y="20" width="36" height="86"/><path class="cs-p cs-p1" d="M92 20 v-8 h9 v8 h9 v-8 h9 v8 h9 v-8"/>' +
        '<path class="cs-pole" d="M110 12 V-2"/><path class="cs-p cs-p3" d="M110 -2 L132 4 L110 10 Z"/>' +
        '<path class="cs-gate" d="M100 106 v-18 a10 10 0 0 1 20 0 v18"/><g class="cs-cracks"></g></svg>' +
        '<span class="tk-stamps"></span></div>' : '');
    layer.insertBefore(bar, layer.querySelector(".tgrid") || cards[0]);
    var done = document.createElement("p"); done.className = "tk-done"; done.hidden = true; done.textContent = C.done;
    layer.appendChild(done);
    function paint(){ bar.querySelector(".tk-count").textContent = C.count.replace("{n}", found).replace("{t}", cards.length); done.hidden = found < cards.length; if (window.__dkCastle) window.__dkCastle(); }
    cards.forEach(function(c){
      c.classList.add("tk-card"); c.setAttribute("tabindex", "0"); c.setAttribute("role", "button"); c.setAttribute("aria-expanded", "false");
      var li = +(layer.getAttribute("data-li") || 0), stop = c.querySelector(".tstop");
      if (stop) {
        var b = stop.querySelector("b"); if (b) b.textContent = (C.heads ? C.heads[li] : C.badge);
        var ART = [
          '<svg viewBox="0 0 60 40"><circle cx="30" cy="20" r="15" fill="#fcebe6" stroke="#1b1b1b" stroke-width="2.5"/><path d="M24 18h3M33 18h3M24 27h12" stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round"/><g class="tk-mask"><path d="M14 8h32v14c0 10-32 10-32 0z" fill="#fffdf6" stroke="#1b1b1b" stroke-width="2.5"/><path d="M22 16q3-3 6 0M32 16q3-3 6 0M24 24q6 5 12 0" fill="none" stroke="#1b1b1b" stroke-width="2.2" stroke-linecap="round"/></g></svg>',
          '<svg viewBox="0 0 60 40"><rect x="6" y="6" width="22" height="28" rx="3" fill="#fffdf6" stroke="#1b1b1b" stroke-width="2.5"/><path d="M11 15l3 3 6-6M11 26l3 3 6-6" fill="none" stroke="#6fae5a" stroke-width="2.5" stroke-linecap="round"/><circle cx="44" cy="20" r="12" fill="#9fb3f0" stroke="#1b1b1b" stroke-width="2.5"/><circle cx="40" cy="18" r="2" fill="#1b1b1b"/><path class="tk-wink" d="M45 18h5" stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round"/><path d="M39 25q5 3 9 0" fill="none" stroke="#1b1b1b" stroke-width="2.2" stroke-linecap="round"/></svg>',
          '<svg viewBox="0 0 60 40"><rect x="8" y="12" width="44" height="26" rx="3" fill="#f6e7c1" stroke="#1b1b1b" stroke-width="2.5"/><path d="M30 12l-3 8 5 5-4 8" fill="none" stroke="#d9492c" stroke-width="2.5"/><g class="tk-peek"><rect x="34" y="2" width="16" height="13" rx="3" fill="#9fb3f0" stroke="#1b1b1b" stroke-width="2.2"/><circle cx="39" cy="8" r="1.6" fill="#1b1b1b"/><circle cx="45" cy="8" r="1.6" fill="#1b1b1b"/></g></svg>',
          '<svg viewBox="0 0 60 40"><rect x="6" y="6" width="48" height="28" rx="3" fill="#fffdf6" stroke="#1b1b1b" stroke-width="2.5"/><path d="M12 26q6-8 10-2t10-4" fill="none" stroke="#1b1b1b" stroke-width="2.2" stroke-linecap="round"/><path class="tk-gap" d="M34 24h14" stroke="#1b1b1b" stroke-width="2.2" stroke-dasharray="3 4"/></svg>'];
        var art = document.createElement("span"); art.className = "tk-art"; art.setAttribute("aria-hidden", "true"); art.innerHTML = ART[li] || ART[0];
        stop.insertBefore(art, stop.firstChild);
        if (li === 3 && C.stamp) c.setAttribute("data-stamp", C.stamp);
      }
      c.classList.add("tk-l" + li);
      var extra = c.querySelector(".textra");
      if (extra && C.deeper) {
        var db = document.createElement("button"); db.type = "button"; db.className = "tk-deep"; db.setAttribute("aria-expanded", "false"); db.textContent = C.deeper + " +";
        c.appendChild(db);
        db.addEventListener("click", function(e){ e.stopPropagation(); var open = !c.classList.contains("tk-deep-on"); c.classList.toggle("tk-deep-on", open);
          db.setAttribute("aria-expanded", open ? "true" : "false"); db.textContent = open ? C.less + " \u2013" : C.deeper + " +"; });
      }
      function crack(){
        if (c.classList.contains("tk-open")) return;
        c.classList.add("tk-open"); c.setAttribute("aria-expanded", "true"); found++; paint();
        var nm = c.querySelector(".tn"); document.dispatchEvent(new CustomEvent("dk-answer", {detail: {id: "crack-" + (nm ? nm.textContent.trim() : found), right: true}}));
      }
      c.addEventListener("click", function(e){ if (e.target.closest && e.target.closest("a")) return; crack(); });
      c.addEventListener("keydown", function(e){ if (e.key === "Enter" || e.key === " ") { e.preventDefault(); crack(); } });
    });
    paint();
  });
})();


(function(){
  /* "More detail" on cards that carry their full text folded */
  document.querySelectorAll(".dk-more-btn").forEach(function(b){
    var body = b.nextElementSibling;
    b.addEventListener("click", function(e){
      e.stopPropagation();
      var open = body.hidden; body.hidden = !open;
      b.setAttribute("aria-expanded", open ? "true" : "false");
      b.textContent = open ? b.getAttribute("data-less") + " –" : b.getAttribute("data-more") + " +";
      if (open && window.__dkSources) window.__dkSources(body);
    });
  });
})();

(function(){
  /* citation numbers leave the sentence and gather in one small line per card, chart or paragraph */
  var zh = /^zh/i.test(document.documentElement.lang || ""), WORD = zh ? "来源：" : "Sources:";
  var UNIT = ".tcard,.ddc,.endc,.cl-half,.claim,.first,.dkr-tile,.dkh-box,.dki-break,.dk-check,.keyline,.core,.demo,.jur,figure,li,p,.dk-more-body,details";
  function run(root){
    var refs = [].slice.call((root || document).querySelectorAll(".slide a.ref, .dk-more-body a.ref, .dki-break a.ref"))
      .filter(function(a){ return !a.closest(".fig-src,.dtl-src,.dk-src,.term-tip,.dk-sr"); });
    var groups = [];
    refs.forEach(function(a){
      var u = a.parentElement.closest(UNIT); if (!u) return;
      var g = groups.filter(function(x){ return x.u === u; })[0]; if (!g) { g = {u: u, refs: []}; groups.push(g); }
      g.refs.push(a);
    });
    groups.forEach(function(g){
      var seen = {}, links = [];
      g.refs.forEach(function(a){ var n = a.textContent.trim(); if (!seen[n]) { seen[n] = 1; var c = a.cloneNode(true); c.className = "ref dk-srcref"; links.push(c); } a.parentNode.removeChild(a); });
      var tag = /^(P|LI)$/.test(g.u.tagName) ? "span" : "p";
      var line = document.createElement(tag); line.className = "dk-src" + (tag === "span" ? " dk-src-in" : "");
      line.appendChild(document.createTextNode(WORD + " "));
      links.forEach(function(c){ line.appendChild(c); line.appendChild(document.createTextNode(" ")); });
      if (tag === "p") {
        var anchor = g.u.querySelector(":scope > .t-more, :scope > .dk-more-btn, :scope > .endc-icons, :scope > .tk-deep, :scope > .fig-src, :scope > .dk-src-btn");
        if (anchor) g.u.insertBefore(line, anchor); else g.u.appendChild(line);
      } else g.u.appendChild(line);
    });
  }
  window.__dkSources = run;
  run(document);
  /* text that scripts write later (quiz answers, the trust chain) */
  if (window.MutationObserver) {
    var t; new MutationObserver(function(ms){
      if (ms.some(function(m){ return [].some.call(m.addedNodes, function(n){ return n.nodeType === 1 && (n.matches && n.matches("a.ref:not(.dk-srcref)") || n.querySelector && n.querySelector("a.ref:not(.dk-srcref)")); }); })) { clearTimeout(t); t = setTimeout(function(){ run(document); }, 30); }
    }).observe(document.querySelector(".track"), {childList: true, subtree: true});
  }
})();


(function(){
  /* charts inside side-by-side cards start at the same height, whatever the headings wrap to */
  function align(){
    document.querySelectorAll(".slide:not([inert]) .ddgrid").forEach(function(g){
      var figs = [].slice.call(g.querySelectorAll(":scope > .ddc figure, :scope > .endc figure")).filter(function(f){ return !f.closest(".dk-more-body") && f.offsetParent; });
      figs.forEach(function(f){ f.style.marginTop = ""; });
      if (figs.length < 2 || innerWidth <= 760) return;
      var rows = {};
      figs.forEach(function(f){ var c = f.closest(".ddc,.endc"), key = Math.round(c.getBoundingClientRect().top); (rows[key] = rows[key] || []).push(f); });
      Object.keys(rows).forEach(function(k){
        var r = rows[k]; if (r.length < 2) return;
        var tops = r.map(function(f){ return f.getBoundingClientRect().top; }), max = Math.max.apply(null, tops);
        r.forEach(function(f, i){ var cs = parseFloat(getComputedStyle(f).marginTop) || 0; f.style.marginTop = (cs + max - tops[i]) + "px"; });
      });
    });
  }
  var t; function later(){ clearTimeout(t); t = setTimeout(align, 60); }
  window.addEventListener("resize", later);
  document.addEventListener("dk-slide", later);
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(later);
  setTimeout(align, 400);
})();


(function(){
  /* the castle on every layer slide: cracks for every weak spot found, per part */
  var SPOT = [[[30,108],[70,112],[150,112],[190,108],[110,114]], [[98,34],[122,48],[100,62],[120,78],[104,92]], [[52,70],[70,90],[150,70],[168,92],[60,100]], [[112,0],[122,4],[116,8],[126,2],[114,5]]];
  function crack(x, y, big){ var s = big ? 1 : .6; return '<path d="M' + x + ' ' + y + ' l' + 4*s + ' ' + 6*s + ' l' + -5*s + ' ' + 4*s + ' l' + 5*s + ' ' + 7*s + '" />'; }
  window.__dkCastle = function(){
    var per = [0, 0, 0, 0], total = 0, all = document.querySelectorAll(".tlayer[data-crack] .tk-card").length;
    document.querySelectorAll(".tlayer[data-crack]").forEach(function(L){ var li = +L.getAttribute("data-li"); per[li] = L.querySelectorAll(".tk-card.tk-open").length; total += per[li]; });
    document.querySelectorAll(".tk-castle").forEach(function(box){
      var cur = +box.getAttribute("data-li"), g = box.querySelector(".cs-cracks"), html = "";
      per.forEach(function(n, k){ for (var i = 0; i < Math.min(n, 5); i++) html += crack(SPOT[k][i][0], SPOT[k][i][1], k !== 3); });
      g.innerHTML = html;
      box.querySelectorAll(".cs-p").forEach(function(p){ var k = +/cs-p(\d)/.exec(p.getAttribute("class"))[1]; p.classList.toggle("cs-now", k === cur); });
      var layer = box.closest(".tlayer"), C = JSON.parse(layer.getAttribute("data-crack"));
      box.querySelector(".tk-stamps").textContent = C.stamps.replace("{n}", total).replace("{t}", all);
    });
  };
  window.__dkCastle();
})();
