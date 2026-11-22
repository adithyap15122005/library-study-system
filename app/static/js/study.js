import { api } from "./api.js";
import { badge, bookCard, dateLabel, empty, esc, field, heading, icon, linkTo, option, progress, sectionHeading } from "./ui.js";

function recommendationUrl(topicId) {
  return `/recommendations${topicId ? `?topic_id=${Number(topicId)}` : ""}`;
}

async function recommendations(ctx) {
  const topicId = ctx.query.get("topic_id") || "";
  const [catalog, data] = await Promise.all([
    api("/topics"),
    api(`/recommendations/me${topicId ? `?topic_id=${encodeURIComponent(topicId)}` : ""}`),
  ]);
  const items = data.recommendations;
  const chosen = catalog.topics.find(topic => topic.topic_id === Number(topicId));
  ctx.render(`${heading("Book recommendations", "Discover books based on your interests, active study topics, or a topic you choose.")}
    <section class="panel pad">
      <form id="recommend-form" class="form">
        <div class="recommend-toolbar">
          ${field("Recommendation focus", `<select name="topic_id"><option value="">My interests and study activity</option>${catalog.topics.map(topic => option(topic.topic_id, topic.name, topicId)).join("")}</select>`)}
          <button class="button primary" type="submit">${icon(items.length ? "refresh" : "spark", true)} ${items.length ? "Refresh recommendations" : "Generate recommendations"}</button>
        </div>
        <div class="form-message" role="alert"></div>
        ${!topicId && ctx.user.interests?.length ? `<div class="tags" aria-label="Your interests">${ctx.user.interests.map(interest => badge(interest, "neutral")).join("")}</div>` : ""}
        <p class="muted small">Match scores use book descriptions and topic overlap. ${linkTo("/profile", "Edit interests", "")}</p>
      </form>
    </section>
    <section class="section">
      ${sectionHeading(chosen ? `Books for ${chosen.name}` : "Your latest picks", items.length ? `Generated ${dateLabel(items[0].generated_at, true)}` : "")}
      ${items.length ? `<div class="book-grid">${items.map(item => bookCard(item.book, item)).join("")}</div>` : empty("No recommendations yet", "Choose a focus and generate a set of recommendations.", "", "spark")}
    </section>`);
  const select = document.querySelector("#recommend-form select");
  select?.addEventListener("change", event => {
    ctx.go(recommendationUrl(event.currentTarget.value));
  });
  ctx.form("recommend-form", async values => {
    const filter = values.get("topic_id");
    const body = filter ? { topic_id: Number(filter) } : {};
    const data = await api("/recommendations/generate", { method: "POST", body });
    ctx.notice(data.recommendations.length ? "Recommendations updated." : "No books match that focus yet.");
    ctx.refresh();
  });
}

function pathwayCard(pathway) {
  return `<article class="path-card">
    <div class="actions">${badge(pathway.status === "completed" ? "Completed" : "Active", pathway.status === "completed" ? "" : "neutral", pathway.status === "completed" ? "check" : "")}</div>
    <h3>${esc(pathway.name)}</h3>
    <p>${esc(pathway.target_goal || pathway.description)}</p>
    ${progress(pathway)}
    <p>${pathway.completed_steps} of ${pathway.total_steps} steps complete</p>
    ${linkTo(`/pathways/${Number(pathway.pathway_id)}`, pathway.status === "completed" ? "View pathway" : "Open pathway")}
  </article>`;
}

async function pathways(ctx) {
  const { pathways: items } = await api("/pathways/me");
  const action = linkTo("/pathways/new", "Create pathway", "plus", "button primary");
  ctx.render(`${heading("Study pathways", "Choose a goal, learn topics in prerequisite order, and track your progress.", "", action)}
    ${items.length ? `<div class="path-grid">${items.map(pathwayCard).join("")}</div>` : empty("No pathways yet", "Choose your first learning goal and the topics you want to explore.", action, "path")}`);
}

