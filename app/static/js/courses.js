import { api } from "./api.js";
import { badge, empty, esc, field, heading, icon, linkTo, option, sectionHeading, stock } from "./ui.js";

export function modulesFor(steps) {
  const modules = [];
  for (const step of steps) {
    const name = step.module || "Learning sequence";
    if (modules.at(-1)?.name !== name) modules.push({ name, steps: [] });
    modules.at(-1).steps.push(step);
  }
  return modules;
}

export function stepBooks(books, label = "Reading") {
  if (!books?.length) return '<p class="small muted">No verified catalogue match for this topic.</p>';
  return `<div class="step-reading"><strong>${esc(label)}</strong><ul>
    ${books.map(book => `<li><div>${linkTo(`/books/${Number(book.book_id)}`, book.title, "")}
    <div class="small muted">${esc(book.author)}</div></div>${stock(book)}</li>`).join("")}</ul></div>`;
}

export function courseCard(course, featured = false) {
  return `<article class="course-card${featured ? " featured-course" : ""}">
    <div class="course-card-top"><span class="icon-frame">${icon(featured ? "spark" : "book")}</span>
    ${badge(course.difficulty_level, "neutral")}</div>
    <div>${course.subject !== course.name ? `<p class="course-subject">${esc(course.subject)}</p>` : ""}<h2>${esc(course.name)}</h2></div>
    <p>${esc(course.description)}</p>
    <div class="course-meta"><span>${icon("clock", true)} ${esc(course.estimated_hours)} hours</span>
    <span>${icon("path", true)} ${esc(course.total_steps)} topics</span></div>
    ${linkTo(`/courses/${Number(course.course_id)}`, "Preview pathway", "arrow", "button secondary")}
  </article>`;
}

async function explore(ctx) {
  const { courses } = await api("/courses");
  const query = ctx.query.get("q") || "";
  const visible = courses.filter(course => `${course.name} ${course.subject} ${course.difficulty_level}`.toLowerCase()
    .includes(query.toLowerCase()));
  const ordered = [...visible].sort((a, b) => Number(b.name === "Machine Learning") - Number(a.name === "Machine Learning"));
  const admin = ctx.user.role === "admin";
  ctx.render(`${heading("Explore courses", "Choose a complete syllabus and Folio will create your study pathway in prerequisite order.",
    "", admin ? linkTo("/courses/new", "Add course", "plus", "button primary") : "")}
    <section class="course-toolbar panel pad">
      <form id="course-filter" role="search">${field("Find a course", `<input type="search" name="q" maxlength="100" value="${esc(query)}" placeholder="Search subject or difficulty">`)}
      <button type="submit" class="button secondary">${icon("search", true)} Search</button></form>
      <p class="small muted">${visible.length} ${visible.length === 1 ? "course" : "courses"}</p>
    </section>
    <div class="course-grid section">${ordered.map(course => courseCard(course, course.name === "Machine Learning")).join("")}</div>
    ${ordered.length ? "" : empty("No courses found", "Try a different subject or difficulty.", linkTo("/courses", "Show all courses"), "search")}`);
  ctx.form("course-filter", async values => {
    const value = String(values.get("q")).trim();
    ctx.go(value ? `/courses?q=${encodeURIComponent(value)}` : "/courses");
  });
}

async function preview(ctx) {
  const { course, steps } = await api(`/courses/${ctx.params[0]}/preview`);
  const admin = ctx.user.role === "admin";
  ctx.render(`<div class="back-link">${linkTo("/courses", "Explore courses", "back")}</div>
    <section class="course-hero">
      <div><div class="tags">${badge(course.difficulty_level)} ${badge(`${course.estimated_hours} hours`, "neutral", "clock")}
        ${badge(`${course.total_steps} topics`, "neutral", "path")}</div>
        <h1>${esc(course.name)}</h1><p>${esc(course.description)}</p>
        ${admin ? linkTo(`/courses/${course.course_id}/edit`, "Edit curriculum", "arrow", "button light") :
        `<button type="button" data-action="start-course" class="button light">${icon("path", true)} Create my pathway</button>`}
      </div>
      <aside><h2>What you’ll learn</h2><ul>${course.objectives.map(value => `<li>${esc(value)}</li>`).join("")}</ul></aside>
    </section>
    <section class="section">${sectionHeading("Course syllabus", "Prerequisites are included and shown in study order.")}
      <div class="stack">${modulesFor(steps).map((module, index) => `<details class="module-panel panel" ${index === 0 ? "open" : ""}>
        <summary><span><span class="module-label">Module ${index + 1}</span> ${esc(module.name)}</span>
          <span class="small muted">${module.steps.length} topics</span></summary>
        <ol class="steps">${module.steps.map(step => `<li class="step">
          <span class="avatar number">${esc(step.sequence_no)}</span><div>
          <h3>${esc(step.name)}</h3><p class="small muted">${step.estimated_hours} hours
          ${step.prerequisites.length ? ` · Requires ${esc(step.prerequisites.map(topic => topic.name).join(", "))}` : ""}</p>
          <p>${esc(step.description)}</p>${stepBooks(step.books.slice(0, 2))}</div></li>`).join("")}</ol>
      </details>`).join("")}</div>
    </section>`);
  ctx.actions("start-course", async () => {
    const result = await api("/pathways/from-course", { method: "POST", body: { course_id: course.course_id } });
    ctx.go(`/pathways/${Number(result.pathway.pathway_id)}`);
    ctx.notice(result.created ? "Your complete pathway is ready." : "Your existing pathway is open.");
  });
}

