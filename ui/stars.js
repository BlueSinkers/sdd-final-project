// Quiet warp of the Fiodos sky. Drawn on a canvas so the page stays free of
// inline styles. Skipped when the visitor asks for less motion.
(function () {
  var canvas = document.getElementById("sky");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  if (!ctx) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    paintStill();
    return;
  }

  var width = 0;
  var height = 0;
  var stars = [];
  var colors = ["rgba(210,213,221,", "rgba(174,184,204,", "rgba(122,127,137,"];

  function makeStar() {
    return {
      x: (Math.random() * 2 - 1) * width,
      y: (Math.random() * 2 - 1) * height,
      z: Math.random() * width,
      tw: 0.45 + Math.random() * 0.55,
      c: colors[Math.floor(Math.random() * colors.length)],
    };
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = canvas.clientWidth || window.innerWidth;
    height = canvas.clientHeight || window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = [];
    var count = Math.min(280, Math.floor((width * height) / 9000));
    for (var i = 0; i < count; i += 1) stars.push(makeStar());
  }

  function frame() {
    requestAnimationFrame(frame);
    ctx.clearRect(0, 0, width, height);
    var cx = width / 2;
    var cy = height / 2;
    for (var i = 0; i < stars.length; i += 1) {
      var star = stars[i];
      star.z -= 0.7;
      if (star.z < 1) {
        var next = makeStar();
        next.z = width;
        stars[i] = next;
        star = next;
      }
      var near = 128 / star.z;
      var x = cx + star.x * near;
      var y = cy + star.y * near;
      if (x < 0 || x > width || y < 0 || y > height) continue;
      var far = 128 / (star.z + 3);
      ctx.globalAlpha = Math.min(1, (1 - star.z / width) * 0.9) * star.tw;
      ctx.strokeStyle = star.c + "1)";
      ctx.lineWidth = Math.max(0.4, (1 - star.z / width) * 1.6);
      ctx.beginPath();
      ctx.moveTo(cx + star.x * far, cy + star.y * far);
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function paintStill() {
    resize();
    ctx.fillStyle = "#d2d5dd";
    for (var i = 0; i < stars.length; i += 1) {
      var star = stars[i];
      var k = 128 / Math.max(star.z, 1);
      ctx.globalAlpha = 0.35 * star.tw;
      ctx.fillRect(width / 2 + star.x * k, height / 2 + star.y * k, 1.2, 1.2);
    }
    ctx.globalAlpha = 1;
  }

  resize();
  window.addEventListener("resize", resize);
  frame();
})();
