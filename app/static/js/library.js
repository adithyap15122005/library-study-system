import { api } from "./api.js";
import { badge, bookArt, bookCard, dateLabel, empty, esc, field, heading, icon, initials, linkTo, loanBadge, option, pagination, rating, sectionHeading, stock } from "./ui.js";

function catalogUrl(params) {
  const query = params.toString();
  return `/catalog${query ? `?${query}` : ""}`;
}

async function catalog(ctx) {
  const params = ctx.query;
  const query = new URLSearchParams(params);
  query.set("per_page", "12");
  const data = await api(`/books?${query}`);
  const { items, categories, subjects, total, page, pages } = data;
  const optionList = (name, options) => options.map(value => option(value, value, params.get(name))).join("");
  ctx.render(`${heading("Library catalog", "Find books by title, author, or the topics you want to learn.")}
    <form class="panel filters" id="catalog-form" role="search">
      ${field("Search", `<input type="search" name="q" value="${esc(params.get("q"))}" placeholder="Title, author, or topic" maxlength="120">`)}
      ${field("Category", `<select name="category"><option value="">All categories</option>${optionList("category", categories)}</select>`)}
      ${field("Subject", `<select name="subject"><option value="">All subjects</option>${optionList("subject", subjects)}</select>`)}
      ${field("Availability", `<select name="availability"><option value="">All copies</option>${option("available", "Available now", params.get("availability"))}${option("unavailable", "Unavailable", params.get("availability"))}</select>`)}
      ${field("Sort", `<select name="sort">${[["", "Default order"], ["title", "Title"], ["author", "Author"], ["available", "Most available"], ["rating", "Highest rated"], ["relevance", "Relevance"]].map(([value, label]) => option(value, label, params.get("sort"))).join("")}</select>`)}
      <button type="submit" class="button primary">${icon("search", true)} Search</button>
    </form>
    <div class="actions filter-row"><p class="muted small">${total} ${total === 1 ? "book" : "books"}${params.get("q") ? ` matching “${esc(params.get("q"))}”` : ""}</p>
      ${["q", "category", "subject", "availability", "sort"].some(key => params.get(key)) ? linkTo("/catalog", "Clear filters", "") : ""}</div>
    ${items.length ? `<div class="book-grid">${items.map(book => bookCard(book)).join("")}</div>` : empty("No books match these filters", "Try a different search term or broaden your filters.", linkTo("/catalog", "Clear filters", ""), "search")}
    ${pagination(page, pages, next => {
      const updated = new URLSearchParams(params);
      updated.set("page", next);
      return catalogUrl(updated);
    })}`);
  ctx.form("catalog-form", async values => {
    const selected = new URLSearchParams();
    for (const [key, value] of values) if (value.trim()) selected.set(key, value.trim());
    ctx.go(catalogUrl(selected));
  });
}

