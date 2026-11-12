/* Софтмонтаж — общие шапка/подвал и мелкие функции.
   Меню и контакты правятся здесь, в одном месте, для всех страниц. */
(function () {
  const PHONE = "+7 708 755 3877";
  const PHONE_HREF = "tel:+77087553877";
  const EMAIL = "info@softmontazh.kz";
  const WA = "https://wa.me/77779000305?text=" + encodeURIComponent("Здравствуйте! Хочу обсудить объект.");
  const TG = "https://t.me/softmontazh";
  const TT = "https://www.tiktok.com/@softmontazh";
  const ESEMER = "https://esemer.kz";

  // На сервере — пути от корня (чтобы шапка работала и на странице 404 по любому адресу), локально (file://) — относительные
  const B = location.protocol === "file:" ? "" : "/";

  const NAV = [
    ["index.html", "Главная"],
    ["services.html", "Услуги"],
    ["certificates.html", "Сертификаты"],
    ["contact.html", "Контакты"],
  ];

  const ICON = {
    phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2"/></svg>',
    mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 3 3 10.5l7 2.5 2.5 7z"/><path d="m21 3-11 10"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="4"/><path d="m10 9 5 3-5 3z"/></svg>',
  };

  let here = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  if (!here.includes(".")) here += ".html"; // адреса без .html: /services → services.html
  const navLinks = (cls) => NAV.map(([href, label]) =>
    `<a class="${cls}${href === here ? " is-active" : ""}" href="${B}${href}"${href === here ? ' aria-current="page"' : ""}>${label}</a>`).join("");

  const header = `
  <div class="container site-header__row">
    <a class="site-header__logo" href="${B}index.html" aria-label="Софтмонтаж — на главную">
      <img src="${B}brand/logo/softmontazh-logo-ru-tight.svg" alt="Софтмонтаж" width="193" height="44">
    </a>
    <nav class="nav" aria-label="Основное меню">${navLinks("")}</nav>
    <a class="site-header__phone" href="${PHONE_HREF}">${PHONE}</a>
    <a class="btn btn--accent btn--sm" href="${WA}" target="_blank" rel="noopener">Оставить заявку</a>
    <button class="burger" type="button" aria-label="Меню" aria-expanded="false" aria-controls="mobile-menu"><span></span></button>
  </div>
  <div class="mobile-menu" id="mobile-menu">
    ${navLinks("mm-link")}
    <a class="mm-link" href="${PHONE_HREF}">${PHONE}</a>
    <a class="btn btn--accent" href="${WA}" target="_blank" rel="noopener">${ICON.chat} Написать в WhatsApp</a>
    <a class="btn btn--outline" href="${TG}" target="_blank" rel="noopener">${ICON.send} Telegram-канал</a>
  </div>`;

  const footer = `
  <div class="container">
    <div class="site-footer__grid">
      <div>
        <img src="${B}brand/logo/softmontazh-logo-ru-tight-dark.svg" alt="Софтмонтаж" width="202" height="46">
        <p>Проектирование, монтаж и обслуживание слаботочных систем в Караганде и области.</p>
        <div class="socials">
          <a href="${WA}" target="_blank" rel="noopener" aria-label="WhatsApp">${ICON.chat}</a>
          <a href="${TG}" target="_blank" rel="noopener" aria-label="Telegram-канал">${ICON.send}</a>
          <a href="${TT}" target="_blank" rel="noopener" aria-label="TikTok">${ICON.play}</a>
        </div>
      </div>
      <div>
        <h4>Разделы</h4>
        <ul>${NAV.map(([h, l]) => `<li><a href="${B}${h}">${l}</a></li>`).join("")}
          <li><a href="${ESEMER}" target="_blank" rel="noopener">Платформа Esemer</a></li></ul>
      </div>
      <div>
        <h4>Контакты</h4>
        <ul>
          <li><a href="${PHONE_HREF}">${PHONE}</a></li>
          <li><a href="mailto:${EMAIL}">${EMAIL}</a></li>
          <li>Караганда, Казахстан</li>
        </ul>
      </div>
    </div>
    <div class="site-footer__bottom">
      <span>© ${new Date().getFullYear()} ТОО «Софтмонтаж». БИН 250640009719</span>
      <span>Гарантия на выполненные работы</span>
    </div>
  </div>`;

  const h = document.getElementById("site-header");
  if (h) { h.className = "site-header"; h.innerHTML = header; }
  const f = document.getElementById("site-footer");
  if (f) { f.className = "site-footer"; f.innerHTML = footer; }

  // ссылки-заглушки на странице (data-link="wa|tg|phone|esemer")
  const MAP = { wa: WA, tg: TG, tt: TT, phone: PHONE_HREF, mail: "mailto:" + EMAIL, esemer: ESEMER };
  document.querySelectorAll("[data-link]").forEach((a) => {
    const v = MAP[a.dataset.link]; if (v) a.href = v;
    if (/^https?:/.test(v)) { a.target = "_blank"; a.rel = "noopener"; }
  });
  document.querySelectorAll("[data-icon]").forEach((el) => { el.insertAdjacentHTML("afterbegin", ICON[el.dataset.icon] || ""); });

  // мобильное меню
  const burger = document.querySelector(".burger");
  const mm = document.getElementById("mobile-menu");
  if (burger && mm) {
    burger.addEventListener("click", () => {
      const open = mm.classList.toggle("is-open");
      burger.setAttribute("aria-expanded", open);
      document.body.style.overflow = open ? "hidden" : "";
    });
  }

  // уведомление
  window.smToast = function (text) {
    let t = document.querySelector(".toast");
    if (!t) { t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = text; t.classList.add("is-show");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("is-show"), 2200);
  };
  document.querySelectorAll("[data-copy]").forEach((b) => {
    b.addEventListener("click", () => {
      const src = document.getElementById(b.dataset.copy);
      const text = src ? src.innerText.trim() : b.dataset.copy;
      navigator.clipboard.writeText(text).then(() => smToast(b.dataset.done || "Скопировано"));
    });
  });

  // просмотр сертификатов
  const certs = [...document.querySelectorAll(".cert")];
  if (certs.length) {
    const lb = document.createElement("div");
    lb.className = "lightbox"; lb.setAttribute("role", "dialog"); lb.setAttribute("aria-modal", "true");
    lb.innerHTML = '<button class="lb-close" aria-label="Закрыть">×</button><button class="lb-prev" aria-label="Предыдущий">‹</button><button class="lb-next" aria-label="Следующий">›</button><figure><img alt=""><figcaption></figcaption></figure>';
    document.body.appendChild(lb);
    let i = 0;
    const show = (k) => {
      i = (k + certs.length) % certs.length;
      const c = certs[i];
      lb.querySelector("img").src = c.dataset.full;
      lb.querySelector("img").alt = c.querySelector("b").textContent;
      lb.querySelector("figcaption").textContent = c.querySelector("b").textContent + " — " + c.querySelector("span").textContent;
      lb.classList.add("is-open");
    };
    const close = () => lb.classList.remove("is-open");
    certs.forEach((c, k) => c.addEventListener("click", () => show(k)));
    lb.querySelector(".lb-close").onclick = close;
    lb.querySelector(".lb-prev").onclick = () => show(i - 1);
    lb.querySelector(".lb-next").onclick = () => show(i + 1);
    lb.addEventListener("click", (e) => { if (e.target === lb) close(); });
    document.addEventListener("keydown", (e) => {
      if (!lb.classList.contains("is-open")) return;
      if (e.key === "Escape") close(); if (e.key === "ArrowLeft") show(i - 1); if (e.key === "ArrowRight") show(i + 1);
    });
  }
  // карточка фирмы Esemer: если виджет отрисовался — прячем запасной блок
  document.querySelectorAll(".esemer-slot").forEach((slot) => {
    const card = slot.querySelector("[data-esemer-firm]");
    if (!card) return;
    const ready = () => card.offsetHeight > 40; // виджет рисует карточку внутри (Shadow DOM) — у пустого блока высота 0
    let n = 0;
    const t = setInterval(() => {
      if (ready()) { slot.classList.add("has-card"); clearInterval(t); }
      else if (++n > 60) clearInterval(t); // ждём до 15 секунд
    }, 250);
  });
})();