async function newPathway(ctx) {
  const { topics } = await api("/topics");
  ctx.render(`<div class="back-link">${linkTo("/pathways", "Study pathways", "back")}</div>
    ${heading("Create a study pathway", "Set a learning goal and select topics. Folio uses the catalog’s prerequisites to order your steps.")}
    <section class="panel pad">
      <form id="pathway-form" class="form">
        <div class="form-grid">
          ${field("Pathway name", '<input name="name" maxlength="200" placeholder="Machine Learning Foundations" required>')}
          ${field("Learning goal", '<input name="target_goal" maxlength="255" placeholder="Learn how to evaluate a classifier" required>')}
          ${field("Description (optional)", '<textarea name="description" maxlength="6000" placeholder="What would you like to get out of this pathway?"></textarea>', "wide")}
        </div>
        ${sectionHeading("Choose topics")}
        ${field("Filter topics", '<input type="search" name="topic_filter" placeholder="Filter by concept or subject">')}
        ${topics.length ? `<div class="topic-list" role="group" aria-label="Choose topics">${topics.map(topic => `
          <label class="checkbox" data-topic-text="${esc(`${topic.name} ${topic.subject} ${topic.difficulty_level || ""}`.toLowerCase())}">
            <input type="checkbox" name="topic_ids" value="${Number(topic.topic_id)}">
            <span><strong>${esc(topic.name)}</strong><small>${esc(topic.subject)} · ${esc(topic.difficulty_level)}</small>
            ${topic.prerequisites?.length ? `<small>Requires ${esc(topic.prerequisites.map(item => item.name).join(", "))}</small>` : ""}
            </span>
          </label>`).join("")}</div><p id="topic-filter-message" class="muted small" role="status" hidden>No topics match that filter.</p>` :
          empty("No topics are available", "Ask a library administrator to add topics to the catalog.", "", "path")}
        <label class="checkbox"><input type="checkbox" name="include_prerequisites"><span>Include missing prerequisites automatically</span></label>
        <div class="form-message" role="alert"></div>
        <div class="actions"><button type="submit" class="button primary" ${topics.length ? "" : "disabled"}>${icon("plus", true)} Create pathway</button></div>
      </form>
    </section>`);
  const filter = document.querySelector('[name="topic_filter"]');
  filter?.addEventListener("input", event => {
    const needle = event.currentTarget.value.trim().toLowerCase();
    const rows = [...document.querySelectorAll("[data-topic-text]")];
    rows.forEach(row => { row.hidden = !row.dataset.topicText.includes(needle) && !row.querySelector("input").checked; });
    const status = document.querySelector("#topic-filter-message");
    if (status) status.hidden = !rows.every(row => row.hidden);
  });
  ctx.form("pathway-form", async values => {
    const ids = values.getAll("topic_ids").map(Number);
    if (!ids.length) throw new Error("Select at least one topic to build your pathway.");
    const data = await api("/pathways", { method: "POST", body: {
      name: values.get("name"), target_goal: values.get("target_goal"), description: values.get("description"),
      topic_ids: ids, include_prerequisites: values.has("include_prerequisites"),
    } });
    ctx.go(`/pathways/${Number(data.pathway.pathway_id)}`);
    ctx.notice("Study pathway created.");
  });
}

function stepView(step) {
  const id = Number(step.pathway_topic_id);
  const label = { available: "Available", completed: "Completed", locked: "Locked" }[step.state] || "Locked";
  const stateTone = step.state === "available" ? "" : step.state === "completed" ? "score" : "neutral";
  const stateIcon = step.state === "completed" ? "check" : step.state === "locked" ? "lock" : "";
  return `<li class="step ${esc(step.state)}">
    <span class="avatar number">${step.state === "completed" ? icon("check", true) : esc(step.sequence_no)}</span>
    <div><h3>${esc(step.name)}</h3>
      <div class="tags">${badge(label, stateTone, stateIcon)} ${badge(step.difficulty_level, "neutral")}</div>
      ${step.description ? `<p>${esc(step.description)}</p>` : ""}
      ${step.prerequisites?.length ? `<p class="small muted">Prerequisites include ${esc(step.prerequisites.map(topic => topic.name).join(", "))}.</p>` : ""}
      ${step.blocked_by?.length ? `<p class="small"><strong>Finish ${esc(step.blocked_by.map(topic => topic.name).join(", "))} to unlock this step.</strong></p>` : ""}
      ${step.completed_at ? `<p class="small muted">Completed ${dateLabel(step.completed_at, true)}</p>` : ""}
      <div class="actions">
        ${linkTo(recommendationUrl(step.topic_id), "Find topic recommendations", "spark")}
        ${step.books?.length ? `<details class="step-books"><summary>${step.books.length} related ${step.books.length === 1 ? "book" : "books"}</summary>
          <ul>${step.books.map(book => `<li>${linkTo(`/books/${Number(book.book_id)}`, book.title, "")} <span class="small muted">· ${esc(book.author)}</span></li>`).join("")}</ul></details>` : ""}
      </div>
    </div>
    ${step.state === "available" ? `<div class="actions"><button type="button" class="button primary compact" data-action="complete-step" data-id="${id}">${icon("check", true)} Mark complete</button></div>` : ""}
  </li>`;
}

