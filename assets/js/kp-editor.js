/* Софтмонтаж — редактор КП менеджера: позиции, цены в пределах вилки, скидка, живой предпросмотр листа */
(() => {
  const K = window.KP, ROLE = window.KP_ROLE;
  const $ = (id) => document.getElementById(id);
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
  const post = (url, d) => fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify(d) });
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const money = (n) => Math.round(n || 0).toLocaleString("ru-RU").replace(/[\s,]/g, " ") + " ₸";
  const FIELDS = ["to", "discount_pct", "view_mode", "hide_prices", "status", "items"];
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const pick = (o) => clone(Object.fromEntries(FIELDS.map((k) => [k, o[k]])));
  let saved = pick(K), st = pick(K);
  const SEC = { equipment: "Оборудование и материалы", works: "Монтажные и пусконаладочные работы" };

  // --- предпросмотр ---
  const frame = $("sheet"), scale = $("pvScale");
  function fit() {
    const w = $("pv").clientWidth - 36, k = Math.min(1, w / 794);
    let h = 1123; try { h = Math.max(1123, frame.contentDocument.documentElement.scrollHeight); } catch (e) { /* грузится */ }
    frame.style.height = h + "px";
    scale.style.transform = `scale(${k})`; scale.style.height = h * k + "px";
  }
  frame.addEventListener("load", fit); window.addEventListener("resize", fit);
  let tm, req = 0;
  function refresh() {
    clearTimeout(tm);
    tm = setTimeout(async () => {
      const my = ++req;
      const r = await post(`/kp/api/kp/${K.id}/preview`, st);
      if (my !== req || !r.ok) return;
      const d = await r.json();
      frame.srcdoc = d.html; renderSum(d.summary);
    }, 300);
  }

  // --- позиции ---
  function rowHtml(it, i) {
    const low = it.floor && it.price < it.floor;
    const hint = it.section === "works" ? "" : it.floor
      ? `розница ${money(it.retail)} · пол ${money(it.floor)}${ROLE === "owner" && it.purchase ? ` · закуп ${money(it.purchase)}` : ""}`
      : `розница ${money(it.retail)} · пол не задан — только по рознице`;
    const name = it.section === "works"
      ? `<input class="kp-input kp-in-name" data-i="${i}" data-f="name" value="${esc(it.name)}" placeholder="Название работы">
         <input class="kp-input kp-in-desc" data-i="${i}" data-f="desc" value="${esc(it.desc)}" placeholder="Описание (необязательно)">`
      : `<b>${esc(it.name)}</b> <span class="kp-type">${esc(it.type)}</span>`;
    return `<div class="kp-item${low ? " is-low" : ""}">
      <div class="kp-item__name">${name}${hint ? `<small>${hint}</small>` : ""}</div>
      <div class="kp-item__nums">
        <label>Кол-во<input class="kp-input" type="number" min="1" data-i="${i}" data-f="qty" value="${it.qty}"></label>
        ${it.section === "works" ? `<label>Ед.<input class="kp-input" data-i="${i}" data-f="unit" value="${esc(it.unit)}"></label>` : ""}
        <label>Цена, ₸<input class="kp-input" type="number" min="${it.floor || 0}" data-i="${i}" data-f="price" value="${it.price}"></label>
        <span class="kp-item__sum">${money(it.qty * it.price)}</span>
        <button type="button" class="kp-del" data-del="${i}" title="Убрать">×</button>
      </div></div>`;
  }
  function renderItems() {
    const groups = { equipment: [], works: [] };
    st.items.forEach((it, i) => (groups[it.section] || groups.equipment).push(rowHtml(it, i)));
    $("items").innerHTML = Object.entries(groups).filter(([, v]) => v.length)
      .map(([k, v]) => `<div class="kp-sec">${SEC[k]}</div>${v.join("")}`).join("") || `<p class="kp-hint">Позиций нет — добавьте товар поиском ниже.</p>`;
    $("cnt").textContent = st.items.length ? `${st.items.length} поз.` : "";
  }
  $("items").addEventListener("input", (e) => {
    const i = +e.target.dataset.i, f = e.target.dataset.f; if (Number.isNaN(i) || !f) return;
    st.items[i][f] = ["qty", "price"].includes(f) ? Math.max(parseInt(e.target.value || "0", 10) || 0, f === "qty" ? 1 : 0) : e.target.value;
    const row = e.target.closest(".kp-item");
    row.querySelector(".kp-item__sum").textContent = money(st.items[i].qty * st.items[i].price);
    row.classList.toggle("is-low", !!(st.items[i].floor && st.items[i].price < st.items[i].floor));
    changed(false);
  });
  $("items").addEventListener("click", (e) => { const d = e.target.closest("[data-del]"); if (!d) return; st.items.splice(+d.dataset.del, 1); renderItems(); changed(); });
  $("addWork").addEventListener("click", () => {
    st.items.push({ id: null, section: "works", name: "", type: "", desc: "", img: "", unit: "усл", qty: 1, price: 0, retail: 0, floor: null, slug: "" });
    renderItems(); changed(); $("items").querySelector(".kp-in-name:last-of-type")?.focus();
  });

  // --- поиск товара ---
  let qt;
  $("q").addEventListener("input", (e) => {
    clearTimeout(qt); const q = e.target.value.trim();
    if (q.length < 2) { $("sugg").hidden = true; return; }
    qt = setTimeout(async () => {
      const r = await fetch(`/api/catalog/products?q=${encodeURIComponent(q)}`, { credentials: "same-origin" }); const d = await r.json();
      $("sugg").innerHTML = d.items.slice(0, 12).map((p) => `<button type="button" data-slug="${esc(p.slug)}">
        <b>${esc(p.brand)} ${esc(p.model)}</b><span>${esc(p.type)}</span><em>${p.price ? money(p.price) : "цена по запросу"}</em></button>`).join("") || `<p class="kp-hint">Ничего не найдено</p>`;
      $("sugg").hidden = false;
    }, 250);
  });
  $("sugg").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-slug]"); if (!b) return;
    const ex = st.items.find((x) => x.slug === b.dataset.slug && !x.id);
    if (ex) ex.qty += 1; else st.items.push({ id: null, slug: b.dataset.slug, section: "equipment", qty: 1, _new: true });
    $("sugg").hidden = true; $("q").value = "";
    // данные товара (цена, пол) подставит сервер — получаем их через предпросмотр
    const r = await post(`/kp/api/kp/${K.id}/preview`, st); const d = await r.json();
    frame.srcdoc = d.html; renderSum(d.summary);
    await hydrateNew();
    renderItems(); changed(false);
  });
  async function hydrateNew() {
    const need = st.items.filter((x) => x._new);
    if (!need.length) return;
    const r = await fetch(`/api/catalog/products?q=&slugs=${need.map((x) => x.slug).join(",")}`, { credentials: "same-origin" });
    const d = await r.json();
    const by = Object.fromEntries(d.items.map((p) => [p.slug, p]));
    need.forEach((x) => {
      const p = by[x.slug]; if (!p) return;
      Object.assign(x, { name: p.model, type: p.type, unit: "шт", price: x.price ?? p.price, retail: p.price, floor: p.staff ? p.staff.floor : null, purchase: p.staff ? p.staff.purchase : null });
      delete x._new;
    });
  }
  document.addEventListener("click", (e) => { if (!e.target.closest(".kp-search")) $("sugg").hidden = true; });

  // --- прочие поля ---
  $("to").addEventListener("input", (e) => { st.to = e.target.value; changed(); });
  $("status").addEventListener("change", (e) => { st.status = e.target.value; changed(); });
  $("discount_pct").addEventListener("input", (e) => { st.discount_pct = parseFloat(e.target.value || "0") || 0; changed(); });
  $("hide_prices").addEventListener("change", (e) => { st.hide_prices = e.target.checked; changed(); });
  const seg = document.querySelector('[data-group="view_mode"]');
  const paintSeg = () => seg.querySelectorAll("button").forEach((b) => b.classList.toggle("is-on", b.dataset.v === st.view_mode));
  seg.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; st.view_mode = b.dataset.v; paintSeg(); changed(); });

  function renderSum(s) {
    if (!s) return;
    let h = `<div class="kp-sum__row">Итого <b>${money(s.total)}</b></div>`;
    if (s.discount) h += `<div class="kp-sum__row">Скидка <b>−${money(s.discount)}</b></div>`;
    h += `<div class="kp-sum__grand">К оплате клиентом <b>${money(s.grand)}</b></div>`;
    h += `<div class="kp-sum__in"><div class="kp-sum__t">Внутреннее — клиент не видит</div>`;
    if (ROLE === "owner") {
      h += `<div class="kp-sum__row">Закупка оборудования <b>${money(s.purchase_sum)}</b></div>
            <div class="kp-sum__row">Прибыль по оборудованию <b>${money(s.profit)}</b></div>`;
      if (s.works_total) h += `<div class="kp-sum__row">Работы <b>${money(s.works_total)}</b></div>`;
      if (s.no_purchase) h += `<div class="kp-sum__warn">У ${s.no_purchase} поз. не задана закупка — прибыль по ним не посчитана.</div>`;
    }
    h += `<div class="kp-sum__row">${ROLE === "owner" ? "Менеджеру" : "Ваш заработок"} <b>${money(s.commission)}</b></div>`;
    h += `<div class="kp-sum__row">Минимум по вилке <b>${money(s.floor_sum)}</b></div></div>`;
    if (s.errors && s.errors.length) h += `<div class="kp-sum__err">${s.errors.map(esc).join("<br>")}${ROLE === "owner" ? "<br><i>Вы владелец — можете сохранить и так.</i>" : ""}</div>`;
    $("sum").innerHTML = h;
    $("maxDisc").textContent = s.total ? `можно до ${s.max_discount_pct}%` : "";
  }

  const dirty = () => JSON.stringify(st) !== JSON.stringify(saved);
  function changed(rerender = true) {
    const d = dirty();
    $("saveBtn").disabled = !d; $("cancelBtn").disabled = !d;
    $("saveState").textContent = d ? "Есть несохранённые изменения" : "Все изменения сохранены";
    refresh();
  }
  function fill() {
    $("to").value = st.to || ""; $("status").value = st.status; $("discount_pct").value = st.discount_pct || 0;
    $("hide_prices").checked = !!st.hide_prices; paintSeg(); renderItems();
  }
  $("saveBtn").addEventListener("click", async () => {
    $("saveBtn").disabled = true;
    const r = await post(`/kp/api/kp/${K.id}/save`, st); const d = await r.json().catch(() => ({}));
    if (!r.ok) { renderSum(d.summary); alert(d.error || "Не сохранено"); changed(false); return; }
    st.items = d.items; saved = clone(st); fill(); renderSum(d.summary); changed(false);
    $("saveState").textContent = "Сохранено";
  });
  $("cancelBtn").addEventListener("click", () => { st = clone(saved); fill(); changed(); });

  // --- ссылка, WhatsApp, копия ---
  $("openLink").href = K.link;
  $("copyLink").addEventListener("click", async () => {
    if (dirty()) { alert("Сначала сохраните КП — по ссылке клиент видит сохранённую версию."); return; }
    try { await navigator.clipboard.writeText(K.link); $("copyLink").textContent = "Ссылка скопирована"; } catch (e) { prompt("Ссылка для клиента:", K.link); }
  });
  if (K.phone) {
    $("waBtn").hidden = false;
    $("waBtn").href = `https://wa.me/${K.phone}?text=${encodeURIComponent(`Здравствуйте! Коммерческое предложение ${K.code} от Софтмонтаж: ${K.link}`)}`;
  }
  $("waBtn").addEventListener("click", (e) => { if (dirty()) { e.preventDefault(); alert("Сначала сохраните КП."); } });
  $("copyKp").addEventListener("click", async () => { const r = await post(`/kp/api/kp/${K.id}/copy`, {}); const d = await r.json(); if (d.url) location.href = d.url; });
  $("link_active").checked = K.link_active;
  $("link_active").addEventListener("change", (e) => post(`/kp/api/kp/${K.id}/link`, { active: e.target.checked }));
  window.addEventListener("beforeunload", (e) => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });

  fill(); changed(false); setTimeout(fit, 60);
})();
