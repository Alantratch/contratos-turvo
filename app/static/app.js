(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let view = "overview";
  let page = 1;
  let pageTotal = 0;
  let secretaries = [];
  let searchTimer = null;

  const html = (text) => String(text ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const date = (s) => s ? new Intl.DateTimeFormat("pt-BR", {timeZone:"UTC"}).format(new Date(s + "T12:00:00Z")) : "Não informada";
  const number = (n) => new Intl.NumberFormat("pt-BR").format(n ?? 0);
  const money = (n) => n == null ? "Valor não informado" : new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"}).format(Number(n));
  const remaining = (s) => s ? Math.ceil((Date.parse(s + "T12:00:00Z") - Date.parse(new Date().toISOString().slice(0,10) + "T12:00:00Z")) / 86400000) : null;
  const status = (due) => {
    const days = remaining(due);
    if (days == null) return '<span class="status neutral">Sem data</span>';
    if (days < 0) return '<span class="status neutral">Prazo encerrado</span>';
    if (days <= 30) return '<span class="status danger">' + days + ' dias</span>';
    if (days <= 60) return '<span class="status warning">' + days + ' dias</span>';
    return '<span class="status good">Acompanhar</span>';
  };

  async function api(path, opts = {}) {
    const response = await fetch(path, {credentials:"same-origin", cache:"no-store", ...opts});
    if (!response.ok) {
      let detail = "Erro HTTP " + response.status;
      try { detail = (await response.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return await response.json();
  }

  function feedback(message, error = false) {
    const node = $("feedback");
    node.textContent = message;
    node.classList.toggle("error", error);
    node.hidden = false;
    window.setTimeout(() => { node.hidden = true; }, 6000);
  }

  function switchView(next) {
    view = next;
    document.querySelectorAll(".view").forEach((section) => { section.hidden = section.id !== next; });
    document.querySelectorAll(".nav-item").forEach((button) => {
      const selected = button.dataset.view === next;
      button.classList.toggle("selected", selected);
      if (selected) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    const names = {overview:"Visão geral",contracts:"Contratos",secretaries:"Secretarias",sync:"Sincronização"};
    $("breadcrumb").textContent = names[next];
    $("sidebar").classList.remove("open");
    $("menu-toggle").setAttribute("aria-expanded", "false");
    if (next === "contracts") loadContracts();
    if (next === "secretaries") loadSecretaries();
    if (next === "sync") loadSync();
  }

  async function loadSummary() {
    try {
      const s = await api("/api/summary");
      $("stat-all").textContent = number(s.all);
      $("stat-active").textContent = number(s.active);
      $("stat-upcoming").textContent = number(s.upcoming);
      $("stat-unclassified").textContent = number(s.unclassified);
      $("overview-sync").textContent = s.sync ? "Última verificação: " + (s.sync.status === "ok" ? "concluída" : "com falha") + (s.sync.finished_at ? " · " + new Date(s.sync.finished_at).toLocaleString("pt-BR") : "") : "Aguardando primeira sincronização";
      const groups = s.by_secretary || [];
      $("secretary-chart").className = groups.length ? "bars" : "chart-empty";
      $("secretary-chart").innerHTML = groups.length ? groups.slice(0, 7).map((g) => {
        const width = Math.max(1, Math.round(100 * g.count / Math.max(1, groups[0].count)));
        return '<div class="bar-item"><div class="bar-top"><strong>' + html(g.name) + '</strong><span>' + number(g.count) + '</span></div><div class="bar-track"><div class="bar-fill" style="width:' + width + '%"></div></div></div>';
      }).join("") : "Sem contratos classificados com vencimento nos próximos 60 dias.";
      const upcoming = await api("/api/contracts?period=30&limit=5");
      $("upcoming-body").innerHTML = upcoming.items.length ? upcoming.items.map((c) =>
        '<tr><td><strong>' + html(c.number || c.pncp_key) + '</strong><span class="subline">' + html(c.year || "") + '</span></td><td>' +
        html(c.supplier || "Não informado") + '</td><td>' + html(c.secretary || "Não atribuída") +
        '</td><td>' + date(c.end_date) + '</td><td>' + status(c.end_date) + '</td></tr>'
      ).join("") : '<tr><td colspan="5" class="empty">Nenhum vencimento encontrado nos próximos 30 dias.</td></tr>';
    } catch (err) { feedback("Não foi possível atualizar o panorama: " + err.message, true); }
  }

  async function loadSecretaries() {
    try {
      secretaries = await api("/api/secretaries");
      const current = $("secretary-filter").value;
      $("secretary-filter").innerHTML = '<option value="">Todas</option>' + secretaries.map(s => '<option value="' + s.id + '">' + html(s.name) + '</option>').join("");
      $("secretary-filter").value = current;
      $("secretary-list").innerHTML = secretaries.length ? secretaries.map((s) =>
        '<div class="secretary-item"><div><strong>' + html(s.name) + '</strong><small>' + html(s.email || "Sem e-mail cadastrado") + '</small></div><span class="tag">Cadastro</span></div>'
      ).join("") : "Nenhuma secretaria cadastrada.";
    } catch (err) { feedback("Não foi possível carregar secretarias: " + err.message, true); }
  }

  function secretaryOptions(selected) {
    return '<option value="">Sem atribuição</option>' + secretaries.map((s) =>
      '<option value="' + s.id + '"' + (s.id === selected ? ' selected' : '') + '>' + html(s.name) + '</option>'
    ).join("");
  }

  async function loadContracts() {
    try {
      const q = $("contract-search").value.trim();
      const period = $("period-filter").value;
      const secretary = $("secretary-filter").value;
      const params = new URLSearchParams({q, period, page:String(page), limit:"25"});
      if (secretary) params.set("secretary_id", secretary);
      const result = await api("/api/contracts?" + params);
      pageTotal = result.total;
      $("contracts-count").textContent = number(pageTotal) + " registros";
      $("pagination-text").textContent = "Página " + page + " · " + number(pageTotal) + " resultado(s)";
      $("prev").disabled = page <= 1;
      $("next").disabled = page * 25 >= pageTotal;
      $("contracts-body").innerHTML = result.items.length ? result.items.map((c) => {
        const eligibleLink = /^\d{14}$/.test(c.buyer_cnpj || "") && Number.isInteger(c.year) && Number.isInteger(c.sequence);
        const link = eligibleLink ? '<a target="_blank" rel="noopener noreferrer" href="https://pncp.gov.br/app/contratos/' + c.buyer_cnpj + '/' + c.year + '/' + c.sequence + '">Abrir PNCP ↗</a>' : "Referência indisponível";
        return '<tr><td><strong>' + html(c.number || c.pncp_key) + '</strong><span class="subline">' + html(c.year || "") + '</span></td>' +
          '<td><strong>' + html(c.supplier || "Não informado") + '</strong><span class="subline">' + html((c.object || "Objeto não informado").slice(0, 160)) + '</span><span class="subline">' + money(c.amount) + '</span></td>' +
          '<td><select class="assign-select" aria-label="Secretaria do contrato ' + html(c.number) + '" data-id="' + c.id + '">' + secretaryOptions(c.secretary_id) + '</select></td>' +
          '<td><strong>' + date(c.end_date) + '</strong><span class="subline">' + status(c.end_date) + '</span></td>' +
          '<td>' + link + '</td></tr>';
      }).join("") : '<tr><td colspan="5" class="empty">Nenhum contrato encontrado para esses filtros.</td></tr>';
    } catch (err) { feedback("Não foi possível carregar contratos: " + err.message, true); }
  }

  async function loadSync() {
    try {
      const data = await api("/api/sync");
      $("cursor-date").textContent = data.next_publication_day ? date(data.next_publication_day) : "Aguardando início";
      $("sync-body").innerHTML = data.runs.length ? data.runs.map((r) =>
        '<tr><td><strong>' + html(r.kind) + '</strong></td><td>' + new Date(r.started_at).toLocaleString("pt-BR") +
        '</td><td>' + number(r.processed) + '</td><td><span class="status ' + (r.status === "ok" ? "good" : r.status === "error" ? "danger" : "neutral") + '">' +
        html(r.status) + '</span>' + (r.error ? '<span class="subline">' + html(r.error.slice(0, 160)) + '</span>' : "") + '</td></tr>'
      ).join("") : '<tr><td colspan="4" class="empty">Nenhuma execução registrada.</td></tr>';
    } catch (err) { feedback("Não foi possível consultar sincronização: " + err.message, true); }
  }

  document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $("menu-toggle").addEventListener("click", () => {
    const opened = $("sidebar").classList.toggle("open");
    $("menu-toggle").setAttribute("aria-expanded", String(opened));
  });
  $("refresh").addEventListener("click", () => { loadSummary(); });
  $("refresh-sync").addEventListener("click", loadSync);
  $("see-all").addEventListener("click", () => { page = 1; $("period-filter").value = "30"; switchView("contracts"); });
  $("contract-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { page = 1; loadContracts(); }, 320);
  });
  ["period-filter","secretary-filter"].forEach((id) => $(id).addEventListener("change", () => { page = 1; loadContracts(); }));
  $("prev").addEventListener("click", () => { if (page > 1) { page--; loadContracts(); } });
  $("next").addEventListener("click", () => { if (page * 25 < pageTotal) { page++; loadContracts(); } });
  $("secretary-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/secretaries", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:$("secretary-name").value,email:$("secretary-email").value || null})});
      e.target.reset();
      await loadSecretaries();
      feedback("Secretaria cadastrada. Confira o e-mail antes de ativar os alertas.");
    } catch (err) { feedback("Cadastro não concluído: " + err.message, true); }
  });
  $("contracts-body").addEventListener("change", async (e) => {
    const select = e.target.closest("select[data-id]");
    if (!select) return;
    const contractId = Number(select.dataset.id);
    select.disabled = true;
    try {
      await api("/api/contracts/" + contractId + "/secretary", {method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({secretary_id:select.value ? Number(select.value) : null})});
      feedback("Responsabilidade atualizada e registrada na auditoria.");
    } catch (err) { feedback("Atribuição não concluída: " + err.message, true); }
    finally { select.disabled = false; }
  });
  (async () => { await loadSecretaries(); await loadSummary(); })();
})();
