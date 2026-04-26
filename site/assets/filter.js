/* filter.js — 2 軸フィルタ (D-32 / D-35)
 *
 * 仕様: 03_style/STYLE_GUIDE.md §7
 * - フィルタ軸: トピック (4) × 重要度 (3)
 * - 軸間 AND、軸内 OR
 * - チップトグルで data-* 属性に基づき .card を表示/非表示
 * - 初期状態: 全チップ active = 全カード表示
 */
(function () {
  "use strict";

  const TOPIC_VALUES = ["ai_agents", "automation", "dx_cases", "other"];
  const IMPORTANCE_VALUES = ["high", "mid", "low"];

  const state = {
    topics: new Set(TOPIC_VALUES),
    importances: new Set(IMPORTANCE_VALUES),
  };

  function applyFilter() {
    const cards = document.querySelectorAll(".card[data-topic]");
    cards.forEach((card) => {
      const t = card.getAttribute("data-topic");
      const i = card.getAttribute("data-importance");
      const visible = state.topics.has(t) && state.importances.has(i);
      card.style.display = visible ? "" : "none";
    });
  }

  function toggleChip(button, axis, value) {
    const set = axis === "topic" ? state.topics : state.importances;
    if (set.has(value)) {
      set.delete(value);
      button.classList.remove("active");
    } else {
      set.add(value);
      button.classList.add("active");
    }
    applyFilter();
  }

  function clearAll() {
    TOPIC_VALUES.forEach((v) => state.topics.add(v));
    IMPORTANCE_VALUES.forEach((v) => state.importances.add(v));
    document.querySelectorAll(".filter-chip").forEach((c) => c.classList.add("active"));
    applyFilter();
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-filter-topic]").forEach((btn) => {
      btn.addEventListener("click", () => {
        toggleChip(btn, "topic", btn.getAttribute("data-filter-topic"));
      });
    });
    document.querySelectorAll("[data-filter-importance]").forEach((btn) => {
      btn.addEventListener("click", () => {
        toggleChip(btn, "importance", btn.getAttribute("data-filter-importance"));
      });
    });
    document.querySelectorAll(".filter-clear").forEach((btn) => {
      btn.addEventListener("click", clearAll);
    });
  });
})();