async function edit(ctx) {
  if (ctx.user.role !== "admin") {
    ctx.render(empty("Administrator access required", "Browse the published courses to start learning.",
      linkTo("/courses", "Explore courses"), "lock"));
    return;
  }
  const id = ctx.params[0];
  const [{ topics }, data] = await Promise.all([api("/topics"), id ? api(`/courses/${id}`) : Promise.resolve(null)]);
  const course = data?.course || {};
  const row = (entry = {}) => `<div class="syllabus-row">
    ${field("Topic", `<select name="topic" required><option value="">Select topic</option>${topics.map(topic =>
      option(topic.topic_id, `${topic.name} · ${topic.subject}`, entry.topic_id)).join("")}</select>`)}
    ${field("Module", `<input name="module" maxlength="100" value="${esc(entry.module)}" required>`)}
    ${field("Hours", `<input name="hours" type="number" min="1" max="100" value="${esc(entry.estimated_hours ?? 2)}" required>`)}
    <button type="button" class="button secondary compact" data-remove-row>Remove</button></div>`;
  ctx.render(`<div class="back-link">${linkTo("/courses", "Explore courses", "back")}</div>
    ${heading(id ? "Edit curriculum" : "Add course", "Arrange the syllabus in its preferred order. Folio adds and sorts prerequisites automatically.")}
    <form id="course-editor" class="form panel pad">
      <div class="form-grid">
        ${field("Course name", `<input name="name" maxlength="150" value="${esc(course.name)}" required>`)}
        ${field("Subject", `<input name="subject" maxlength="100" value="${esc(course.subject)}" required>`)}
        ${field("Difficulty", `<select name="difficulty_level">${["Beginner", "Intermediate", "Advanced"].map(value => option(value, value, course.difficulty_level)).join("")}</select>`)}
        ${field("Description", `<textarea name="description" maxlength="6000" required>${esc(course.description)}</textarea>`, "wide")}
        ${field("Objectives, one per line", `<textarea name="objectives" required>${esc(course.objectives?.join("\n"))}</textarea>`, "wide")}
      </div>
      <h2>Syllabus</h2><div id="syllabus-editor" class="stack">${(data?.syllabus || [{}]).map(row).join("")}</div>
      <div class="actions"><button type="button" data-action="add-topic-row" class="button secondary">Add syllabus topic</button>
      <button type="submit" class="button primary">Save course</button></div><div class="form-message" role="alert"></div>
    </form>`);
  const editor = document.getElementById("syllabus-editor");
  ctx.actions("add-topic-row", async () => {
    editor.insertAdjacentHTML("beforeend", row());
    editor.lastElementChild.querySelector("select").focus();
  });
  editor.addEventListener("click", event => {
    if (event.target.matches("[data-remove-row]")) event.target.closest(".syllabus-row").remove();
  });
  ctx.form("course-editor", async values => {
    const syllabus = [...editor.querySelectorAll(".syllabus-row")].map(element => ({
      topic_id: Number(element.querySelector('[name="topic"]').value),
      module: element.querySelector('[name="module"]').value,
      estimated_hours: Number(element.querySelector('[name="hours"]').value),
    }));
    const body = Object.fromEntries(["name", "subject", "difficulty_level", "description"].map(key => [key, values.get(key)]));
    body.objectives = values.get("objectives").split("\n").map(value => value.trim()).filter(Boolean);
    body.syllabus = syllabus;
    const result = await api(id ? `/admin/courses/${id}` : "/admin/courses", { method: id ? "PUT" : "POST", body });
    ctx.go(`/courses/${Number(result.course_id)}`);
    ctx.notice("Curriculum saved.");
  });
}

export async function courseView(path, ctx) {
  if (path === "/courses") await explore(ctx);
  else if (path === "/courses/new" || path.endsWith("/edit")) await edit(ctx);
  else await preview(ctx);
}
