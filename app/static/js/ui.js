const paths = {
  arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  back: '<path d="M20 12H5m6-6-6 6 6 6"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  book: '<path d="M12 7C9 4 5 4 2.5 5v14c3-1 6.5-1 9.5 2 3-3 6.5-3 9.5-2V5C19 4 15 4 12 7Zm0 0v14"/>',
  library: '<path d="M3 4h3v15H3zm6 0h3v15H9zm6.5.5 2.8-.7 3.7 14.6-3 .8z"/>',
  layout: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18m-12 0v12"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  spark: '<path d="M12 2.5 14.5 9.5 21.5 12l-7 2.5-2.5 7-2.5-7-7-2.5 7-2.5L12 2.5Zm6.5 1v4m-2-2h4"/>',
  path: '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M8 5h6a4 4 0 0 1 0 8h-4a3 3 0 0 0 0 6h6"/>',
  shield: '<path d="M12 22s8-3.5 8-11V5l-8-3-8 3v6c0 7.5 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  user: '<circle cx="12" cy="8" r="3.5"/><path d="M4.5 20c0-3.2 3.1-5.5 7.5-5.5s7.5 2.3 7.5 5.5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="M10.4 4.5 3 17.5A1.5 1.5 0 0 0 4.3 20h15.4a1.5 1.5 0 0 0 1.3-2.5l-7.4-13a1.8 1.8 0 0 0-3.2 0Z"/><path d="M12 9v4.5m0 3.5h.01"/>',
  star: '<path d="m12 3 2.8 5.6 6.2.9-4.5 4.4 1.1 6.1-5.6-2.9-5.6 2.9 1.1-6.1L3 9.5l6.2-.9L12 3Z"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5m-4 4v2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  refresh: '<path d="M19.5 11a7.5 7.5 0 0 0-12.8-5L4 9m0-4v4h4m-3.5 4a7.5 7.5 0 0 0 12.8 5l2.7-3m0 4v-4h-4"/>',
  logout: '<path d="M10 5H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h5m4-11 4 4-4 4m-6-4h12"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
};

export function icon(name, small = false) {
  return `<svg class="ico${small ? " sm" : ""}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${paths[name] || ""}</svg>`;
}

const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => entities[character]);
}

export function logo(path = "/") {
  return `<a class="brand" href="${path}"><img src="/static/images/folio.svg" alt=""><span><strong>Folio</strong><small>Academic library</small></span></a>`;
}

export function initials(name) {
  return esc(String(name ?? "").trim().split(/\s+/).slice(0, 2).map(word => word.charAt(0).toUpperCase()).join(""));
}

export function heading(title, description, eyebrow = "", action = "") {
  return `<header class="page-head"><div>${eyebrow ? `<div class="eyebrow">${esc(eyebrow)}</div>` : ""}<h1>${esc(title)}</h1>${description ? `<p>${esc(description)}</p>` : ""}</div>${action}</header>`;
}

export function sectionHeading(title, description = "", action = "") {
  return `<header class="section-head"><div><h2>${esc(title)}</h2>${description ? `<p>${esc(description)}</p>` : ""}</div>${action}</header>`;
}

export function linkTo(path, label, arrow = "arrow", type = "inline-link") {
  return `<a class="${type}" href="${esc(path)}">${arrow === "back" ? icon(arrow, true) : ""}${esc(label)}${arrow && arrow !== "back" ? icon(arrow, true) : ""}</a>`;
}

export function badge(label, tone = "", image = "") {
  return `<span class="badge ${tone}">${image ? icon(image, true) : ""}${esc(label)}</span>`;
}

export function empty(title, description, action = "", image = "book") {
  return `<div class="empty"><span class="icon-frame">${icon(image)}</span><strong>${esc(title)}</strong><p>${esc(description)}</p>${action}</div>`;
}

