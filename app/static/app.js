(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let view = "overview";
  let page = 1;
  let pageTotal = 0;
  let secretaries = [];
  let searchTimer = null;
  let calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  let calendarSelectedDay = null;
  let contractDateFilter = null;
  let calendarRequest = 0;
  let calendarDays = {};
  let procurementPage = 1;
  let procurementTotal = 0;

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
    const names = {overview:"Visão geral",contracts:"Contratos",procurements:"Contratações",calendar:"Calendário",secretaries:"Secretarias",sync:"Sincronização"};
    $("breadcrumb").textContent = names[next];
    $("sidebar").classList.remove("open");
    $("menu-toggle").setAttribute("aria-expanded", "false");
    if (next === "contracts") loadContracts();
    if (next === "procurements") loadProcurements();
    if (next === "calendar") loadCalendar();
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
      const calendarCurrent = $("calendar-secretary-filter").value;
      $("calendar-secretary-filter").innerHTML = '<option value="">Todas as secretarias</option>' + secretaries.map(s => '<option value="' + s.id + '">' + html(s.name) + '</option>').join("");
      $("calendar-secretary-filter").value = calendarCurrent;
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
      if (contractDateFilter) params.set("due_date", contractDateFilter);
      $("clear-calendar-date").hidden = !contractDateFilter;
      $("clear-calendar-date").textContent = contractDateFilter ? "Limpar data: " + date(contractDateFilter) : "Limpar filtro da data";
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

  async function loadProcurements() {
    try {
      const q = $("procurement-search").value.trim();
      const data = await api("/api/procurements?" + new URLSearchParams({q, page:String(procurementPage), limit:"25"}));
      procurementTotal = data.total;
      $("procurements-count").textContent = number(data.total) + " registros";
      $("procurement-pagination-text").textContent = "Página " + procurementPage + " · " + number(data.total) + " resultado(s)";
      $("procurement-prev").disabled = procurementPage <= 1;
      $("procurement-next").disabled = procurementPage * 25 >= procurementTotal;
      $("procurements-body").innerHTML = data.items.length ? data.items.map((p) =>
        '<tr><td><strong>' + html(p.number || p.source_key) + '</strong><span class="subline">' + html(p.year || "") + ' · Processo ' + html(p.process || "não informado") + '</span></td>' +
        '<td><strong>' + html(p.modality || "Não informada") + '</strong><span class="subline">' + html(p.status || "Situação não informada") + '</span></td>' +
        '<td><span class="subline procurement-object">' + html(p.object || "Objeto não informado") + '</span></td>' +
        '<td><span class="subline">Estimado: ' + money(p.estimated_amount) + '</span><span class="subline">Homologado: ' + money(p.awarded_amount) + '</span></td>' +
        '<td>' + date(p.published_at) + '</td></tr>'
      ).join("") : '<tr><td colspan="5" class="empty">Nenhuma contratação encontrada.</td></tr>';
    } catch (err) { feedback("Não foi possível carregar contratações: " + err.message, true); }
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


  function isoLocal(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function monthKey() {
    return calendarMonth.getFullYear() + "-" + String(calendarMonth.getMonth() + 1).padStart(2, "0");
  }

  function calendarMonthShift(delta) {
    const next = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + delta, 1);
    if (next.getFullYear() < 2021 || next.getFullYear() > 2100) return;
    calendarMonth = next;
    calendarSelectedDay = null;
    loadCalendar();
  }

  async function loadCalendar() {
    const requestId = ++calendarRequest;
    const month = monthKey();
    const year = calendarMonth.getFullYear();
    const monthIndex = calendarMonth.getMonth();
    const title = new Intl.DateTimeFormat("pt-BR", {month:"long", year:"numeric"}).format(calendarMonth);
    $("calendar-month-label").textContent = title.charAt(0).toUpperCase() + title.slice(1);
    $("calendar-grid").textContent = "Carregando vencimentos…";
    $("calendar-selected-date").textContent = "Aguardando seleção";
    $("calendar-day-list").textContent = "Carregando…";
    $("calendar-see-all").hidden = true;
    const secretaryId = $("calendar-secretary-filter").value;
    const params = new URLSearchParams({month});
    if (secretaryId) params.set("secretary_id", secretaryId);
    try {
      const data = await api("/api/calendar?" + params);
      if (requestId !== calendarRequest || view !== "calendar") return;
      calendarDays = Object.fromEntries((data.days || []).map(d => [d.date, d.items || []]));
      const counts = Object.fromEntries((data.days || []).map(d => [d.date, d.count]));
      $("calendar-total").textContent = number(data.total) + " vencimento(s) neste mês";
      const today = isoLocal(new Date());
      const currentMonth = today.slice(0, 7) === month;
      const first = new Date(year, monthIndex, 1);
      const count = new Date(year, monthIndex + 1, 0).getDate();
      const offset = (first.getDay() + 6) % 7;
      if (!calendarSelectedDay || !calendarSelectedDay.startsWith(month)) {
        calendarSelectedDay = currentMonth ? today : ((data.days || [])[0]?.date || isoLocal(first));
      }
      const cells = Array.from({length:offset}, () => '<span class="calendar-spacer" aria-hidden="true"></span>');
      for (let day = 1; day <= count; day++) {
        const due = isoLocal(new Date(year, monthIndex, day));
        const total = counts[due] || 0;
        const soon = total > 0 && remaining(due) >= 0 && remaining(due) <= 30;
        const classes = ["calendar-day", due === today ? "is-today" : "", due === calendarSelectedDay ? "is-selected" : "", total ? "has-deadlines" : "", soon ? "is-soon" : ""].filter(Boolean).join(" ");
        const label = day + " de " + title + ": " + total + " vencimentos";
        cells.push('<button type="button" class="' + classes + '" data-day="' + due + '" aria-label="' + html(label) + '" aria-pressed="' + (due === calendarSelectedDay) + '"><span class="day-number">' + day + '</span>' + (total ? '<span class="day-dot"></span><span class="day-total">' + number(total) + ' venc.</span>' : '') + '</button>');
      }
      $("calendar-grid").innerHTML = cells.join("");
      showCalendarDay(calendarSelectedDay, requestId);
    } catch (err) {
      if (requestId !== calendarRequest) return;
      $("calendar-grid").textContent = "Não foi possível carregar o calendário.";
      $("calendar-selected-count").textContent = "Erro na consulta ao banco";
      $("calendar-day-list").textContent = "Tente recarregar o calendário.";
      feedback("Calendário indisponível: " + err.message, true);
    }
  }

  async function showCalendarDay(day, requestId = calendarRequest) {
    calendarSelectedDay = day;
    $("calendar-grid").querySelectorAll("button[data-day]").forEach(button => {
      const active = button.dataset.day === day;
      button.classList.toggle("is-selected", active);
      button.setAttribute("aria-pressed", String(active));
    });
    $("calendar-selected-date").textContent = new Intl.DateTimeFormat("pt-BR", {day:"numeric", month:"long", year:"numeric", timeZone:"UTC"}).format(new Date(day + "T12:00:00Z"));
    const items = calendarDays[day] || [];
    if (requestId !== calendarRequest || day !== calendarSelectedDay || view !== "calendar") return;
    $("calendar-selected-count").textContent = number(items.length) + " contrato(s) com vencimento registrado nesta data";
    $("calendar-day-list").innerHTML = items.length ? items.map(c =>
        '<article class="calendar-entry"><div class="entry-top"><strong>' + html(c.number || c.pncp_key) + '</strong>' + status(c.end_date) +
        '</div><p class="calendar-entry-object">' + html(c.object || "Objeto não informado") + '</p><small>' +
        html(c.supplier || "Fornecedor não informado") + '</small><small>' +
        html(c.secretary || "Sem secretaria definida") + '</small><small class="calendar-entry-object">' +
        html(money(c.amount)) + '</small></article>'
      ).join("") : '<p class="muted calendar-empty">Nenhum contrato com vencimento registrado nesse dia.</p>';
    $("calendar-see-all").hidden = items.length === 0;
  }

  function showDateInContracts() {
    if (!calendarSelectedDay) return;
    contractDateFilter = calendarSelectedDay;
    $("period-filter").value = "all";
    $("secretary-filter").value = $("calendar-secretary-filter").value;
    page = 1;
    switchView("contracts");
  }

  document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $("menu-toggle").addEventListener("click", () => {
    const opened = $("sidebar").classList.toggle("open");
    $("menu-toggle").setAttribute("aria-expanded", String(opened));
  });
  $("refresh").addEventListener("click", () => { loadSummary(); });
  $("refresh-sync").addEventListener("click", loadSync);
  $("calendar-prev").addEventListener("click", () => calendarMonthShift(-1));
  $("calendar-next").addEventListener("click", () => calendarMonthShift(1));
  $("calendar-today").addEventListener("click", () => {
    const today = new Date();
    calendarMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    calendarSelectedDay = isoLocal(today);
    loadCalendar();
  });
  $("calendar-secretary-filter").addEventListener("change", loadCalendar);
  $("calendar-grid").addEventListener("click", (e) => {
    const button = e.target.closest("button[data-day]");
    if (button) showCalendarDay(button.dataset.day);
  });
  $("calendar-see-all").addEventListener("click", showDateInContracts);
  $("clear-calendar-date").addEventListener("click", () => {
    contractDateFilter = null;
    page = 1;
    loadContracts();
  });
  $("see-all").addEventListener("click", () => { page = 1; $("period-filter").value = "30"; switchView("contracts"); });
  $("contract-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { page = 1; loadContracts(); }, 320);
  });
  ["period-filter","secretary-filter"].forEach((id) => $(id).addEventListener("change", () => { page = 1; loadContracts(); }));
  $("procurement-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { procurementPage = 1; loadProcurements(); }, 320);
  });
  $("procurement-prev").addEventListener("click", () => { if (procurementPage > 1) { procurementPage--; loadProcurements(); } });
  $("procurement-next").addEventListener("click", () => { if (procurementPage * 25 < procurementTotal) { procurementPage++; loadProcurements(); } });
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
