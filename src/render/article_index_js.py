"""Dependency-free progressive enhancement for the curated article index."""

ARTICLE_INDEX_JS = r"""(() => {
  "use strict";

  const root = document.querySelector("[data-article-library]");
  if (!root) return;

  const controls = root.querySelector("[data-article-filter]");
  const search = root.querySelector("[data-article-search]");
  const reset = root.querySelector("[data-article-reset]");
  const results = root.querySelector("[data-article-results]");
  const empty = root.querySelector("[data-article-empty]");
  const groups = Array.from(root.querySelectorAll("[data-article-group]"));
  const entries = Array.from(root.querySelectorAll("[data-article-entry]"));
  const tagButtons = Array.from(root.querySelectorAll("[data-article-tag]"));

  if (!controls || !search || !reset || !results || !empty || !entries.length) {
    return;
  }

  const normalize = (value) => {
    const text = String(value ?? "");
    const normalized = typeof text.normalize === "function" ? text.normalize("NFKC") : text;
    return normalized.toLocaleLowerCase("zh-CN");
  };

  const records = entries.map((entry) => {
    let tags = [];
    try {
      const parsed = JSON.parse(entry.dataset.tags || "[]");
      if (Array.isArray(parsed)) tags = parsed.map(String);
    } catch (_error) {
      tags = [];
    }

    const searchable = [".ttl", ".sum", ".meta"]
      .map((selector) => entry.querySelector(selector)?.textContent || "")
      .join(" ");
    return { entry, tags, searchable: normalize(searchable) };
  });

  let selectedTag = "";

  const updatePressedTag = () => {
    tagButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String((button.dataset.tag || "") === selectedTag));
    });
  };

  const applyFilters = () => {
    const tokens = normalize(search.value).trim().split(/\s+/u).filter(Boolean);
    let visible = 0;

    records.forEach(({ entry, tags, searchable }) => {
      const matchesSearch = tokens.every((token) => searchable.includes(token));
      const matchesTag = !selectedTag || tags.includes(selectedTag);
      const matches = matchesSearch && matchesTag;
      entry.hidden = !matches;
      if (matches) visible += 1;
    });

    groups.forEach((group) => {
      group.hidden = !group.querySelector("[data-article-entry]:not([hidden])");
    });

    const active = tokens.length > 0 || selectedTag !== "";
    results.textContent = active ? `找到 ${visible} 篇文章` : `共 ${visible} 篇文章`;
    empty.hidden = visible !== 0;
    reset.hidden = !active;
  };

  search.addEventListener("input", applyFilters);
  tagButtons.forEach((button) => {
    button.addEventListener("click", () => {
      selectedTag = button.dataset.tag || "";
      updatePressedTag();
      applyFilters();
    });
  });
  reset.addEventListener("click", () => {
    search.value = "";
    selectedTag = "";
    updatePressedTag();
    applyFilters();
    search.focus();
  });

  controls.hidden = false;
  updatePressedTag();
  applyFilters();
})();
"""
