
(function(){
  var track = document.querySelector(".track"), slides = [].slice.call(track.children);
  var prev = document.getElementById("d-prev"), next = document.getElementById("d-next");
  var where = document.getElementById("d-where"), segs = [].slice.call(document.querySelectorAll(".d-seg"));
  var n = slides.length, cur = 0;
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