export function stat(label, value, image, note = "", tone = "") {
  return `<article class="stat"><div class="stat-header"><span>${esc(label)}</span><span class="icon-frame ${tone}">${icon(image)}</span></div><strong>${esc(value)}</strong>${note ? `<small>${esc(note)}</small>` : ""}</article>`;
}

export function field(label, control, cls = "") {
  return `<label class="field ${cls}"><span>${esc(label)}</span>${control}</label>`;
}

export function option(value, label, selected) {
  return `<option value="${esc(value)}"${String(value) === String(selected ?? "") ? " selected" : ""}>${esc(label)}</option>`;
}

export function dateLabel(value, includeTime = false) {
  if (!value) return "—";
  const text = String(value);
  const normalized = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(text) ? text.replace(" ", "T") + "Z" : text;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    ...(includeTime ? { timeStyle: "short" } : {}),
  }).format(date);
}

function coverSource(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:") return parsed.href;
  } catch {
    return "";
  }
  return "";
}

export function bookArt(book, large = false) {
  const tone = ((Number(book.book_id) || 0) % 7) + 1;
  const image = coverSource(book.cover_url);
  return `<div class="book-stage tone-${tone}${large ? " large" : ""}" aria-hidden="true">
    <div class="book-cover">
      <span class="book-art-tag">${esc(book.category || "Folio Library")}</span>
      <span class="book-art-title">${esc(book.title)}</span>
      <span class="book-art-author">${esc(book.author)}</span>
      ${image ? `<img src="${esc(image)}" alt="" loading="lazy" data-optional-cover referrerpolicy="no-referrer">` : ""}
    </div>
  </div>`;
}

export function stock(book) {
  const available = Number(book.available_copies) || 0;
  return badge(`${available} available`, available > 0 ? "" : "neutral");
}

export function rating(book) {
  if (book.average_rating == null) return '<span class="muted small">Unrated</span>';
  return `<span class="rating" aria-label="${esc(book.average_rating)} out of 5 stars">${icon("star", true)} ${Number(book.average_rating).toFixed(1)}${book.review_count ? ` <span class="muted">(${esc(book.review_count)})</span>` : ""}</span>`;
}

export function bookCard(book, recommendation) {
  const href = `/books/${Number(book.book_id)}`;
  const topics = (book.topics || []).slice(0, 3);
  return `<article class="book-card">
    <a href="${href}" aria-label="${esc(book.title)}">${bookArt(book)}</a>
    <div class="book-card-body">
      ${book.category ? `<div class="eyebrow">${esc(book.category)}</div>` : ""}
      <h3><a href="${href}">${esc(book.title)}</a></h3>
      <p class="author">${esc(book.author)}</p>
      <div class="book-card-foot">${stock(book)} ${recommendation ? badge(`${Math.round(Number(recommendation.score) * 100)}% match`, "score", "spark") : rating(book)}</div>
      ${recommendation ? `<p class="score-detail">${esc(recommendation.reason)}</p>${topics.length ? `<div class="tags">${topics.map(topic => badge(topic.name, "neutral")).join("")}</div>` : ""}` : ""}
    </div>
  </article>`;
}

export function progress(pathway) {
  return `<div class="progress-row"><progress max="100" value="${Number(pathway.progress_percent) || 0}" aria-label="Pathway progress"></progress><strong>${Number(pathway.progress_percent) || 0}%</strong></div>`;
}

export function loanBadge(loan) {
  if (loan.status === "overdue") return badge("Overdue", "error", "alert");
  if (loan.status === "returned") return badge("Returned", "neutral", "check");
  return badge("Issued");
}

export function pagination(page, pages, url) {
  if (pages < 2) return "";
  return `<nav class="pagination" aria-label="Pagination">
    ${page > 1 ? linkTo(url(page - 1), "Previous", "back", "button secondary compact") : ""}
    <span>Page ${esc(page)} of ${esc(pages)}</span>
    ${page < pages ? linkTo(url(page + 1), "Next", "arrow", "button secondary compact") : ""}
  </nav>`;
}
