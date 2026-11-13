(function () {
  "use strict";

  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");

  // menu lateral no telemóvel
  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-open", open);
    if (overlay) overlay.hidden = !open;
    document.body.style.overflow = open ? "hidden" : "";
  }
  document.querySelectorAll("[data-sidebar-open]").forEach((b) => b.addEventListener("click", () => setSidebar(true)));
  document.querySelectorAll("[data-sidebar-close]").forEach((b) => b.addEventListener("click", () => setSidebar(false)));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { setSidebar(false); closeDropdowns(); } });

  // lembra que grupos do menu ficaram abertos
  const STORAGE_KEY = "sgtf:menu-aberto";
  let abertos = [];
  try { abertos = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch (e) { abertos = []; }

  document.querySelectorAll("[data-nav-group]").forEach((group) => {
    const id = group.getAttribute("data-nav-group");
    const toggle = group.querySelector(":scope > [data-nav-toggle]");
    if (abertos.includes(id)) group.classList.add("is-open");
    toggle?.setAttribute("aria-expanded", group.classList.contains("is-open"));
    toggle?.addEventListener("click", () => {
      const emRail = window.matchMedia("(min-width: 768px) and (max-width: 1279px)").matches;
      if (emRail && !sidebar.classList.contains("is-open")) {
        group.classList.add("is-open");
        toggle.setAttribute("aria-expanded", "true");
        setSidebar(true);
        return;
      }
      const open = group.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open);
      abertos = open ? [...new Set([...abertos, id])] : abertos.filter((x) => x !== id);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(abertos)); } catch (e) { /* ignorar */ }
    });
  });

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
    grupo?.classList.add("is-open", "has-active");
  }

  let melhorInferior = null;
  document.querySelectorAll("[data-bottom-nav] a.sgtf-bnav-item[href]").forEach((a) => {
    const href = a.getAttribute("href");
    if (path === href || (href.length > 1 && path.startsWith(href))) {
      if (!melhorInferior || href.length > melhorInferior.getAttribute("href").length) melhorInferior = a;
    }
  });
  if (melhorInferior) {
    melhorInferior.classList.add("is-active");
    melhorInferior.setAttribute("aria-current", "page");
  }

  window.matchMedia("(min-width: 1280px)").addEventListener("change", (e) => { if (e.matches) setSidebar(false); });

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

  // no telemóvel as tabelas passam a cartões; o CSS usa o data-label como título
  function prepararTabelas(raiz) {
    (raiz || document).querySelectorAll(".sgtf-content table:not([data-sem-cartoes])").forEach((tabela) => {
      const titulos = [...tabela.querySelectorAll("thead th")].map((th) => th.textContent.replace(/\s+/g, " ").trim());
      if (!titulos.length) {
        if (!tabela.parentElement.classList.contains("sgtf-table-wrap") && !tabela.closest(".overflow-x-auto")) {
          const wrap = document.createElement("div");
          wrap.className = "sgtf-table-wrap";
          tabela.parentNode.insertBefore(wrap, tabela);
          wrap.appendChild(tabela);
        }
        return;
      }
      tabela.classList.add("sgtf-rtable");
      tabela.querySelectorAll("tbody tr").forEach((tr) => {
        let col = 0;
        [...tr.children].forEach((td) => {
          if (!td.hasAttribute("data-label")) td.setAttribute("data-label", td.hasAttribute("colspan") ? "" : (titulos[col] || ""));
          col += parseInt(td.getAttribute("colspan") || "1", 10);
        });
      });
    });
  }
  prepararTabelas();
  const conteudo = document.querySelector(".sgtf-content");
  if (conteudo && "MutationObserver" in window) {
    let pendente = false;
    new MutationObserver(() => {
      if (pendente) return;
      pendente = true;
      requestAnimationFrame(() => { pendente = false; prepararTabelas(); });
    }).observe(conteudo, { childList: true, subtree: true });
  }

  document.addEventListener("pointerdown", (e) => {
    const alvo = e.target.closest(".sgtf-btn, .sgtf-nav-link, .sgtf-bnav-item, .sgtf-auth-btn, .sgtf-dropdown__item");
    if (!alvo) return;
    alvo.classList.add("sgtf-ripple-host");
    const r = alvo.getBoundingClientRect();
    const d = Math.max(r.width, r.height);
    const onda = document.createElement("span");
    onda.className = "sgtf-ripple";
    onda.style.cssText = `width:${d}px;height:${d}px;left:${e.clientX - r.left - d / 2}px;top:${e.clientY - r.top - d / 2}px`;
    alvo.appendChild(onda);
    setTimeout(() => onda.remove(), 550);
  });

  // júri da pré-defesa: um professor escolhido num campo sai das opções dos outros
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

  document.addEventListener("click", (e) => {
    const el = e.target.closest("a[data-confirm], button[data-confirm]");
    if (el && !window.confirm(el.getAttribute("data-confirm"))) { e.preventDefault(); e.stopPropagation(); }
  });
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form.matches("form[data-confirm]") && !window.confirm(form.getAttribute("data-confirm"))) { e.preventDefault(); return; }
    const btn = form.querySelector('[type="submit"]:not([data-no-lock])');
    if (btn && !e.defaultPrevented) {
      setTimeout(() => { btn.disabled = true; btn.classList.add("opacity-70", "cursor-wait"); }, 0);
      setTimeout(() => { btn.disabled = false; btn.classList.remove("opacity-70", "cursor-wait"); }, 8000);
    }
  });
})();
