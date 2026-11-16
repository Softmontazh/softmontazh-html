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

  const brandOf = (slug) => MENU.find((b) => b.slug === slug);
  const total = MENU.reduce((a, b) => a + b.count, 0);

  // --- меню: колонка (компьютер), выпадающий список брендов и лента разделов (телефон) ---
  function renderMenu() {
    const opt = (attr, v, label, n, on) => `<button class="cat-opt${on ? " is-on" : ""}" ${attr}="${esc(v)}">${esc(label)} <small>${n}</small></button>`;
    const brandsHtml = opt("data-brand", "", "Все бренды", total, !st.brand) + MENU.map((b) => opt("data-brand", b.slug, b.name, b.count, st.brand === b.slug)).join("");
    $("brands").innerHTML = brandsHtml;
    $("subBrands").innerHTML = brandsHtml;
    const b = brandOf(st.brand);
    $("bbtnLabel").textContent = b ? b.name : "Все бренды";
    const cats = b ? b.cats : [];
    $("cats").closest(".cat-side__block").hidden = !b;
    $("cats").innerHTML = b ? opt("data-cat", "", "Все разделы", b.count, !st.cat) + cats.map((c) => opt("data-cat", c.slug, c.name, c.count, st.cat === c.slug)).join("") : "";
    $("subCats").innerHTML = b
      ? [["", "Все разделы"], ...cats.map((c) => [c.slug, c.name])].map(([v, l]) => `<button class="cchip cchip--cat${st.cat === v ? " is-on" : ""}" data-cat="${esc(v)}">${esc(l)}</button>`).join("")
      : `<span class="cat-hint">Выберите бренд — появятся разделы</span>`;
    const on = $("subCats").querySelector(".is-on");
    if (on) on.scrollIntoView({ block: "nearest", inline: "center" });
  }

  // --- товары ---
  const stockHtml = (p) => p.stock > 0
    ? `<span class="stock is-in">В наличии${p.stock_label && p.stock_label[0] === ">" ? " " + esc(p.stock_label) : ""}</span>`
    : `<span class="stock">Под заказ</span>`;
  const card = (p) => `
    <a class="pcard" href="/catalog/${esc(p.slug)}/">
      <div class="pcard__img">${p.img ? `<img src="${esc(p.img)}" alt="${esc(p.brand + " " + p.model)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='${NOIMG.replace(/"/g, "&quot;")}'">` : NOIMG}</div>
      <div class="pcard__brand">${esc(p.brand)}</div>
      <div class="pcard__model">${esc(p.model)}</div>
      <div class="pcard__type">${esc(p.type)}</div>
      <div class="pcard__foot">${p.price > 0 ? `<div class="pcard__price">${money(p.price)}</div>` : `<div class="pcard__price is-req">Цена по запросу</div>`}${stockHtml(p)}</div>
    </a>`;

  let req = 0;
  async function load(append) {
    const my = ++req;
    const qs = new URLSearchParams();
    if (st.brand) qs.set("brand", st.brand);
    if (st.brand && st.cat) qs.set("cat", st.cat);
    if (st.q) qs.set("q", st.q);
    if (st.instock) qs.set("instock", "1");
    if (st.sort !== "pop") qs.set("sort", st.sort);
    history.replaceState(null, "", location.pathname + (qs.toString() ? "?" + qs : ""));
    qs.set("page", st.page);
    $("grid").classList.add("is-loading");
    try {
      const r = await fetch("/api/catalog/products?" + qs);
      const d = await r.json();
      if (my !== req) return;
      $("count").textContent = `${d.total.toLocaleString("ru-RU")} ${plural(d.total, ["товар", "товара", "товаров"])}`;
      const html = d.items.map(card).join("");
      if (append) $("grid").insertAdjacentHTML("beforeend", html);
      else $("grid").innerHTML = html || `<div class="cat-empty">Ничего не нашли. Напишите нам — подберём аналог или привезём под заказ.<br><br><a class="btn btn--accent btn--sm" href="https://wa.me/77779000305" target="_blank" rel="noopener">Написать в WhatsApp</a></div>`;
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
    const b = e.target.closest("[data-brand]"), c = e.target.closest("[data-cat]");
    if (b) { st.brand = b.dataset.brand; st.cat = ""; } else if (c) { st.cat = c.dataset.cat; } else return;
    toggleBrands(false); reload();
    if (window.innerWidth > 960) window.scrollTo({ top: $("grid").getBoundingClientRect().top + scrollY - 160, behavior: "smooth" });
  };
  ["brands", "cats", "sub"].forEach((id) => $(id).addEventListener("click", pick));
  $("bbtn").addEventListener("click", (e) => { e.stopPropagation(); toggleBrands($("bmenu").hidden); });
  document.addEventListener("click", (e) => { if (!e.target.closest("#bmenu, #bbtn")) toggleBrands(false); });
  let t; $("q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value.trim(); if (st.q) { st.brand = ""; st.cat = ""; } reload(); }, 300); });
  $("instock").addEventListener("change", (e) => { st.instock = e.target.checked; reload(); });
  $("sort").addEventListener("change", (e) => { st.sort = e.target.value; reload(); });
  $("more").addEventListener("click", () => { st.page += 1; load(true); });

  reload();
})();
