/* Софтмонтаж — редактор шаблона КП: живой предпросмотр (лист рисует сервер), сохранение, логотип */
(() => {
  const T = window.KP_TEMPLATE;
  const $ = (id) => document.getElementById(id);
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
  const post = (url, body, isForm) => fetch(url, {
    method: "POST", credentials: "same-origin",
    headers: isForm ? { "X-CSRFToken": csrf() } : { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    body: isForm ? body : JSON.stringify(body),
  });
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const FIELDS = ["name", "is_default", "company", "slogan", "contacts", "header", "theme", "custom_color", "footer", "view_mode", "hide_prices"];
  const pick = (o) => JSON.parse(JSON.stringify(Object.fromEntries(FIELDS.map((k) => [k, o[k]]))));
  let saved = pick(T), st = pick(T);

  // --- предпросмотр: масштаб листа под ширину колонки ---
  const frame = $("sheet"), scale = $("pvScale");
  function fit() {
    const w = $("pv").clientWidth - 36;
    const k = Math.min(1, w / 794);
    scale.style.transform = `scale(${k})`;
    scale.style.marginLeft = scale.style.marginRight = k < 1 ? `${(w - 794) / 2}px` : "auto";
    try { frame.style.height = Math.max(1123, frame.contentDocument.documentElement.scrollHeight) + "px"; } catch (e) { /* ещё грузится */ }
    scale.style.height = (parseFloat(frame.style.height || 1123) * k) + "px";
    $("pv").style.height = (parseFloat(frame.style.height || 1123) * k + 36) + "px";
  }
  frame.addEventListener("load", fit);
  window.addEventListener("resize", fit);
  let t, req = 0;
  function refresh() {
    clearTimeout(t);
    t = setTimeout(async () => {
      const my = ++req;
      const r = await post(`/kp/api/templates/${T.id}/preview`, st);
      if (my === req && r.ok) frame.srcdoc = await r.text();
    }, 250);
  }

  // --- поля ---
  function bindSeg(group) {
    const box = document.querySelector(`[data-group="${group}"]`);
    const paint = () => box.querySelectorAll("button").forEach((b) => b.classList.toggle("is-on", b.dataset.v === st[group]));
    box.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b || e.target.type === "color") return; st[group] = b.dataset.v; paint(); changed(); });
    paint();
    return paint;
  }
  const paints = ["view_mode", "header", "theme"].map(bindSeg);
  const vmHint = () => { $("vmHint").textContent = st.view_mode === "full" ? "Полная спецификация: фото, модели, описания" : "Только названия, количество и цены — без фото и описаний"; };

  function lines(boxId, key, withLabel) {
    const box = $(boxId);
    box.innerHTML = st[key].map((v, i) => `<div class="kp-line">
      ${withLabel ? `<input class="kp-input lbl" data-i="${i}" data-f="label" value="${esc(v.label)}" placeholder="Название">` : ""}
      <input class="kp-input" data-i="${i}" data-f="${withLabel ? "value" : ""}" value="${esc(withLabel ? v.value : v)}" placeholder="${withLabel ? "Значение" : "Строка подвала"}">
      <button type="button" class="kp-del" data-i="${i}" title="Удалить">×</button></div>`).join("");
  }
  function bindLines(boxId, key, withLabel, addId, blank) {
    const box = $(boxId);
    box.addEventListener("input", (e) => {
      const i = +e.target.dataset.i; if (Number.isNaN(i)) return;
      if (withLabel) st[key][i][e.target.dataset.f] = e.target.value; else st[key][i] = e.target.value;
      changed();
    });
    box.addEventListener("click", (e) => { const d = e.target.closest(".kp-del"); if (!d) return; st[key].splice(+d.dataset.i, 1); lines(boxId, key, withLabel); changed(); });
    $(addId).addEventListener("click", () => { st[key].push(blank()); lines(boxId, key, withLabel); changed(); box.querySelector(".kp-line:last-child input")?.focus(); });
  }
  bindLines("contacts", "contacts", true, "addContact", () => ({ label: "", value: "" }));
  bindLines("footer", "footer", false, "addFooter", () => "");

  ["name", "company", "slogan"].forEach((k) => $(k).addEventListener("input", (e) => { st[k] = e.target.value; changed(); }));
  $("hide_prices").addEventListener("change", (e) => { st.hide_prices = e.target.checked; changed(); });
  $("is_default").addEventListener("change", (e) => { st.is_default = e.target.checked; changed(); });
  $("custom_color").addEventListener("input", (e) => { st.custom_color = e.target.value; st.theme = "custom"; paints[2](); changed(); });

  function fill() {
    ["name", "company", "slogan"].forEach((k) => { $(k).value = st[k] || ""; });
    $("hide_prices").checked = !!st.hide_prices;
    $("is_default").checked = !!st.is_default;
    $("custom_color").value = st.custom_color || "#2E3A8C";
    lines("contacts", "contacts", true); lines("footer", "footer", false);
    paints.forEach((p) => p()); vmHint();
    $("logoImg").src = T.logo;
  }

  const dirty = () => JSON.stringify(st) !== JSON.stringify(saved);
  function changed() {
    vmHint();
    const d = dirty();
    $("saveBtn").disabled = !d || !T.editable; $("cancelBtn").disabled = !d;
    $("saveState").textContent = !T.editable ? "Шаблон фирмы — только просмотр. Сделайте копию, чтобы менять." : d ? "Есть несохранённые изменения" : "Нет изменений для сохранения";
    refresh();
  }

  $("saveBtn").addEventListener("click", async () => {
    $("saveBtn").disabled = true;
    const r = await post(`/kp/api/templates/${T.id}/save`, st);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { alert(d.error || "Не сохранилось"); changed(); return; }
    saved = JSON.parse(JSON.stringify(st)); changed();
    $("saveState").textContent = "Сохранено";
  });
  $("cancelBtn").addEventListener("click", () => { st = JSON.parse(JSON.stringify(saved)); fill(); changed(); });
  $("tplSelect").addEventListener("change", (e) => {
    if (dirty() && !confirm("Есть несохранённые изменения. Перейти к другому шаблону без сохранения?")) { e.target.value = T.id; return; }
    location.href = `/kp/templates/${e.target.value}/`;
  });
  $("copyBtn").addEventListener("click", async () => {
    const r = await post(`/kp/api/templates/${T.id}/copy`, {}); const d = await r.json();
    if (d.id) location.href = `/kp/templates/${d.id}/`;
  });
  $("delBtn").addEventListener("click", async () => {
    if (!confirm(`Удалить шаблон «${saved.name}»?`)) return;
    const r = await post(`/kp/api/templates/${T.id}/delete`, {}); const d = await r.json().catch(() => ({}));
    if (!r.ok) { alert(d.error || "Не удалось удалить"); return; }
    location.href = "/kp/";
  });
  $("logoFile").addEventListener("change", async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("logo", f);
    const r = await post(`/kp/api/templates/${T.id}/logo`, fd, true); const d = await r.json().catch(() => ({}));
    if (!r.ok) { alert(d.error || "Не загрузилось"); return; }
    T.logo = d.logo; $("logoImg").src = d.logo; refresh(); e.target.value = "";
  });
  $("logoDel").addEventListener("click", async () => {
    const fd = new FormData(); fd.append("remove", "1");
    const r = await post(`/kp/api/templates/${T.id}/logo`, fd, true); const d = await r.json().catch(() => ({}));
    if (r.ok) { T.logo = d.logo; $("logoImg").src = d.logo; refresh(); }
  });
  window.addEventListener("beforeunload", (e) => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });

  if (!T.editable) { $("panel").classList.add("kp-ro"); $("roNote").hidden = false; $("delBtn").hidden = true; document.querySelectorAll("#logoFile, #logoDel").forEach((x) => (x.closest("label") || x).style.display = "none"); }
  if (!T.firm) $("defaultRow").hidden = true;
  fill(); changed(); setTimeout(fit, 50);
})();