async function details(ctx) {
  const [book, data] = await Promise.all([api(`/books/${ctx.params[0]}`), api(`/books/${ctx.params[0]}/reviews`)]);
  const reviews = data.items;
  const mine = reviews.find(review => review.user_id === ctx.user.user_id);
  const topics = book.topics || [];
  const related = book.related_books || [];
  const student = ctx.user.role === "student";
  document.title = `${book.title} · Folio`;
  ctx.render(`<div class="back-link">${linkTo("/catalog", "Library catalog", "back")}</div>
    <article class="panel pad book-info">
      ${bookArt(book, true)}
      <div>${book.category ? `<div class="eyebrow">${esc(book.category)}</div>` : ""}
        <h1>${esc(book.title)}</h1><div class="muted">By ${esc(book.author)}</div>
        <div class="meta">${rating(book)} ${book.publisher ? `<span>${esc(book.publisher)}</span>` : ""} ${book.isbn ? `<span>ISBN ${esc(book.isbn)}</span>` : ""}</div>
        <p class="description">${esc(book.description)}</p>
        ${topics.length ? `<div class="tags">${topics.map(topic => `<a aria-label="Search catalog for ${esc(topic.name)}" href="/catalog?q=${encodeURIComponent(topic.name)}">${badge(topic.name, "neutral")}</a>`).join("")}</div>` : ""}
        <div class="section actions">${stock(book)}<span class="small muted">${book.total_copies} total ${book.total_copies === 1 ? "copy" : "copies"}</span>
        ${student ? `<button class="button primary" type="button" data-action="borrow" ${book.available_copies < 1 ? "disabled" : ""}>${icon("book", true)} Borrow a copy</button>` : ""}</div>
      </div>
    </article>
    <div class="${student ? "split" : ""} section">
      <section class="panel pad">${sectionHeading("Reviews", `${book.review_count} ${book.review_count === 1 ? "review" : "reviews"}`)}
        ${reviews.length ? `<ul class="review-list">${reviews.map(review => `<li>
          <span class="avatar">${initials(review.author)}</span><div><strong>${esc(review.author)}</strong>
          <div class="small muted">${dateLabel(review.timestamp, true)}</div>${review.review_text ? `<p class="review-text">${esc(review.review_text)}</p>` : ""}</div>
          <span class="rating">${icon("star", true)} ${esc(review.rating)}/5</span></li>`).join("")}</ul>` : empty("No reviews yet", "Reviews from readers will appear here.", "", "star")}
      </section>
      ${student ? `<section class="panel pad">${sectionHeading(mine ? "Edit your review" : "Write a review")}
        <form class="form" id="review-form">
          ${field("Rating", `<select name="rating" required><option value="">Choose a rating</option>${[5, 4, 3, 2, 1].map(value => option(value, `${value} ${value === 1 ? "star" : "stars"}`, mine?.rating)).join("")}</select>`)}
          ${field("Review", `<textarea name="review_text" maxlength="2000" placeholder="Which readers would benefit from this book?">${esc(mine?.review_text)}</textarea>`)}
          <div class="form-message" role="alert"></div><div><button type="submit" class="button primary">${mine ? "Save review" : "Post review"}</button></div>
        </form>
      </section>` : ""}
    </div>
    ${related.length ? `<section class="section">${sectionHeading("Related books")}<div class="book-grid">${related.slice(0, 4).map(item => bookCard(item)).join("")}</div></section>` : ""}`);
  ctx.actions("borrow", async () => {
    await api("/borrows", { method: "POST", body: { book_id: book.book_id } });
    ctx.notice("Book borrowed. See your due date in My borrowings.");
    ctx.refresh();
  });
  ctx.form("review-form", async values => {
    const body = { review_text: values.get("review_text"), rating: Number(values.get("rating")) };
    await api(`/books/${book.book_id}/reviews${mine ? "/me" : ""}`, { method: mine ? "PUT" : "POST", body });
    ctx.notice("Review saved.");
    ctx.refresh();
  });
}

function loanTable(loans, active) {
  return `<div class="panel table-wrap"><table>
    <thead><tr><th scope="col">Book</th><th scope="col">Issued</th><th scope="col">Due</th>${active ? "" : '<th scope="col">Returned</th>'}<th scope="col">Status</th>${active ? '<th scope="col">Action</th>' : ""}</tr></thead>
    <tbody>${loans.map(loan => `<tr><td><strong><a href="/books/${Number(loan.book_id)}">${esc(loan.title)}</a></strong><div class="muted">${esc(loan.author)}</div></td>
      <td>${dateLabel(loan.issue_date)}</td><td>${dateLabel(loan.due_date)}</td>${active ? "" : `<td>${dateLabel(loan.return_date)}</td>`}<td>${loanBadge(loan)}</td>
      ${active ? `<td><button class="button secondary compact" type="button" data-action="return-book" data-id="${Number(loan.borrow_id)}">Return book</button></td>` : ""}</tr>`).join("")}</tbody>
  </table></div>`;
}

async function borrowing(ctx) {
  const { items } = await api("/borrows/me");
  const active = items.filter(loan => loan.status !== "returned");
  const returned = items.filter(loan => loan.status === "returned");
  ctx.render(`${heading("My borrowings", "Check due dates, return books, and see your borrowing history.", "", linkTo("/catalog", "Browse catalog", "arrow", "button secondary"))}
    <section>${sectionHeading("Currently issued", `${active.length} active ${active.length === 1 ? "loan" : "loans"}`)}
      ${active.length ? loanTable(active, true) : empty("No active loans", "An available book can be borrowed from its details page.", linkTo("/catalog", "Find a book"), "clock")}
    </section>
    <section class="section">${sectionHeading("Borrowing history")}
      ${returned.length ? loanTable(returned, false) : empty("No returned books", "Returned copies will appear in your history.")}
    </section>`);
  ctx.actions("return-book", async ({ id }) => {
    await api(`/borrows/${Number(id)}/return`, { method: "POST" });
    ctx.notice("Book returned. The copy is available in the catalog.");
    ctx.refresh();
  });
}

export async function libraryView(path, ctx) {
  if (path === "/catalog") await catalog(ctx);
  else if (path === "/borrowing") await borrowing(ctx);
  else await details(ctx);
}
