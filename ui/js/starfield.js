// Ambient animated starfield background. Purely decorative and
// self-contained - no other module touches the canvas.
import { el } from "./dom.js";

export function initStarfield() {
  const canvas = el("starfield");
  const ctx = canvas.getContext("2d");
  let stars = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const count = Math.floor((canvas.width * canvas.height) / 9000);
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.2 + 0.2,
      tw: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.15 + 0.02,
    }));
  }

  function draw(t) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const s of stars) {
      const alpha = 0.35 + 0.65 * Math.abs(Math.sin(s.tw + t * 0.001 * s.speed));
      ctx.beginPath();
      ctx.fillStyle = `rgba(232,232,245,${alpha.toFixed(2)})`;
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(draw);
}
