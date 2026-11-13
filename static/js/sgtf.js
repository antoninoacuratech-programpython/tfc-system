/* SGTF — comportamento partilhado dos painéis (sem dependências). */
(function () {
  "use strict";

  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");

  // ---------- Menu lateral (mobile) ----------
  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-open", open);
    if (overlay) overlay.hidden = !open;
    document.body.style.overflow = open ? "hidden" : "";
  }
  document.querySelectorAll("[data-sidebar-open]").forEach((b) => b.addEventListener("click", () => setSidebar(true)));
  document.querySelectorAll("[data-sidebar-close]").forEach((b) => b.addEventListener("click", () => setSidebar(false)));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { setSidebar(false); closeDropdowns(); } });

  // ---------- Grupos do menu (submenus) ----------
  const STORAGE_KEY = "sgtf:menu-aberto";
  let abertos = [];
  try { abertos = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch (e) { abertos = []; }

  document.querySelectorAll("[data-nav-group]").forEach((group) => {
    const id = group.getAttribute("data-nav-group");
    const toggle = group.querySelector(":scope > [data-nav-toggle]");
    if (abertos.includes(id)) group.classList.add("is-open");
    toggle?.setAttribute("aria-expanded", group.classList.contains("is-open"));
    toggle?.addEventListener("click", () => {
      const open = group.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open);
      abertos = open ? [...new Set([...abertos, id])] : abertos.filter((x) => x !== id);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(abertos)); } catch (e) { /* ignorar */ }
    });
  });

  // ---------- Link activo ----------
  const path = window.location.pathname;
  let melhor = null;
  document.querySelectorAll("[data-nav] a.sgtf-nav-link[href]").forEach((a) => {
    const href = a.getAttribute("href");
    if (!href || href === "#" || href === "/") return;
    if (path === href || (path.startsWith(href) && href.length > 1)) {
      if (!melhor || href.length > melhor.getAttribute("href").length) melhor = a;
    }
  });
  if (melhor) {
    melhor.classList.add("is-active");
    melhor.setAttribute("aria-current", "page");
    const grupo = melhor.closest("[data-nav-group]");
    grupo?.classList.add("is-open");
  }

  // ---------- Dropdowns (notificações, utilizador) ----------
  function closeDropdowns(except) {
    document.querySelectorAll("[data-dropdown]").forEach((dd) => {
      if (dd === except) return;
      const menu = dd.querySelector("[data-dropdown-menu]");
      if (menu) menu.hidden = true;
      dd.querySelector("[data-dropdown-toggle]")?.setAttribute("aria-expanded", "false");
    });
  }
  document.querySelectorAll("[data-dropdown]").forEach((dd) => {
    const toggle = dd.querySelector("[data-dropdown-toggle]");
    const menu = dd.querySelector("[data-dropdown-menu]");
    toggle?.addEventListener("click", (e) => {
      e.stopPropagation();
      const abrir = menu.hidden;
      closeDropdowns(dd);
      menu.hidden = !abrir;
      toggle.setAttribute("aria-expanded", String(abrir));
    });
    menu?.addEventListener("click", (e) => e.stopPropagation());
  });
  document.addEventListener("click", () => closeDropdowns());

  // ---------- Alertas ----------
  document.querySelectorAll("[data-alert]").forEach((alerta) => {
    alerta.querySelector("[data-alert-close]")?.addEventListener("click", () => alerta.remove());
    if (alerta.classList.contains("sgtf-alert--success") || alerta.classList.contains("sgtf-alert--info")) {
      setTimeout(() => {
        alerta.style.transition = "opacity .4s";
        alerta.style.opacity = "0";
        setTimeout(() => alerta.remove(), 400);
      }, 6000);
    }
  });

  // ---------- Selects exclusivos (ex.: mesa de júri) ----------
  // Uso: <select data-exclusivo="juri">...</select> em vários campos do mesmo grupo.
  // Um valor escolhido num campo desaparece das opções dos restantes campos do grupo.
  // Valores extra a excluir de todo o grupo: <input type="hidden" data-exclusivo-extra="juri" value="ID">
  function atualizarExclusivos() {
    const grupos = {};
    document.querySelectorAll("select[data-exclusivo]").forEach((s) => {
      (grupos[s.dataset.exclusivo] ||= []).push(s);
    });
    Object.entries(grupos).forEach(([grupo, selects]) => {
      const extras = [...document.querySelectorAll(`[data-exclusivo-extra="${grupo}"]`)]
        .map((el) => el.value).filter(Boolean);
      selects.forEach((select) => {
        const usadosNosOutros = new Set(
          selects.filter((o) => o !== select && o.value).map((o) => o.value).concat(extras)
        );
        [...select.options].forEach((opt) => {
          if (!opt.value) return; // placeholder
          const bloquear = usadosNosOutros.has(opt.value);
          opt.hidden = bloquear;
          opt.disabled = bloquear;
        });
        // Se o valor actual ficou bloqueado (ex.: orientador escolhido depois), limpa o campo.
        if (select.value && usadosNosOutros.has(select.value) && [...select.options].some((o) => !o.value)) {
          select.value = "";
          select.dispatchEvent(new Event("change", { bubbles: true }));
        }
      });
    });
  }
  document.addEventListener("change", (e) => {
    if (e.target.matches("select[data-exclusivo], [data-exclusivo-extra]")) atualizarExclusivos();
  });
  atualizarExclusivos();
  window.SGTF = Object.assign(window.SGTF || {}, { atualizarExclusivos });

  // ---------- Confirmação de acções destrutivas ----------
  // Uso: <a href="..." data-confirm="Eliminar este registo?">  ou  <form data-confirm="...">
  document.addEventListener("click", (e) => {
    const el = e.target.closest("a[data-confirm], button[data-confirm]");
    if (el && !window.confirm(el.getAttribute("data-confirm"))) { e.preventDefault(); e.stopPropagation(); }
  });
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form.matches("form[data-confirm]") && !window.confirm(form.getAttribute("data-confirm"))) { e.preventDefault(); return; }
    // Evita submissões duplicadas.
    const btn = form.querySelector('[type="submit"]:not([data-no-lock])');
    if (btn && !e.defaultPrevented) {
      setTimeout(() => { btn.disabled = true; btn.classList.add("opacity-70", "cursor-wait"); }, 0);
      // Reactiva caso a resposta seja um download (a página não muda).
      setTimeout(() => { btn.disabled = false; btn.classList.remove("opacity-70", "cursor-wait"); }, 8000);
    }
  });
})();