async function pathway(ctx) {
  const { pathway: item } = await api(`/pathways/${ctx.params[0]}`);
  ctx.render(`<div class="back-link">${linkTo("/pathways", "Study pathways", "back")}</div>
    ${heading(item.name, item.target_goal, "", linkTo(`/pathways/${item.pathway_id}/verify`, "Verify progress", "shield", "button secondary"))}
    <section class="panel pad">${sectionHeading("Progress", `${item.completed_steps} of ${item.total_steps} steps complete`)}
      ${progress(item)}${item.description ? `<p class="section muted">${esc(item.description)}</p>` : ""}
    </section>
    <section class="section">${sectionHeading("Learning sequence")}
      <ol class="steps">${item.steps.map(stepView).join("")}</ol>
    </section>`);
  ctx.actions("complete-step", async ({ id }) => {
    await api(`/pathway-topics/${Number(id)}/complete`, { method: "POST" });
    ctx.notice("Step completed and recorded in the progress ledger.");
    ctx.refresh();
  });
}

function hashCell(hash) {
  return `<details class="hash"><summary>${esc(String(hash || "").slice(0, 12))}…</summary><code>${esc(hash)}</code></details>`;
}

async function verification(ctx) {
  const { entries, pathway: item, verification: result } = await api(`/pathways/${ctx.params[0]}/ledger`);
  const back = ctx.user.role === "admin" ? linkTo("/admin?section=progress", "Progress records", "back") : linkTo(`/pathways/${item.pathway_id}`, item.name, "back");
  ctx.render(`<div class="back-link">${back}</div>
    ${heading("Verify progress", item.name)}
    <section class="panel pad ledger-result">
      <div>${badge(result.valid ? "Verified" : "Verification failed", result.valid ? "" : "error", result.valid ? "shield" : "alert")}
        <p>${esc(result.message)}</p>
        ${result.first_invalid_entry != null ? `<p class="small muted">First invalid ledger entry #${esc(result.first_invalid_entry)}</p>` : ""}
        ${result.first_invalid_entry == null && result.first_invalid_step != null ? `<p class="small muted">First affected step record #${esc(result.first_invalid_step)}</p>` : ""}
      </div>
      <button class="button secondary" type="button" data-action="verify-again">${icon("refresh", true)} Verify again</button>
    </section>
    <section class="section">
      ${sectionHeading("Completion history", `${entries.length} recorded ${entries.length === 1 ? "event" : "events"}`)}
      ${entries.length ? `<div class="panel table-wrap"><table>
        <thead><tr><th scope="col">Step</th><th scope="col">Topic</th><th scope="col">Completed</th><th scope="col">Previous hash</th><th scope="col">Entry hash</th></tr></thead>
        <tbody>${entries.map(entry => `<tr><td>${esc(entry.sequence_no)}</td><td><strong>${esc(entry.topic_name || "Unknown topic")}</strong><div class="small muted">Entry #${esc(entry.ledger_id)}</div></td>
        <td>${dateLabel(entry.event_time, true)}</td><td>${hashCell(entry.previous_hash)}</td><td>${hashCell(entry.entry_hash)}</td></tr>`).join("")}</tbody>
      </table></div>` : empty("No completion entries", "The first completed step will create the beginning of this pathway’s ledger.", "", "shield")}
      <p class="section muted small">Folio checks whether the completion records agree with each other and with the pathway. A privileged party with control of both the records and the signing secret could rewrite history.</p>
    </section>`);
  ctx.actions("verify-again", async () => ctx.refresh());
}

export async function studyView(path, ctx) {
  if (path === "/recommendations") await recommendations(ctx);
  else if (path === "/pathways") await pathways(ctx);
  else if (path === "/pathways/new") await newPathway(ctx);
  else if (path.endsWith("/verify")) await verification(ctx);
  else await pathway(ctx);
}
