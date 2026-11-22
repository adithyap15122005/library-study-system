import { api } from "./api.js";
import { modulesFor, stepBooks } from "./courses.js";
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
  const action = linkTo("/courses", "Explore courses", "arrow", "button primary");
  ctx.render(`${heading("My study pathways", "Continue a course and track your verified progress.", "", action)}
    ${items.length ? `<div class="path-grid">${items.map(pathwayCard).join("")}</div>` : empty("No pathways yet", "Choose a course and Folio will generate its complete learning sequence.", action, "path")}`);
}

function stepView(step, verified) {
  const id = Number(step.pathway_topic_id);
  const label = { available: "Available", completed: "Completed", locked: "Locked" }[step.state] || "Locked";
  const stateTone = step.state === "available" ? "" : step.state === "completed" ? "score" : "neutral";
  const stateIcon = step.state === "completed" ? "check" : step.state === "locked" ? "lock" : "";
  return `<li class="step ${esc(step.state)}">
    <span class="avatar number">${step.state === "completed" ? icon("check", true) : esc(step.sequence_no)}</span>
    <div><h3>${esc(step.name)}</h3>
      <div class="tags">${badge(label, stateTone, stateIcon)} ${badge(step.difficulty_level, "neutral")}
        ${step.estimated_hours ? badge(`${step.estimated_hours} hours`, "neutral", "clock") : ""}</div>
      ${step.description ? `<p>${esc(step.description)}</p>` : ""}
      ${step.prerequisites?.length ? `<p class="small muted">Prerequisites include ${esc(step.prerequisites.map(topic => topic.name).join(", "))}.</p>` : ""}
      ${step.blocked_by?.length ? `<p class="small muted"><strong>Finish ${esc(step.blocked_by[0].name)}${step.blocked_by.length > 1 ? ` and ${step.blocked_by.length - 1} other earlier topics` : ""} to unlock this step.</strong></p>` : ""}
      ${step.completed_at ? `<p class="small muted">Completed ${dateLabel(step.completed_at, true)}</p>` : ""}
      <div class="actions">
        ${linkTo(recommendationUrl(step.topic_id), "Find topic recommendations", "spark")}
      </div>
      ${verified || step.books?.length ? stepBooks(step.books, "Related catalogue books") : ""}
    </div>
    ${step.state === "available" ? `<div class="actions"><button type="button" class="button primary compact" data-action="complete-step" data-id="${id}">${icon("check", true)} Mark complete</button></div>` : ""}
  </li>`;
}

async function pathway(ctx) {
  const { pathway: item } = await api(`/pathways/${ctx.params[0]}`);
  const modules = modulesFor(item.steps);
  const percent = Math.min(100, Math.max(0, Number(item.progress_percent) || 0));
  ctx.render(`<div class="back-link">${linkTo("/pathways", "Study pathways", "back")}</div>
    <section class="course-hero pathway-hero"><div>
      <h1>${esc(item.name)}</h1><p>${esc(item.description || item.target_goal)}</p>
      <div class="tags">${badge(`${item.total_steps} topics`, "neutral", "path")}
      ${item.estimated_hours ? badge(`${item.estimated_hours} hours`, "neutral", "clock") : ""}
      ${linkTo(`/pathways/${item.pathway_id}/verify`, "Verify progress", "shield", "button light")}</div>
    </div><aside class="pathway-progress">
      <div class="progress-ring" style="--progress: ${percent}%"><strong>${percent}%</strong></div>
      <div><h2>Study progress</h2><p>${item.completed_steps} of ${item.total_steps} steps complete</p></div>
    </aside>
    </section>
    <section class="section stack">${modules.map((module, index) => `<details class="module-panel panel"
      ${module.steps.some(step => step.state === "available") || modules.length === 1 ? "open" : ""}>
      <summary><span><span class="module-label">Module ${index + 1}</span> ${esc(module.name)}</span>
      <span class="small muted">${module.steps.filter(step => step.is_completed).length} / ${module.steps.length} complete</span></summary>
      <ol class="steps">${module.steps.map(step => stepView(step, item.course_id != null)).join("")}</ol>
    </details>`).join("")}</section>`);
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
  else if (path === "/pathways/new") ctx.go("/courses", true);
  else if (path.endsWith("/verify")) await verification(ctx);
  else await pathway(ctx);
}
