(() => {
  "use strict";

  let allArticles = [];
  let currentCategory = "all";
  let currentDate = new Date();
  let searchQuery = "";
  let showAllDates = true;

  const FAV_KEY = "ai-daily-favorites";
  let favUrls = new Set();

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ── 收藏（localStorage，存整篇，永不自动清理）──
  function getFavorites() {
    try {
      return JSON.parse(localStorage.getItem(FAV_KEY)) || [];
    } catch {
      return [];
    }
  }

  function refreshFav() {
    favUrls = new Set(getFavorites().map((a) => a.url));
  }

  function isFav(url) {
    return favUrls.has(url);
  }

  function toggleFav(url) {
    let favs = getFavorites();
    if (favUrls.has(url)) {
      favs = favs.filter((a) => a.url !== url);
    } else {
      const art = allArticles.find((a) => a.url === url);
      if (art) favs.push(art);
    }
    localStorage.setItem(FAV_KEY, JSON.stringify(favs));
    refreshFav();
    render();
  }

  // ── Init ──
  async function init() {
    try {
      const resp = await fetch("data/articles.json?t=" + Date.now(), {
        cache: "no-store",
      });
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
    refreshFav();
    bindEvents();
    render();
  }

  // ── Render ──
  function matchQuery(a) {
    const q = searchQuery.toLowerCase();
    return (
      a.title.toLowerCase().includes(q) ||
      (a.titleCn || "").toLowerCase().includes(q) ||
      a.source.toLowerCase().includes(q) ||
      a.category.toLowerCase().includes(q)
    );
  }

  function render() {
    const favMode = currentCategory === "favorites";
    const grouped = favMode || showAllDates || !!searchQuery;

    $(".date-nav").style.display = favMode ? "none" : "";
    if (!favMode) {
      $("#current-date").textContent = showAllDates
        ? "全部日期"
        : formatDateDisplay(currentDate);
      $("#toggle-all").classList.toggle("active", showAllDates);
      $("#toggle-all").textContent = showAllDates ? "单日浏览" : "查看全部";
    }

    let filtered;
    if (favMode) {
      filtered = getFavorites();
    } else if (searchQuery) {
      filtered = allArticles.filter(matchQuery);
    } else if (showAllDates) {
      filtered = allArticles.slice();
    } else {
      const dateStr = formatDate(currentDate);
      filtered = allArticles.filter((a) => a.date === dateStr);
    }

    if (favMode && searchQuery) {
      filtered = filtered.filter(matchQuery);
    }

    if (!favMode && currentCategory !== "all") {
      filtered = filtered.filter((a) => a.category === currentCategory);
    }

    filtered.sort((a, b) => {
      if (a.date !== b.date) return b.date.localeCompare(a.date);
      return (b.score || 0) - (a.score || 0);
    });

    const container = $("#articles");
    const empty = $("#empty-state");
    const stats = $("#stats");

    if (filtered.length === 0) {
      container.innerHTML = "";
      empty.style.display = "block";
      empty.innerHTML = favMode
        ? `<div class="empty-icon">☆</div><p>还没有收藏</p><p class="empty-hint">点任意资讯右侧的星标即可收藏</p>`
        : `<div class="empty-icon">📭</div><p>当日暂无符合条件的资讯</p><p class="empty-hint">试试切换日期或分类</p>`;
      stats.textContent = "";
    } else {
      empty.style.display = "none";
      const days = new Set(filtered.map((a) => a.date)).size;
      stats.textContent = grouped
        ? `共 ${filtered.length} 篇资讯 · ${days} 天`
        : `共 ${filtered.length} 篇资讯`;
      container.innerHTML = grouped
        ? renderGrouped(filtered)
        : filtered.map(renderCard).join("");
    }
  }

  function renderGrouped(articles) {
    let html = "";
    let lastDate = null;
    for (const a of articles) {
      if (a.date !== lastDate) {
        html += `<div class="date-group-header">${formatDateDisplay(parseDate(a.date))}</div>`;
        lastDate = a.date;
      }
      html += renderCard(a);
    }
    return html;
  }

  function renderCard(article) {
    const scoreClass =
      article.score >= 10 ? "s10" : article.score >= 9 ? "s9" : "";
    const hasSummary =
      article.category === "论文" || article.category === "技术博客";
    const sid = hasSummary ? summaryId(article.url) : "";
    return `
      <div class="article-card">
        <div class="article-score ${scoreClass}">${article.score || "-"}</div>
        <a class="article-main" href="${escapeAttr(article.url)}" target="_blank" rel="noopener noreferrer">
          <div class="article-info">
            <div class="article-title">${escapeHtml(article.title)}</div>
            ${article.titleCn ? `<div class="article-title-cn">${escapeHtml(article.titleCn)}</div>` : ""}
            <div class="article-meta">
              <span class="source-tag" data-cat="${escapeAttr(article.category)}">${escapeHtml(article.source)}</span>
              <span>${escapeHtml(article.category)}</span>
            </div>
          </div>
          <svg class="article-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m9 18 6-6-6-6"/>
          </svg>
        </a>
        ${hasSummary ? `<button class="summary-btn" data-id="${escapeAttr(sid)}" data-title="${escapeAttr(article.title)}">📄 中文摘要</button>` : ""}
        <button class="fav-btn ${isFav(article.url) ? "on" : ""}" data-url="${escapeAttr(article.url)}" title="${isFav(article.url) ? "取消收藏" : "收藏"}">${isFav(article.url) ? "★" : "☆"}</button>
      </div>`;
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
      showAllDates = false;
      currentDate.setDate(currentDate.getDate() - 1);
      render();
    });

    $("#next-date").addEventListener("click", () => {
      showAllDates = false;
      const today = new Date();
      const next = new Date(currentDate);
      next.setDate(next.getDate() + 1);
      if (next <= today) {
        currentDate = next;
        render();
      }
    });

    $("#toggle-all").addEventListener("click", () => {
      showAllDates = !showAllDates;
      render();
    });

    const datePicker = $("#date-picker");
    $("#pick-date").addEventListener("click", () => {
      datePicker.value = formatDate(currentDate);
      datePicker.showPicker();
    });
    datePicker.addEventListener("change", (e) => {
      if (e.target.value) {
        showAllDates = false;
        currentDate = parseDate(e.target.value);
        render();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT") return;
      if (e.key === "ArrowLeft") $("#prev-date").click();
      if (e.key === "ArrowRight") $("#next-date").click();
      if (e.key === "Escape") closeReader();
    });

    // 卡片操作：摘要 / 收藏
    $("#articles").addEventListener("click", (e) => {
      const fav = e.target.closest(".fav-btn");
      if (fav) {
        e.preventDefault();
        toggleFav(fav.dataset.url);
        return;
      }
      const btn = e.target.closest(".summary-btn");
      if (!btn) return;
      e.preventDefault();
      openSummary(btn.dataset.id, btn.dataset.title);
    });

    $(".reader-close").addEventListener("click", closeReader);
    $(".reader-backdrop").addEventListener("click", closeReader);
  }

  // ── 论文摘要阅读器 ──
  function summaryId(url) {
    const m = url.match(/(\d{4}\.\d{4,5})/);
    if (m) return m[1];
    const seg = url
      .replace(/[#?].*$/, "")
      .replace(/\/+$/, "")
      .split("/")
      .pop();
    return (seg || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80);
  }

  async function openSummary(id, title) {
    const modal = $("#reader-modal");
    const content = $("#reader-content");
    modal.style.display = "block";
    document.body.style.overflow = "hidden";
    content.innerHTML = `
      <div class="reader-loading">
        <div class="spinner"></div>
        <p>正在读取摘要...</p>
      </div>`;

    try {
      const resp = await fetch(`data/summaries/${id}.json?t=` + Date.now(), {
        cache: "no-store",
      });
      if (!resp.ok) throw new Error("not found");
      const data = await resp.json();
      content.innerHTML = renderReader(data, title);
    } catch {
      content.innerHTML = `
        <div class="reader-empty">
          <div class="empty-icon">🕐</div>
          <p>摘要生成中，请稍后刷新查看</p>
          <p class="empty-hint">新内容的中文摘要由后台自动生成，通常在收录后一小时内就绪</p>
        </div>`;
    }
  }

  function renderReader(data, fallbackTitle) {
    const sections = (data.sections || [])
      .map(
        (s) => `
        <section class="reader-section">
          <h3>${escapeHtml(s.heading || "")}</h3>
          <p>${escapeHtml(s.summary || "")}</p>
        </section>`
      )
      .join("");
    const meta = [data.source, data.date, data.hasFullText ? "基于全文" : "基于标题"]
      .filter(Boolean)
      .join(" · ");
    return `
      <article class="reader-doc">
        <div class="reader-head">
          <h2>${escapeHtml(data.titleCn || fallbackTitle || "")}</h2>
          <p class="reader-en">${escapeHtml(data.title || fallbackTitle || "")}</p>
          <p class="reader-meta">${escapeHtml(meta)}</p>
          ${data.url ? `<a class="reader-origin" href="${escapeAttr(data.url)}" target="_blank" rel="noopener noreferrer">查看原文 →</a>` : ""}
        </div>
        ${data.overview ? `<div class="reader-overview"><h3>概述</h3><p>${escapeHtml(data.overview)}</p></div>` : ""}
        ${sections}
      </article>`;
  }

  function closeReader() {
    const modal = $("#reader-modal");
    if (modal) modal.style.display = "none";
    document.body.style.overflow = "";
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
