import { api } from "./api.js";
import {
  badge, dateLabel, empty, esc, field, heading, linkTo, loanBadge, option, pagination, sectionHeading, stat,
} from "./ui.js";

const sections = {
  overview: "Overview",
  books: "Books & inventory",
  topics: "Topics",
  prerequisites: "Prerequisites",
  borrowing: "Borrowing",
  progress: "Progress records",
};
const submit = label => `<button type="submit" class="button primary">${esc(label)}</button>`;
const message = '<div class="form-message" role="status"></div>';

function adminUrl(section, values = {}) {
  return "/admin?" + new URLSearchParams({ section, ...values });
}

function table(headers, rows) {
  return `<div class="panel table-wrap"><table>
    <thead><tr>${headers.map(label => `<th scope="col">${esc(label)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(cells => `<tr>${cells.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
}

function render(ctx, section, description, body) {
  const tabs = Object.entries(sections).map(([key, label]) =>
    `<a class="button secondary compact" href="${adminUrl(key)}"${key === section ? ' aria-current="page"' : ""}>${label}</a>`,
  ).join("");
  ctx.render(`${heading("Administration", description)}
    <nav class="tabs" aria-label="Administration sections">${tabs}</nav><div class="stack">${body}</div>`);
}

function input(name, value, extra = "") {
  return `<input name="${name}" value="${esc(value)}" ${extra}>`;
}

function textarea(name, value) {
  return `<textarea name="${name}" maxlength="10000" rows="4" required>${esc(value)}</textarea>`;
}

async function overview(ctx) {
  const stats = await api("/admin/stats");
  render(ctx, "overview", "Monitor catalog inventory, borrowing, and pathway activity.", `
    <div class="stats">
      ${stat("Catalog titles", stats.books, "library", `${stats.available_copies} of ${stats.total_copies} copies available`)}
      ${stat("Current loans", stats.issued, "clock", `${stats.overdue} overdue`, stats.overdue ? "warm" : "")}
      ${stat("Student accounts", stats.students, "user", `${stats.reviews} book reviews`)}
      ${stat("Study pathways", stats.pathways, "path", `${stats.completed_pathways} completed`)}
    </div>
    <section class="panel pad">
      ${sectionHeading("Learning records", "", linkTo(adminUrl("progress"), "Inspect progress"))}
      <ul class="activity">
        <li><strong>${esc(stats.topics)}</strong><span>Academic topics</span></li>
        <li><strong>${esc(stats.ledger_entries)}</strong><span>Recorded completion events</span></li>
      </ul>
    </section>`);
}

function bookForm(book, topics) {
  const linked = new Set((book.topics || []).map(topic => topic.topic_id));
  const topicChoices = topics.map(topic => `<option value="${Number(topic.topic_id)}"${linked.has(topic.topic_id) ? " selected" : ""}>
    ${esc(topic.name)} · ${esc(topic.subject)}
  </option>`).join("");
  return `<section class="panel pad" aria-labelledby="book-editor">
    <h2 id="book-editor">${book.book_id ? "Edit catalog book" : "Add a catalog book"}</h2>
    <form id="admin-book-form" class="form">
      <div class="form-grid">
        ${field("Title", input("title", book.title, 'maxlength="255" required'))}
        ${field("Author", input("author", book.author, 'maxlength="255" required'))}
        ${field("Publisher", input("publisher", book.publisher, 'maxlength="255"'))}
        ${field("ISBN", input("isbn", book.isbn, 'maxlength="20"'))}
        ${field("Category", input("category", book.category, 'maxlength="100"'))}
        ${field("Total copies", input("total_copies", book.total_copies ?? 0, 'type="number" min="0" max="2147483647" required'))}
        ${field("Description", textarea("description", book.description), "wide")}
        ${field("Cover image URL (optional)", input("cover_url", book.cover_url, 'type="url" maxlength="1000" placeholder="https://"'), "wide")}
        ${field("Academic topics", `<select name="topic_ids" size="6" multiple aria-describedby="book-topic-help">${topicChoices}</select>
          <small id="book-topic-help">Hold Ctrl or Command to select multiple topics.</small>`, "wide")}
      </div>
      ${message}
      <div class="actions">${submit(book.book_id ? "Save book" : "Add book")} ${linkTo(adminUrl("books"), "Cancel", "", "button secondary")}</div>
    </form>
  </section>`;
}

async function catalogAdmin(ctx) {
  const editId = ctx.query.get("book");
  if (editId) {
    const [book, { topics }] = await Promise.all([
      editId === "new" ? Promise.resolve({}) : api(`/books/${Number(editId)}`),
      api("/topics"),
    ]);
    render(ctx, "books", "Edit bibliographic details, copy counts, and academic topic mappings.", bookForm(book, topics));
    ctx.form("admin-book-form", async values => {
      const body = Object.fromEntries(values);
      body.total_copies = Number(values.get("total_copies"));
      body.topic_ids = values.getAll("topic_ids").map(Number);
      await api(book.book_id ? `/admin/books/${book.book_id}` : "/admin/books", {
        method: book.book_id ? "PUT" : "POST", body,
      });
      ctx.notice(book.book_id ? "Book and inventory updated." : "Book added to the catalog.");
      ctx.go(adminUrl("books"));
    });
    return;
  }
  const q = ctx.query.get("q") || "";
  const page = Number(ctx.query.get("page")) || 1;
  const catalog = await api(`/books?${new URLSearchParams({ q, page, per_page: 15 })}`);
  const rows = catalog.items.map(book => [
    `${linkTo(`/books/${book.book_id}`, book.title, "")}<div class="muted small">${esc(book.author)}</div>`,
    esc(book.category || "—"), esc(book.available_copies), esc(book.total_copies),
    linkTo(adminUrl("books", { book: book.book_id }), "Edit", "", "button secondary compact"),
  ]);
  render(ctx, "books", "Add titles, update copy counts, and manage topic associations.", `
    <section class="panel pad">
      ${sectionHeading("Catalog inventory", `${catalog.total} titles`,
        linkTo(adminUrl("books", { book: "new" }), "Add book", "plus", "button primary"))}
      <form id="admin-book-search" class="form-grid">
        ${field("Search inventory", input("q", q, 'type="search" maxlength="150" placeholder="Title, author, or topic"'))}
        <div class="actions">${submit("Search")}</div>
      </form>
    </section>
    ${rows.length ? table(["Book", "Category", "Available", "Total copies", "Manage"], rows)
      : empty("No matching books", "Try another title, author, or topic.")}
    ${pagination(catalog.page, catalog.pages, next => adminUrl("books", { q, page: next }))}`);
  ctx.form("admin-book-search", values => ctx.go(adminUrl("books", { q: String(values.get("q")).trim() })));
}

async function topicAdmin(ctx) {
  const editId = ctx.query.get("topic");
  const { topics } = await api("/topics");
  if (editId) {
    const topic = editId === "new" ? {} : topics.find(row => row.topic_id === Number(editId));
    if (!topic) {
      render(ctx, "topics", "", empty("Topic unavailable", "Choose a topic from the catalog.",
        linkTo(adminUrl("topics"), "View topics", "back"), "path"));
      return;
    }
    const choices = ["Beginner", "Intermediate", "Advanced"]
      .map(level => option(level, level, topic.difficulty_level)).join("");
    render(ctx, "topics", "Academic topics are shared across the catalog and study pathways.", `
      <section class="panel pad">
        ${sectionHeading(topic.topic_id ? "Edit topic" : "Add topic")}
        <form id="admin-topic-form" class="form">
          <div class="form-grid">
            ${field("Name", input("name", topic.name, 'maxlength="150" required'))}
            ${field("Subject", input("subject", topic.subject, 'maxlength="100" required'))}
            ${field("Difficulty", `<select name="difficulty_level">${choices}</select>`)}
            ${field("Description", textarea("description", topic.description), "wide")}
          </div>
          ${message}<div class="actions">${submit("Save topic")} ${linkTo(adminUrl("topics"), "Cancel", "", "button secondary")}</div>
        </form>
      </section>`);
    ctx.form("admin-topic-form", async values => {
      await api(topic.topic_id ? `/admin/topics/${topic.topic_id}` : "/admin/topics", {
        method: topic.topic_id ? "PUT" : "POST", body: Object.fromEntries(values),
      });
      ctx.notice("Topic saved.");
      ctx.go(adminUrl("topics"));
    });
    return;
  }
  const rows = topics.map(topic => [
    `<strong>${esc(topic.name)}</strong>`, esc(topic.subject), badge(topic.difficulty_level, "neutral"),
    esc(topic.books.length), linkTo(adminUrl("topics", { topic: topic.topic_id }), "Edit", "", "button secondary compact"),
  ]);
  render(ctx, "topics", "Maintain the concepts students can select for their pathways.", `
    ${sectionHeading("Academic topic catalog", `${topics.length} topics`,
      linkTo(adminUrl("topics", { topic: "new" }), "Add topic", "plus", "button primary"))}
    ${rows.length ? table(["Topic", "Subject", "Difficulty", "Related books", "Manage"], rows)
      : empty("No academic topics", "Add a topic to organize catalog books and build pathways.", "", "path")}`);
}

async function prerequisiteAdmin(ctx) {
  const { topics } = await api("/topics");
  const choices = option("", "Select a topic", "") + topics.map(topic =>
    option(topic.topic_id, `${topic.name} · ${topic.subject}`),
  ).join("");
  const rows = topics.flatMap(topic => topic.prerequisites.map(prerequisite => [
    esc(prerequisite.name), esc(topic.name),
    `<button class="button secondary compact" data-action="remove-prerequisite"
      data-prerequisite="${Number(prerequisite.topic_id)}" data-dependent="${Number(topic.topic_id)}"
      aria-label="Remove ${esc(prerequisite.name)} as a prerequisite for ${esc(topic.name)}">Remove</button>`,
  ]));
  render(ctx, "prerequisites", "Set which topics students must complete before moving to a dependent topic.", `
    <section class="panel pad">
      ${sectionHeading("Add a prerequisite")}
      <form id="admin-prerequisite-form" class="form">
        <div class="form-grid">
          ${field("Prerequisite topic", `<select name="prerequisite_topic_id" required>${choices}</select>`)}
          ${field("Dependent topic", `<select name="dependent_topic_id" required>${choices}</select>`)}
        </div>
        ${message}<div>${submit("Add prerequisite")}</div>
      </form>
    </section>
    ${rows.length ? table(["Prerequisite", "Dependent topic", "Manage"], rows)
      : empty("No prerequisite relationships", "Link two academic topics to set a required study order.", "", "path")}`);
  ctx.form("admin-prerequisite-form", async values => {
    await api("/admin/prerequisites", {
      method: "POST", body: {
        prerequisite_topic_id: Number(values.get("prerequisite_topic_id")),
        dependent_topic_id: Number(values.get("dependent_topic_id")),
      },
    });
    ctx.notice("Prerequisite added.");
    ctx.refresh();
  });
  ctx.actions("remove-prerequisite", async ({ prerequisite, dependent }) => {
    await api(`/admin/prerequisites/${prerequisite}/${dependent}`, { method: "DELETE" });
    ctx.notice("Prerequisite removed.");
    ctx.refresh();
  });
}

async function borrowingAdmin(ctx) {
  const status = ctx.query.get("status") || "all";
  const page = Number(ctx.query.get("page")) || 1;
  const data = await api(`/admin/borrows?${new URLSearchParams({ status, page })}`);
  const choices = ["all", "issued", "overdue", "returned"].map(key => option(
    key, key === "all" ? "All statuses" : key.charAt(0).toUpperCase() + key.slice(1), status,
  )).join("");
  const rows = data.items.map(loan => [
    esc(loan.student), linkTo(`/books/${loan.book_id}`, loan.title, ""), dateLabel(loan.issue_date),
    dateLabel(loan.due_date), dateLabel(loan.return_date), loanBadge(loan),
    loan.status === "returned" ? "—" : `<button class="button secondary compact" data-action="staff-return"
      data-id="${Number(loan.borrow_id)}">Record return</button>`,
  ]);
  render(ctx, "borrowing", "Inspect active and historic loans and record returns.", `
    <section class="panel pad">
      <form id="admin-borrowing-filter" class="form-grid">
        ${field("Loan status", `<select name="status">${choices}</select>`)}
        <div class="actions">${submit("Apply filter")}</div>
      </form>
    </section>
    ${rows.length ? table(["Student", "Book", "Issued", "Due", "Returned", "Status", "Action"], rows)
      : empty("No matching loans", "Select another status to review borrowing activity.", "", "clock")}
    ${pagination(data.page, data.pages, next => adminUrl("borrowing", { status, page: next }))}`);
  ctx.form("admin-borrowing-filter", values => ctx.go(adminUrl("borrowing", { status: values.get("status") })));
  ctx.actions("staff-return", async ({ id }) => {
    await api(`/borrows/${id}/return`, { method: "POST" });
    ctx.notice("Book returned and inventory updated.");
    ctx.refresh();
  });
}

async function progressAdmin(ctx) {
  const { pathway_rows: pathways } = await api("/admin/stats");
  const rows = pathways.map(pathway => [
    `<strong>${esc(pathway.name)}</strong>`, esc(pathway.student),
    badge(pathway.status === "completed" ? "Completed" : "Active", pathway.status === "completed" ? "" : "neutral"),
    `${esc(pathway.completed_steps)} / ${esc(pathway.total_steps)}`,
    linkTo(`/pathways/${pathway.pathway_id}/verify`, "Inspect ledger", "shield", "button secondary compact"),
  ]);
  render(ctx, "progress", "Inspect completion records and verify their hash links.", rows.length
    ? table(["Pathway", "Student", "Status", "Steps completed", "Verification"], rows)
    : empty("No study pathways", "Student pathways and their progress will appear here.", "", "path"));
}

export async function adminView(ctx) {
  if (ctx.user.role !== "admin") {
    ctx.render(empty("Administrator access required", "This section is available to library administrators.",
      linkTo("/dashboard", "Back to overview", "back"), "lock"));
    return;
  }
  const renderer = new Map([
    ["overview", overview], ["books", catalogAdmin], ["topics", topicAdmin],
    ["prerequisites", prerequisiteAdmin], ["borrowing", borrowingAdmin], ["progress", progressAdmin],
  ]).get(ctx.query.get("section")) || overview;
  await renderer(ctx);
}
