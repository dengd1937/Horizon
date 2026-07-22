"""Dependency-free progressive enhancement for the research-paper index."""

PAPER_INDEX_JS = r"""(() => {
  "use strict";

  const root = document.querySelector("[data-paper-library]");
  if (!root) return;

  const controls = root.querySelector("[data-paper-filter]");
  const search = root.querySelector("[data-paper-search]");
  const reset = root.querySelector("[data-paper-reset]");
  const results = root.querySelector("[data-paper-results]");
  const empty = root.querySelector("[data-paper-empty]");
  const list = root.querySelector("[data-paper-list]");
  const entries = Array.from(root.querySelectorAll("[data-paper-entry]"));
  const tagButtons = Array.from(root.querySelectorAll("[data-paper-tag]"));

  if (!controls || !search || !reset || !results || !empty || !list || !entries.length) {
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
    return {
      entry,
      tags,
      searchable: normalize(entry.dataset.search || ""),
    };
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

    records.forEach((record) => {
      const matchesSearch = tokens.every((token) => record.searchable.includes(token));
      const matchesTag = !selectedTag || record.tags.includes(selectedTag);
      const matches = matchesSearch && matchesTag;
      record.entry.hidden = !matches;
      if (matches) visible += 1;
    });

    const active = tokens.length > 0 || selectedTag !== "";
    results.textContent = active ? `找到 ${visible} 篇论文` : `共 ${visible} 篇论文`;
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
