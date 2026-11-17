/* Софтмонтаж — страница корзины: товары, количество, отправка заявки («Пришлите КП» / «Заказать») */
(() => {
  const $ = (id) => document.getElementById(id);
  const C = window.SMCart;
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const money = (n) => Math.round(n || 0).toLocaleString("ru-RU").replace(/[\s,]/g, " ") + " ₸";
  const NOIMG = '<img class="noimg" src="/brand/favicon/softmontazh-favicon.svg" alt="">';
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  let items = [];

  async function load() {
    const c = C.get(), slugs = Object.keys(c);
    if (!slugs.length) { show("empty"); return; }
    const r = await fetch(`/api/cart/items?slugs=${encodeURIComponent(slugs.join(","))}`); const d = await r.json();
    items = d.items;
    const known = new Set(items.map((x) => x.slug));
    slugs.filter((s) => !known.has(s)).forEach((s) => C.qty(s, 0)); // товара больше нет в каталоге
    render();
  }
  function show(what) {
    $("cartGrid").hidden = what !== "list"; $("cartEmpty").hidden = what !== "empty"; $("cartDone").hidden = what !== "done";
  }
  function render() {
    const c = C.get();
    items = items.filter((x) => c[x.slug]);
    if (!items.length) { show("empty"); return; }
    show("list");
    let total = 0, noPrice = 0;
    $("cartList").innerHTML = items.map((p) => {
      const q = c[p.slug]; total += q * p.price; if (!p.price) noPrice++;
      return `<div class="citem">
        <div class="citem__img">${p.img ? `<img src="${esc(p.img)}" alt="" referrerpolicy="no-referrer" onerror="this.outerHTML='${NOIMG.replace(/"/g, "&quot;")}'">` : NOIMG}</div>
        <div><a class="citem__model" href="/catalog/${esc(p.slug)}/">${esc(p.brand)} ${esc(p.model)}</a><div class="citem__type">${esc(p.type)} · ${p.price ? money(p.price) + " за шт" : "цена по запросу"}</div></div>
        <div class="citem__right">
          <span class="qty"><button type="button" data-d="-1" data-s="${esc(p.slug)}">−</button><input type="number" min="1" value="${q}" data-s="${esc(p.slug)}"><button type="button" data-d="1" data-s="${esc(p.slug)}">+</button></span>
          <span class="citem__sum">${p.price ? money(q * p.price) : "—"}</span>
          <button type="button" class="kp-del" data-rm="${esc(p.slug)}" title="Убрать">×</button>
        </div></div>`;
    }).join("");
    $("cartTotal").innerHTML = `Итого по рознице: <b>${money(total)}</b>${noPrice ? `<small>${noPrice} поз. — цена по запросу, менеджер уточнит</small>` : ""}<small>Окончательную цену и сроки подтвердит менеджер в КП</small>`;
  }
  $("cartList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-d]"), rm = e.target.closest("[data-rm]");
    if (b) { const c = C.get(); C.qty(b.dataset.s, Math.max((c[b.dataset.s] || 1) + +b.dataset.d, 1)); render(); }
    if (rm) { C.qty(rm.dataset.rm, 0); render(); }
  });
  $("cartList").addEventListener("change", (e) => { if (e.target.dataset.s) { C.qty(e.target.dataset.s, Math.max(parseInt(e.target.value, 10) || 1, 1)); render(); } });

  let kind = "kp";
  document.querySelectorAll(".cart-btn[data-kind]").forEach((b) => b.addEventListener("click", () => { kind = b.dataset.kind; }));
  $("cartForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target), d = Object.fromEntries(f.entries());
    const digits = (d.phone || "").replace(/\D/g, "");
    if (!window.SM_CUSTOMER && digits.length < 10 && !(d.email || "").includes("@")) { err("Укажите телефон — по нему менеджер с вами свяжется."); return; }
    d.kind = kind; d.via_tg = !!window.SM_IN_TG; d.items = Object.entries(C.get()).map(([slug, qty]) => ({ slug, qty }));
    e.target.querySelectorAll("button").forEach((x) => { x.disabled = true; });
    try {
      const r = await fetch("/api/cart/lead", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify(d) });
      const res = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(res.error || "Не отправилось. Попробуйте ещё раз или напишите нам в WhatsApp.");
      C.set({}); $("leadNo").textContent = res.id || "";
      $("cartDoneText").firstChild.textContent = kind === "order" ? "Заказ принят. Менеджер свяжется с вами, чтобы подтвердить наличие и доставку. Номер заявки: " : "Менеджер подготовит коммерческое предложение и свяжется с вами. Номер заявки: ";
      show("done");
      try { if (window.SM_IN_TG && window.Telegram && window.Telegram.WebApp) window.Telegram.WebApp.HapticFeedback.notificationOccurred("success"); } catch (e2) { /* */ }
    } catch (ex) { err(ex.message); }
    e.target.querySelectorAll("button").forEach((x) => { x.disabled = false; });
  });
  function err(t) { $("cartErr").textContent = t; $("cartErr").hidden = !t; }

  $("toKp")?.addEventListener("click", async () => {
    const d = { items: Object.entries(C.get()).map(([slug, qty]) => ({ slug, qty })) };
    const r = await fetch("/kp/api/from-cart", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify(d) });
    const res = await r.json(); if (res.url) { C.set({}); location.href = res.url; }
  });
  load();
})();
