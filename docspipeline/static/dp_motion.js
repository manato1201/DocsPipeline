/* ページの読み進みの帯。スクロールの位置に合わせて、細い帯が横に伸びる (transform だけを動かす)。
 * 「動きを減らす」設定のときは、帯を作らない。JavaScript が無くても、本文は変わらず読める。 */
(function () {
  "use strict";

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduce && reduce.matches) return;

  function init() {
    var bar = document.createElement("div");
    bar.className = "dp-progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.appendChild(bar);

    var queued = false;
    function update() {
      queued = false;
      var doc = document.documentElement;
      var max = doc.scrollHeight - doc.clientHeight;
      var ratio = max > 0 ? Math.min(1, Math.max(0, (window.scrollY || doc.scrollTop) / max)) : 0;
      bar.style.transform = "scaleX(" + ratio.toFixed(4) + ")";
    }
    function schedule() {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(update);
    }

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    update();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
