/**
 * site-header.js — Theme toggle + search dropdown for the recommender.
 * Adapted from ForeverHYX/Homepage site-header.js (vanilla JS, no deps).
 * Load with `<script ... defer>`.
 */
(function () {
  "use strict";

  function init() {
    initThemeToggle();
    initSearch();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { passive: true });
  } else {
    init();
  }

  /* --- Theme toggle (mirrors Homepage) --- */
  function initThemeToggle() {
    var themeToggle = document.getElementById("themeToggle");
    var moonIcon = document.querySelector(".theme-icon-moon");
    var sunIcon = document.querySelector(".theme-icon-sun");

    function currentTheme() {
      return document.documentElement.getAttribute("data-theme") === "dark"
        ? "dark"
        : "light";
    }

    function syncIcon() {
      var isDark = currentTheme() === "dark";
      if (moonIcon) moonIcon.style.display = isDark ? "none" : "";
      if (sunIcon) sunIcon.style.display = isDark ? "" : "none";
    }

    syncIcon();

    if (typeof MutationObserver !== "undefined") {
      var observer = new MutationObserver(syncIcon);
      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"],
      });
    }

    if (!themeToggle) return;
    themeToggle.addEventListener("click", function () {
      var nextTheme = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", nextTheme);
      document.documentElement.style.colorScheme = nextTheme;
      try {
        localStorage.setItem("theme", nextTheme);
      } catch (e) {
        /* ignore */
      }
      syncIcon();
    });
  }

  /* --- Search dropdown --- */
  function initSearch() {
    var navCluster = document.getElementById("navCluster");
    var navIsland = document.getElementById("navIsland");
    var searchTrigger = document.getElementById("searchTrigger");
    var searchCloseBtn = document.getElementById("searchCloseBtn");
    var inlineSearchInput = document.getElementById("inlineSearchInput");

    if (
      !navCluster ||
      !navIsland ||
      !searchTrigger ||
      !searchCloseBtn ||
      !inlineSearchInput
    ) {
      return;
    }

    var state = {
      searchOpen: false,
      query: "",
      searchIndex: null,
      searchIndexLoading: false,
    };

    var dropdownEl = null;
    var dropdownResultsEl = null;
    var dropdownCleanup = null;

    function createDropdownNode() {
      var dd = document.createElement("div");
      dd.id = "searchDropdown";
      dd.className = "search-dropdown";
      dd.style.position = "fixed";
      dd.style.zIndex = "9999";

      var results = document.createElement("div");
      results.id = "inlineSearchResults";
      results.style.padding = "8px 0";
      dd.appendChild(results);

      return { dd: dd, results: results };
    }

    function startDropdownTracking(dropdown, input) {
      var cancelled = false;

      function positionDropdown() {
        if (cancelled || !dropdown || !input) return;
        var rect = input.getBoundingClientRect();
        if (rect.width > 100) {
          dropdown.style.left = rect.left + "px";
          dropdown.style.top = rect.bottom + 8 + "px";
          dropdown.style.width = rect.width + "px";
        }
      }

      var intervalId = window.setInterval(function () {
        if (cancelled || !input) return;
        var rect = input.getBoundingClientRect();
        if (rect.width > 100) {
          dropdown.style.left = rect.left + "px";
          dropdown.style.top = rect.bottom + 8 + "px";
          dropdown.style.width = rect.width + "px";
          window.clearInterval(intervalId);
        }
      }, 50);

      var timeoutId = window.setTimeout(function () {
        window.clearInterval(intervalId);
        positionDropdown();
      }, 500);

      window.addEventListener("resize", positionDropdown, { passive: true });
      window.addEventListener("scroll", positionDropdown, {
        passive: true,
        capture: true,
      });

      return function cleanup() {
        cancelled = true;
        window.clearInterval(intervalId);
        window.clearTimeout(timeoutId);
        window.removeEventListener("resize", positionDropdown);
        window.removeEventListener("scroll", positionDropdown, true);
      };
    }

    function openDropdown() {
      if (dropdownEl) return;
      var built = createDropdownNode();
      dropdownEl = built.dd;
      dropdownResultsEl = built.results;
      document.body.appendChild(dropdownEl);
      dropdownCleanup = startDropdownTracking(dropdownEl, inlineSearchInput);
      renderResults();
    }

    function closeDropdown() {
      if (dropdownCleanup) {
        dropdownCleanup();
        dropdownCleanup = null;
      }
      if (dropdownEl && dropdownEl.parentNode) {
        dropdownEl.parentNode.removeChild(dropdownEl);
      }
      dropdownEl = null;
      dropdownResultsEl = null;
    }

    function renderResults() {
      if (!dropdownResultsEl) return;

      while (dropdownResultsEl.firstChild) {
        dropdownResultsEl.removeChild(dropdownResultsEl.firstChild);
      }

      var normalized = state.query.trim().toLowerCase();
      if (!normalized) {
        dropdownEl.classList.remove("has-results");
        return;
      }
      dropdownEl.classList.add("has-results");

      var hits = computeHits(normalized);
      if (hits.length === 0) {
        var empty = document.createElement("div");
        empty.style.padding = "14px";
        empty.style.textAlign = "center";
        empty.style.color = "var(--muted)";
        empty.style.fontSize = "14px";
        empty.textContent = "没有匹配的论文或仓库。";
        dropdownResultsEl.appendChild(empty);
        return;
      }

      for (var i = 0; i < hits.length && i < 12; i++) {
        var hit = hits[i];
        var anchor = document.createElement("a");
        anchor.href = hit.url;
        var title = document.createElement("div");
        title.className = "search-result-title";
        var chip = document.createElement("span");
        chip.className = "search-result-chip";
        chip.textContent = hit.type;
        title.appendChild(chip);
        title.appendChild(document.createTextNode(hit.title));
        anchor.appendChild(title);
        anchor.addEventListener("click", resetSearchState, { passive: true });
        dropdownResultsEl.appendChild(anchor);
      }
    }

    function computeHits(normalized) {
      if (!state.searchIndex) return [];
      var out = [];
      for (var i = 0; i < state.searchIndex.length; i++) {
        var item = state.searchIndex[i];
        var keywords = item.keywords || [];
        var kwHit = false;
        for (var k = 0; k < keywords.length; k++) {
          if (
            keywords[k] &&
            String(keywords[k]).toLowerCase().indexOf(normalized) !== -1
          ) {
            kwHit = true;
            break;
          }
        }
        if (
          (item.title &&
            String(item.title).toLowerCase().indexOf(normalized) !== -1) ||
          (item.desc &&
            String(item.desc).toLowerCase().indexOf(normalized) !== -1) ||
          kwHit
        ) {
          out.push(item);
        }
      }
      return out;
    }

    function ensureSearchIndex() {
      if (state.searchIndex || state.searchIndexLoading) return;
      state.searchIndexLoading = true;
      fetch("recommendations.json", { cache: "no-store" })
        .then(function (response) {
          if (!response.ok) throw new Error("recommendations.json failed");
          return response.json();
        })
        .then(function (data) {
          var recs = Array.isArray(data.recommendations) ? data.recommendations : [];
          state.searchIndex = recs.map(function (r) {
            var isRepo = String(r.item_type || "").toLowerCase() === "repository";
            return {
              title: r.title || r.paper_id || "",
              desc: r.tldr || r.abstract || "",
              type: isRepo ? "仓库" : "论文",
              url:
                "index.html?paper_id=" +
                encodeURIComponent(String(r.paper_id || "")),
              keywords: Array.from(
                new Set(
                  []
                    .concat(r.categories || [])
                    .concat(r.repository_topics || [])
                    .concat(isRepo ? [r.repository_language] : [])
                    .concat(r.sections || [])
                    .concat(r.authors || [])
                    .concat(r.affiliations || [])
                    .filter(Boolean)
                )
              ),
            };
          });
          renderResults();
        })
        .catch(function () {
          state.searchIndex = [];
          renderResults();
        })
        .finally(function () {
          state.searchIndexLoading = false;
        });
    }

    function setSearchOpen(open) {
      state.searchOpen = open;
      searchTrigger.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        navIsland.classList.add("search-mode");
        openDropdown();
        ensureSearchIndex();
        window.setTimeout(function () {
          if (state.searchOpen) inlineSearchInput.focus();
        }, 100);
      } else {
        navIsland.classList.remove("search-mode");
        closeDropdown();
        state.query = "";
        if (inlineSearchInput.value !== "") inlineSearchInput.value = "";
      }
    }

    function closeSearch() {
      if (state.searchOpen) setSearchOpen(false);
    }

    function resetSearchState() {
      closeSearch();
    }

    searchTrigger.addEventListener("click", function () {
      setSearchOpen(true);
    });

    searchCloseBtn.addEventListener("click", closeSearch);

    inlineSearchInput.addEventListener("input", function (event) {
      state.query = event.target.value;
      renderResults();
    });

    document.addEventListener("click", function (event) {
      if (!navCluster || navCluster.contains(event.target)) return;
      if (state.searchOpen) closeSearch();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      if (state.searchOpen) {
        event.preventDefault();
        closeSearch();
      }
    });
  }
})();
