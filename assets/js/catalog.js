/* Софтмонтаж — каталог оборудования. Данные с сервера: /api/catalog/products, меню — window.CATALOG_MENU */
(() => {
  const MENU = window.CATALOG_MENU || [];
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const money = (p) => p.toLocaleString("ru-RU").replace(/[\s,]/g, " ") + " ₸";
  const NOIMG = '<img class="noimg" src="/brand/favicon/softmontazh-favicon.svg" alt="">';
  const plural = (n, f) => { const a = n % 100, b = n % 10; return a > 10 && a < 20 ? f[2] : b === 1 ? f[0] : b >= 2 && b <= 4 ? f[1] : f[2]; };

  const url = new URLSearchParams(location.search);
  const st = {
    brand: url.get("brand") || "", cat: url.get("cat") || "", q: url.get("q") || "",
    instock: url.get("instock") === "1", sort: url.get("sort") || "pop", page: 1,
  };
  $("q").value = st.q; $("instock").checked = st.instock; $("sort").value = st.sort;

  // --- дерево: бренды › разделы › подразделы (id узла: "b:<бренд>", "n<id Barlau>", "c<раздел>") ---
  const ROOT = MENU.map((b) => ({ id: "b:" + b.slug, name: b.name, count: b.count, children: b.children, brand: b.slug }));
  const total = MENU.reduce((a, b) => a + b.count, 0);
  const parentOf = new Map(), brandOfId = new Map(), byId = new Map();
  (function index(list, parent, brand) {
    list.forEach((it) => {
      byId.set(it.id, it); parentOf.set(it.id, parent); brandOfId.set(it.id, brand || it.brand);
      index(it.children || [], it, brand || it.brand);
    });
  })(ROOT, null, null);

  // выбранный узел из адреса
  st.sel = st.brand ? "b:" + st.brand : "";
  if (url.get("node")) st.sel = "n" + url.get("node");
  else if (url.get("cat")) st.sel = "c" + url.get("cat");
  if (st.sel && !byId.has(st.sel)) st.sel = st.brand ? "b:" + st.brand : "";
  const open = new Set();
  const openPathTo = (id) => { let it = byId.get(id); while (it) { open.add(it.id); it = parentOf.get(it.id); } };
  openPathTo(st.sel);

  function setSel(id) {
    st.sel = id;
    st.brand = id ? brandOfId.get(id) : "";
    st.node = id && id[0] === "n" ? id.slice(1) : "";
    st.cat = id && id[0] === "c" ? id.slice(1) : "";
  }
  setSel(st.sel);

  function treeHtml(list, depth) {
    return list.map((it) => {
      const kids = it.children && it.children.length;
      const isOpen = open.has(it.id), on = st.sel === it.id;
      return `<div class="tr${on ? " is-on" : ""}${isOpen ? " is-open" : ""}" style="--d:${depth}">
        <div class="tr-row">${kids ? `<button class="tr-tog" data-tog="${esc(it.id)}" aria-label="${isOpen ? "Свернуть" : "Развернуть"}" aria-expanded="${isOpen}"></button>` : `<span class="tr-dot"></span>`}
          <button class="tr-name" data-sel="${esc(it.id)}">${esc(it.name)} <small>${it.count}</small></button></div>
        ${kids && isOpen ? `<div class="tr-kids">${treeHtml(it.children, depth + 1)}</div>` : ""}
      </div>`;
    }).join("");
  }

  function renderMenu() {
    const all = `<div class="tr${!st.sel ? " is-on" : ""}" style="--d:0"><div class="tr-row"><span class="tr-dot"></span><button class="tr-name" data-sel="">Все товары <small>${total}</small></button></div></div>`;
    $("tree").innerHTML = all + treeHtml(ROOT, 0);
    $("mtree").innerHTML = all + treeHtml(ROOT, 0);
    const cur = byId.get(st.sel);
    $("bbtnLabel").textContent = cur ? cur.name : "Каталог";
    // лента на телефоне: «назад» + подразделы текущего узла (или соседи, если глубже некуда)
    let chips = "";
    if (cur) {
      const par = parentOf.get(cur.id);
      const list = cur.children && cur.children.length ? cur.children : (par ? par.children : ROOT);
      chips = `<button class="cchip cchip--back" data-sel="${par ? esc(par.id) : ""}">‹ ${esc(par ? par.name : "Все")}</button>` +
        list.map((c) => `<button class="cchip cchip--cat${c.id === st.sel ? " is-on" : ""}" data-sel="${esc(c.id)}">${esc(c.name)}</button>`).join("");
    } else {
      chips = ROOT.map((c) => `<button class="cchip cchip--cat" data-sel="${esc(c.id)}">${esc(c.name)}</button>`).join("");
    }
    $("subCats").innerHTML = chips;
    const on = $("subCats").querySelector(".is-on");
    if (on) on.scrollIntoView({ block: "nearest", inline: "center" }); else $("subCats").scrollLeft = 0;
  }

  // --- товары ---
  const stockHtml = (p) => p.stock > 0
    ? `<span class="stock is-in">В наличии${p.stock_label && p.stock_label[0] === ">" ? " " + esc(p.stock_label) : ""}</span>`
    : `<span class="stock">Под заказ</span>`;
  const staffLine = (p) => {
    const x = p.staff; if (!x) return "";
    const parts = [];
    if (window.CATALOG_ROLE === "owner") parts.push(x.purchase ? `закуп ${money(x.purchase)}` : "закуп —");
    parts.push(x.floor ? `пол ${money(x.floor)}` : "пол —");
    if (x.room_pct != null) parts.push(`уступить до ${x.room_pct}%`);
    return `<div class="pcard__staff" title="Видят только сотрудники">${parts.join(" · ")}</div>`;
  };
  const card = (p) => `
    <a class="pcard" href="/catalog/${esc(p.slug)}/">
      <div class="pcard__img">${p.img ? `<img src="${esc(p.img)}" alt="${esc(p.brand + " " + p.model)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='${NOIMG.replace(/"/g, "&quot;")}'">` : NOIMG}</div>
      <div class="pcard__brand">${esc(p.brand)}</div>
      <div class="pcard__model">${esc(p.model)}</div>
      <div class="pcard__type">${esc(p.type)}</div>
      ${staffLine(p)}
      <div class="pcard__foot">${p.price > 0 ? `<div class="pcard__price">${money(p.price)}</div>` : `<div class="pcard__price is-req">Цена по запросу</div>`}${stockHtml(p)}</div>
    </a>`;

  let req = 0;
  async function load(append) {
    const my = ++req;
    const qs = new URLSearchParams();
    if (st.brand) qs.set("brand", st.brand);
    if (st.node) qs.set("node", st.node);
    else if (st.brand && st.cat) qs.set("cat", st.cat);
    if (st.q) qs.set("q", st.q);
    if (st.instock) qs.set("instock", "1");
    if (st.sort !== "pop") qs.set("sort", st.sort);
    history.replaceState(null, "", location.pathname + (qs.toString() ? "?" + qs : ""));
    qs.set("page", st.page);
    $("grid").classList.add("is-loading");
    try {
      const r = await fetch("/api/catalog/products?" + qs, { credentials: "same-origin" });
      const d = await r.json();
      if (my !== req) return;
      $("count").textContent = `${d.total.toLocaleString("ru-RU")} ${plural(d.total, ["товар", "товара", "товаров"])}`;
      const html = d.items.map(card).join("");
      if (append) $("grid").insertAdjacentHTML("beforeend", html);
      else $("grid").innerHTML = html || `<div class="cat-empty">Ничего не нашли. Напишите нам — подберём аналог или привезём под заказ.<br><br><a class="btn btn--accent btn--sm" href="${(window.SM && window.SM.wa) || "https://wa.me/77779000305"}" target="_blank" rel="noopener">Написать в WhatsApp</a></div>`;
      $("more").hidden = d.page >= d.pages;
    } catch (e) {
      if (my === req) $("grid").innerHTML = `<div class="cat-empty">Каталог временно не загрузился. Обновите страницу или напишите нам в WhatsApp.</div>`;
    } finally {
      if (my === req) $("grid").classList.remove("is-loading");
    }
  }
  const reload = () => { st.page = 1; renderMenu(); load(false); };

  // --- события ---
  function toggleBrands(open) {
    $("bmenu").hidden = !open; $("bbtn").setAttribute("aria-expanded", open); $("bbtn").classList.toggle("is-open", open);
  }
  const pick = (e) => {
    const tog = e.target.closest("[data-tog]");
    if (tog) { const id = tog.dataset.tog; open.has(id) ? open.delete(id) : open.add(id); renderMenu(); return; }
    const sel = e.target.closest("[data-sel]");
    if (!sel) return;
    const id = sel.dataset.sel;
    setSel(id); if (id) { openPathTo(id); open.add(id); }
    const inPanel = !!e.target.closest("#bmenu");
    const it = byId.get(id);
    if (!inPanel || !(it && it.children && it.children.length)) toggleBrands(false);
    reload();
    if (window.innerWidth > 960) window.scrollTo({ top: Math.min(scrollY, $("grid").getBoundingClientRect().top + scrollY - 160), behavior: "smooth" });
  };
  ["tree", "sub"].forEach((id) => $(id).addEventListener("click", pick));
  $("bbtn").addEventListener("click", (e) => { e.stopPropagation(); toggleBrands($("bmenu").hidden); });
  document.addEventListener("click", (e) => { if (!e.composedPath().some((el) => el.id === "bmenu" || el.id === "bbtn")) toggleBrands(false); });
  let t; $("q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value.trim(); if (st.q) setSel(""); reload(); }, 300); });
  $("instock").addEventListener("change", (e) => { st.instock = e.target.checked; reload(); });
  $("sort").addEventListener("change", (e) => { st.sort = e.target.value; reload(); });
  $("more").addEventListener("click", () => { st.page += 1; load(true); });

  reload();
})();
