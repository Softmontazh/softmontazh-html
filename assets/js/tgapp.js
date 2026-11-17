/* Софтмонтаж — каталог внутри Telegram (Mini App) и корзина вошедшего клиента.
   В Telegram: проверяем вход по initData (подпись проверяет сервер), склеиваем корзину с корзиной из бота. */
(() => {
  const qs = new URLSearchParams(location.search);
  try { if (qs.get("tgapp") === "1") sessionStorage.setItem("tgapp", "1"); } catch (e) { /* нет хранилища */ }
  let inTg = false;
  try { inTg = sessionStorage.getItem("tgapp") === "1"; } catch (e) { inTg = qs.get("tgapp") === "1"; }
  window.SM_IN_TG = inTg;
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
  const post = (url, d) => fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify(d) });

  // корзина вошедшего клиента живёт и на сервере (её пополняет бот кнопкой «В корзину»)
  let t;
  function pushCart() {
    if (!window.SM_CUSTOMER || !window.SMCart) return;
    clearTimeout(t);
    t = setTimeout(() => post("/api/me/cart", { cart: window.SMCart.get() }), 400);
  }
  if (window.SMCart) {
    const orig = window.SMCart.set.bind(window.SMCart);
    window.SMCart.set = (c) => { orig(c); pushCart(); };
  }
  async function mergeCart() {
    if (!window.SM_CUSTOMER || !window.SMCart) return;
    const r = await post("/api/me/cart", { cart: window.SMCart.get(), merge: true });
    if (r.ok) { const d = await r.json(); try { localStorage.setItem("sm_cart", JSON.stringify(d.cart)); } catch (e) { /* */ } window.SMCart.paint(); }
  }

  if (!inTg) { mergeCart(); return; }
  document.documentElement.classList.add("in-tg");
  const s = document.createElement("script");
  s.src = "https://telegram.org/js/telegram-web-app.js";
  s.onload = async () => {
    const W = window.Telegram && window.Telegram.WebApp;
    if (!W) return;
    W.ready(); W.expand();
    if (W.BackButton && history.length > 1) { W.BackButton.show(); W.BackButton.onClick(() => history.back()); }
    if (window.SM_CUSTOMER) { mergeCart(); return; }
    if (!W.initData) return;
    const r = await post("/api/tg/webapp-login", { initData: W.initData });
    const d = await r.json().catch(() => ({}));
    if (d.ok) { window.SM_CUSTOMER = { name: d.name, phone: d.phone }; await mergeCart(); location.reload(); }
    else if (d.need === "register") {
      const b = document.createElement("div");
      b.className = "tg-need";
      b.innerHTML = 'Чтобы оформить заявку, отправьте номер в чате с ботом — кнопка «📱 Отправить номер». <button type="button">Вернуться в чат</button>';
      b.querySelector("button").onclick = () => W.close();
      document.body.prepend(b);
    }
  };
  document.head.appendChild(s);
})();
