(() => {
  "use strict";

  let allArticles = [];
  let currentCategory = "all";
  let currentDate = new Date();
  let searchQuery = "";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ── Init ──
  async function init() {
    try {
      const resp = await fetch("data/articles.json");
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();
      allArticles = data.articles || [];

      if (data.lastUpdated) {
        $("#last-updated").textContent =
          "最后更新：" + new Date(data.lastUpdated).toLocaleString("zh-CN");
      }

      if (allArticles.length > 0) {
        currentDate = parseDate(allArticles[0].date);
      }
    } catch {
      allArticles = [];
    }

    $("#loading").style.display = "none";
    bindEvents();
    render();
  }

  // ── Render ──
  function render() {
    const dateStr = formatDate(currentDate);
    $("#current-date").textContent = formatDateDisplay(currentDate);

    let filtered = allArticles.filter((a) => a.date === dateStr);

    if (currentCategory !== "all") {
      filtered = filtered.filter((a) => a.category === currentCategory);
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (a) =>
          a.title.toLowerCase().includes(q) ||
          a.source.toLowerCase().includes(q)
      );
    }

    filtered.sort((a, b) => (b.score || 0) - (a.score || 0));

    const container = $("#articles");
    const empty = $("#empty-state");
    const stats = $("#stats");

    if (filtered.length === 0) {
      container.innerHTML = "";
      empty.style.display = "block";
      stats.textContent = "";
    } else {
      empty.style.display = "none";
      stats.textContent = `共 ${filtered.length} 篇资讯`;
      container.innerHTML = filtered.map(renderCard).join("");
    }
  }

  function renderCard(article) {
    const scoreClass =
      article.score >= 10 ? "s10" : article.score >= 9 ? "s9" : "";
    return `
      <a class="article-card" href="${escapeAttr(article.url)}" target="_blank" rel="noopener noreferrer">
        <div class="article-score ${scoreClass}">${article.score || "-"}</div>
        <div class="article-info">
          <div class="article-title">${escapeHtml(article.title)}</div>
          <div class="article-meta">
            <span class="source-tag" data-cat="${escapeAttr(article.category)}">${escapeHtml(article.source)}</span>
            <span>${escapeHtml(article.category)}</span>
          </div>
        </div>
        <svg class="article-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="m9 18 6-6-6-6"/>
        </svg>
      </a>`;
  }

  // ── Events ──
  function bindEvents() {
    $$(".cat-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        $(".cat-btn.active").classList.remove("active");
        btn.classList.add("active");
        currentCategory = btn.dataset.category;
        render();
      });
    });

    let debounceTimer;
    $("#search").addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        searchQuery = e.target.value.trim();
        render();
      }, 200);
    });

    $("#prev-date").addEventListener("click", () => {
      currentDate.setDate(currentDate.getDate() - 1);
      render();
    });

    $("#next-date").addEventListener("click", () => {
      const today = new Date();
      const next = new Date(currentDate);
      next.setDate(next.getDate() + 1);
      if (next <= today) {
        currentDate = next;
        render();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT") return;
      if (e.key === "ArrowLeft") $("#prev-date").click();
      if (e.key === "ArrowRight") $("#next-date").click();
    });
  }

  // ── Helpers ──
  function formatDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function formatDateDisplay(d) {
    const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
    const m = d.getMonth() + 1;
    const day = d.getDate();
    const w = weekdays[d.getDay()];
    return `${m}月${day}日 周${w}`;
  }

  function parseDate(str) {
    const [y, m, d] = str.split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  function escapeHtml(text) {
    const el = document.createElement("span");
    el.textContent = text;
    return el.innerHTML;
  }

  function escapeAttr(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // ── Go ──
  init();
})();
