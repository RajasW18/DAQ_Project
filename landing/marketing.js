/* ── ForgeLab Landing — Interactive Features ── */

(function () {
  "use strict";

  /* ── Theme ── */
  const root = document.documentElement;
  const saved = localStorage.getItem("forgelab-landing-theme");
  if (saved) {
    root.dataset.theme = saved;
  } else if (window.matchMedia("(prefers-color-scheme: light)").matches) {
    root.dataset.theme = "light";
  }

  const themeBtn = document.querySelector("[data-theme-toggle]");
  themeBtn?.addEventListener("click", () => {
    const next = root.dataset.theme === "light" ? "dark" : "light";
    root.dataset.theme = next;
    localStorage.setItem("forgelab-landing-theme", next);
  });

  /* ── Mobile menu ── */
  const menuBtn = document.querySelector("[data-menu-toggle]");
  const nav = document.querySelector(".site-nav");
  menuBtn?.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    menuBtn.setAttribute("aria-expanded", String(open));
    menuBtn.textContent = open ? "Close" : "Menu";
  });

  /* ── Sticky header shadow ── */
  const header = document.getElementById("site-header");
  const onHeaderScroll = () => {
    header?.classList.toggle("is-scrolled", window.scrollY > 10);
  };
  window.addEventListener("scroll", onHeaderScroll, { passive: true });
  onHeaderScroll();

  /* ── Scroll progress bar ── */
  const progressBar = document.querySelector("[data-scroll-progress]");
  const updateProgress = () => {
    const h = document.documentElement.scrollHeight - window.innerHeight;
    if (h > 0 && progressBar) {
      progressBar.style.width = ((window.scrollY / h) * 100).toFixed(1) + "%";
    }
  };
  window.addEventListener("scroll", updateProgress, { passive: true });
  updateProgress();

  /* ── Back to top ── */
  const backBtn = document.querySelector("[data-back-to-top]");
  const toggleBackToTop = () => {
    backBtn?.classList.toggle("is-visible", window.scrollY > window.innerHeight * 0.7);
  };
  window.addEventListener("scroll", toggleBackToTop, { passive: true });
  backBtn?.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

  /* ── Toast ── */
  const toast = document.querySelector("[data-toast]");
  let toastTimer;
  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2800);
  }

  /* ── Reveal on scroll ── */
  const reveals = document.querySelectorAll(".reveal");
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    reveals.forEach((el) => el.classList.add("is-visible"));
  } else {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14 }
    );
    reveals.forEach((el) => observer.observe(el));
  }

  /* ── Particle canvas ── */
  const canvas = document.getElementById("particle-canvas");
  if (canvas && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const ctx = canvas.getContext("2d");
    let particles = [];
    let mouseX = -1000;
    let mouseY = -1000;
    let animId;

    function resize() {
      const hero = canvas.parentElement;
      if (!hero) return;
      canvas.width = hero.offsetWidth;
      canvas.height = hero.offsetHeight;
    }

    function createParticles() {
      particles = [];
      const count = Math.min(80, Math.floor((canvas.width * canvas.height) / 12000));
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          r: Math.random() * 2 + 1,
        });
      }
    }

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const isDark = root.dataset.theme !== "light";
      const dotColor = isDark ? "rgba(0,201,106," : "rgba(0,155,77,";
      const lineColor = isDark ? "rgba(0,201,106," : "rgba(0,155,77,";

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // Mouse repulsion
        const dx = p.x - mouseX;
        const dy = p.y - mouseY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          const force = (120 - dist) / 120 * 0.8;
          p.vx += (dx / dist) * force;
          p.vy += (dy / dist) * force;
        }

        p.x += p.vx;
        p.y += p.vy;

        // Dampen velocity
        p.vx *= 0.99;
        p.vy *= 0.99;

        // Wrap around
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        // Draw particle
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = dotColor + (0.5 + p.r * 0.15) + ")";
        ctx.fill();

        // Draw connections
        for (let j = i + 1; j < particles.length; j++) {
          const q = particles[j];
          const cx = p.x - q.x;
          const cy = p.y - q.y;
          const cd = Math.sqrt(cx * cx + cy * cy);
          if (cd < 140) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = lineColor + (0.12 * (1 - cd / 140)) + ")";
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(draw);
    }

    canvas.parentElement?.addEventListener("mousemove", (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
    });
    canvas.parentElement?.addEventListener("mouseleave", () => {
      mouseX = -1000;
      mouseY = -1000;
    });

    window.addEventListener("resize", () => {
      resize();
      createParticles();
    });
    resize();
    createParticles();
    draw();

    // Pause animation when not visible
    const heroObserver = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (!animId) draw();
        } else {
          cancelAnimationFrame(animId);
          animId = null;
        }
      },
      { threshold: 0 }
    );
    heroObserver.observe(canvas.parentElement);
  }

  /* ── Copy to clipboard ── */
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.dataset.copy;
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = "Copied!";
        btn.classList.add("copied");
        showToast("Command copied to clipboard.");
      } catch {
        // Fallback
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.cssText = "position:fixed;opacity:0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
        btn.textContent = "Copied!";
        btn.classList.add("copied");
        showToast("Command copied to clipboard.");
      }
      setTimeout(() => {
        btn.textContent = "Copy";
        btn.classList.remove("copied");
      }, 2000);
    });
  });

  /* ── FAQ accordion ── */
  document.querySelectorAll(".faq-question").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".faq-item");
      const wasOpen = item.classList.contains("is-open");

      // Close all
      document.querySelectorAll(".faq-item.is-open").forEach((other) => {
        other.classList.remove("is-open");
        other.querySelector(".faq-question")?.setAttribute("aria-expanded", "false");
      });

      // Toggle current
      if (!wasOpen) {
        item.classList.add("is-open");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });

  /* ── Server health check ── */
  const badge = document.querySelector("[data-server-badge]");
  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8765" : "";
  let wasOnline = false;

  async function checkServer(manual = false) {
    if (!badge) return;
    if (manual) {
      badge.querySelector("span:not(.status-dot)").textContent = "Checking…";
    }
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${API_BASE}/api/status`, {
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (res.ok) {
        const data = await res.json();
        const count = data.files_count || (data.files ? data.files.length : 8);
        badge.className = "server-badge online";
        badge.title = `ForgeLab server online on port ${data.port || 8765}. Hardware: ${data.board?.name || "ATmega2560"}`;
        badge.querySelector("span:not(.status-dot)").textContent = `Server online · ${count} files`;
        if (!wasOnline) {
          showToast(`Backend connected · ForgeLab workspace live on :${data.port || 8765}`);
          wasOnline = true;
        }
      } else {
        setOffline(manual);
      }
    } catch {
      setOffline(manual);
    }
  }

  function setOffline(manual = false) {
    if (!badge) return;
    badge.className = "server-badge offline";
    badge.title = "Backend server offline. Run: .\\.venv\\Scripts\\python.exe forgelab_server.py (Click to retry)";
    badge.querySelector("span:not(.status-dot)").textContent = "Offline · Click to retry";
    if (wasOnline) {
      showToast("Backend connection lost. Trying to reconnect...");
      wasOnline = false;
    } else if (manual) {
      showToast("Backend unreachable at http://127.0.0.1:8765. Launch forgelab_server.py to connect.");
    }
  }

  badge?.addEventListener("click", () => checkServer(true));
  checkServer();
  // Poll periodically so it reconnects automatically
  setInterval(() => checkServer(false), 5000);

  /* ── Counter animation for signal band ── */
  const counterEls = document.querySelectorAll("[data-count-to]");
  if (counterEls.length && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const counterObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const el = entry.target;
            const target = parseInt(el.dataset.countTo, 10);
            let current = 0;
            const step = () => {
              current++;
              el.textContent = String(current).padStart(2, "0");
              if (current < target) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
            counterObserver.unobserve(el);
          }
        });
      },
      { threshold: 0.5 }
    );
    counterEls.forEach((el) => {
      el.textContent = "00";
      counterObserver.observe(el);
    });
  }
})();
