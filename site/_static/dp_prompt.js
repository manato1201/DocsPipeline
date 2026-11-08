/* `.. prompt::` のブロックに、「プロンプトをコピー」ボタンを足す。
 * JavaScript が無くても、本文は読めて、選択してコピーできる (ボタンだけが出ない)。 */
(function () {
  "use strict";

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // https でないページ (file:// など) 向けの代替。選択して、コピーの命令を使う。
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy") ? resolve() : reject(new Error("copy failed"));
      } catch (error) {
        reject(error);
      } finally {
        document.body.removeChild(area);
      }
    });
  }

  function setup(box) {
    if (box.getAttribute("data-dp-ready")) return;
    var pre = box.querySelector("pre");
    if (!pre) return;
    box.setAttribute("data-dp-ready", "1");

    var titleNode = box.querySelector(".dp-prompt-title");
    var title = titleNode ? titleNode.textContent.trim() : "プロンプト";

    var button = document.createElement("button");
    button.type = "button";
    button.className = "dp-prompt-copy";
    button.textContent = "プロンプトをコピー";
    button.setAttribute("aria-label", title + " をコピー");

    var status = document.createElement("span");
    status.className = "dp-prompt-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");

    var timer = null;
    function report(message, failed) {
      status.textContent = message;
      status.classList.toggle("dp-prompt-failed", !!failed);
      clearTimeout(timer);
      timer = setTimeout(function () { status.textContent = ""; }, 2500);
    }

    button.addEventListener("click", function () {
      var text = pre.textContent.replace(/\s+$/, "");
      copyText(text).then(
        function () { report("コピーしました", false); },
        function () { report("コピーできませんでした。本文を選択してコピーしてください", true); }
      );
    });

    var bar = document.createElement("div");
    bar.className = "dp-prompt-bar";
    bar.appendChild(button);
    bar.appendChild(status);
    if (titleNode) {
      titleNode.appendChild(bar);
    } else {
      box.insertBefore(bar, box.firstChild);
    }
  }

  function init() {
    Array.prototype.forEach.call(document.querySelectorAll(".dp-prompt"), setup);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
