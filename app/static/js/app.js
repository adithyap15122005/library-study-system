import { api } from "./api.js";
import { bookCard, dateLabel, empty, esc as escapeHTML, field, heading, icon, initials, linkTo, loanBadge, logo, progress, sectionHeading, stat } from "./ui.js";

const app = document.querySelector("#app");
let user = null;
let viewId = 0;

const nav = [
  ["/dashboard", "Overview", "layout"],
  ["/courses", "Explore courses", "path"],
  ["/catalog", "Browse books", "library"],
  ["/borrowing", "My borrowings", "clock"],
  ["/recommendations", "Recommendations", "spark"],
  ["/pathways", "My study pathways", "path"],
  ["/profile", "My profile", "user"],
  ["/admin", "Administration", "shield"],
];

function routeName(path) {
  if (path.startsWith("/books/")) return "/catalog";
  if (path.startsWith("/courses/")) return "/courses";
  if (user?.role === "admin" && path.endsWith("/verify")) return "/admin";
  if (path.startsWith("/pathways/")) return "/pathways";
  return path;
}

function publicFrame(content) {
  app.innerHTML = `<div class="public">
    <header class="public-header">${logo()}<nav class="public-nav" aria-label="Main navigation">
      <a href="/catalog" class="public-catalog">Library</a><a href="/login">Sign in</a>
      <a href="/register" class="button primary">Create account ${icon("arrow", true)}</a>
    </nav></header>
    <main id="main" class="public-main" tabindex="-1">${content}</main>
    <footer class="public-footer"><span>Folio · RV College of Engineering</span><span>Database Management System Lab</span></footer>
  </div>`;
}

function workspaceFrame(path) {
  const current = routeName(path);
  const title = nav.find(([href]) => href === current)?.[1] || "Overview";
  app.innerHTML = `<div class="workspace">
    <aside class="sidebar" id="workspace-nav">${logo(user.role === "admin" ? "/admin" : "/dashboard")}
      <nav class="side-nav" aria-label="Workspace"><div class="eyebrow">Workspace</div>
        ${nav.filter(([href]) => (href !== "/admin" || user.role === "admin") &&
          (user.role !== "admin" || !["/dashboard", "/borrowing", "/recommendations", "/pathways"].includes(href)))
          .map(([href, label, glyph]) => `<a href="${href}" ${href === current ? 'aria-current="page"' : ""}>${icon(glyph)}${label}</a>`).join("")}
      </nav>
      <div class="side-footer"><a href="/profile"><span class="avatar">${initials(user.name)}</span>
        <span><strong>${escapeHTML(user.name)}</strong><small>${user.role === "admin" ? "Administrator" : "Student account"}</small></span>
      </a></div>
    </aside>
    <button class="nav-overlay" type="button" tabindex="-1" aria-label="Close navigation"></button>
    <div class="work-area">
      <header class="topbar">
        <button class="icon-button mobile-menu" type="button" aria-label="Open navigation" aria-controls="workspace-nav" aria-expanded="false">${icon("menu")}</button>
        <div class="breadcrumb"><span>Workspace</span>${icon("chevron", true)}<strong>${title}</strong></div>
        <form class="top-search" role="search"><label class="sr-only" for="global-query">Search the library</label>${icon("search", true)}<input id="global-query" name="q" type="search" placeholder="Search the library…" maxlength="120"></form>
      </header>
      <main id="main" class="main-content" tabindex="-1"><div class="loading" role="status"><span class="spinner"></span> Loading ${title.toLowerCase()}…</div></main>
    </div>
  </div>`;
  const workspace = app.querySelector(".workspace");
  const menu = app.querySelector(".mobile-menu");
  function toggleMenu(open) {
    workspace.classList.toggle("nav-open", open);
    menu.setAttribute("aria-expanded", String(open));
    menu.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  }
  menu.addEventListener("click", () => {
    const open = !workspace.classList.contains("nav-open");
    toggleMenu(open);
    if (open) (workspace.querySelector(".side-nav a[aria-current]") || workspace.querySelector(".side-nav a"))?.focus();
  });
  workspace.querySelector(".nav-overlay").addEventListener("click", () => {
    toggleMenu(false);
    menu.focus();
  });
  workspace.addEventListener("keydown", event => {
    if (event.key === "Escape" && workspace.classList.contains("nav-open")) {
      toggleMenu(false);
      menu.focus();
    }
  });
  workspace.querySelector(".top-search").addEventListener("submit", event => {
    event.preventDefault();
    const q = new FormData(event.currentTarget).get("q").trim();
    go(`/catalog${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  });
  document.title = `${title} · Folio`;
}

function landing() {
  document.title = "Folio · Your academic library";
  publicFrame(`<section class="landing-hero">
    <div class="landing-copy"><div class="eyebrow">RV College of Engineering</div>
      <h1>A library for what’s next.</h1>
      <p>Find the right books for your interests, borrow from the collection, and build a study pathway you can follow at your own pace.</p>
      <div class="actions">${linkTo("/register", "Get started", "arrow", "button light")}${linkTo("/login", "Sign in", "", "button on-dark")}</div>
    </div>
  </section>
  <section class="landing-features" aria-label="What you can do">
    <article class="feature-card"><span class="icon-frame">${icon("library")}</span><h2>Explore the collection</h2><p>Search by book, author, or academic topic and borrow an available copy.</p></article>
    <article class="feature-card"><span class="icon-frame amber">${icon("spark")}</span><h2>Find your next read</h2><p>Get book recommendations based on your interests and see what makes each one a match.</p></article>
    <article class="feature-card"><span class="icon-frame blue">${icon("path")}</span><h2>Build a study pathway</h2><p>Learn topics in prerequisite order and verify your record of completed steps.</p></article>
  </section>`);
}

function loginRedirect() {
  const redirect = new URLSearchParams(location.search).get("next");
  return redirect && /^\/(?![\\/])/.test(redirect) && !redirect.startsWith("/login") && !redirect.startsWith("/register") ? redirect : "";
}

function auth(mode) {
  const registering = mode === "register";
  const next = loginRedirect();
  const suffix = next ? `?next=${encodeURIComponent(next)}` : "";
  document.title = `${registering ? "Create account" : "Sign in"} · Folio`;
  publicFrame(`<section class="auth-shell">
    <div class="auth-photo"><div><h2>Make space for what you want to learn.</h2><p>Explore the collection and pick up where you left off.</p></div></div>
    <div class="auth-form"><div><h1>${registering ? "Create an account" : "Sign in"}</h1>
      <p class="muted">${registering ? "Start your student account with your name and email." : "Open your library and study workspace."}</p>
      <form id="auth-form" class="form">
        ${registering ? field("Full name", '<input name="name" autocomplete="name" required maxlength="120">') : ""}
        ${field("Email address", '<input name="email" type="email" autocomplete="email" required maxlength="255">')}
        ${field("Password", `<input name="password" type="password" autocomplete="${registering ? "new-password" : "current-password"}" required ${registering ? 'minlength="8"' : ""} maxlength="128">`)}
        <div class="form-message" role="alert"></div>
        <button class="button primary" type="submit">${registering ? "Create account" : "Sign in"} ${icon("arrow", true)}</button>
      </form>
      <p class="small muted">${registering ? "Already have an account?" : "New to Folio?"} ${linkTo(`${registering ? "/login" : "/register"}${suffix}`, registering ? "Sign in" : "Create an account", "")}</p>
    </div></div>
  </section>`);
  context(viewId).form("auth-form", async values => {
    const data = await api(`/auth/${mode}`, { method: "POST", body: Object.fromEntries(values) });
    if (data.user) {
      user = data.user;
      go(next || (user.role === "admin" ? "/admin" : "/dashboard"), true);
    } else {
      go(`/login${suffix}`, true);
      notice("Account created. Sign in to open your workspace.");
    }
  });
}

async function dashboard(ctx) {
  if (user.role === "admin") {
    go("/admin", true);
    return;
  }
  const [data, recommendations, pathways, catalogue, { courseCard }] = await Promise.all([
    api("/dashboard"), api("/recommendations/me"), api("/pathways/me"), api("/courses"), import("./courses.js"),
  ]);
  const firstName = user.name.trim().split(/\s+/)[0];
  const active = (pathways.pathways || []).find(pathway => pathway.status === "active");
  const picks = (recommendations.recommendations || []).slice(0, 4);
  const featured = ["Machine Learning", "Database Management Systems", "Python"].map(
    name => catalogue.courses.find(course => course.name === name),
  ).filter(Boolean);
  ctx.render(`${heading(`Welcome, ${firstName}`, "Here’s what’s happening in your library and study pathways.")}
    <section class="dash-hero"><div><span class="eyebrow">Your library</span><h2>What will you learn next?</h2><p>Find a book for your next topic or pick up an active study pathway.</p>
      <div class="actions">${linkTo("/courses", "Explore courses", "arrow", "button light")}${linkTo("/catalog", "Browse real books", "", "button on-dark")}</div>
    </div></section>
    <section class="stats" aria-label="Library and study activity">
      ${stat("Books borrowed", data.total_borrowed, "book", "All borrowing activity")}
      ${stat("Currently issued", data.issued, "clock", `${data.due_soon} due soon · ${data.overdue} overdue`, "amber")}
      ${stat("Active pathways", data.active_pathways, "path", "In progress", "blue")}
      ${stat("Steps completed", data.completed_steps, "check", "Across all pathways")}
    </section>
    <div class="split section">
      <section class="panel pad">${sectionHeading("Continue learning", "", linkTo("/pathways", "My study pathways"))}
        ${active ? `<div class="path-card"><h3>${escapeHTML(active.name)}</h3><p>${active.completed_steps} of ${active.total_steps} steps complete</p>${progress(active)}${linkTo(`/pathways/${Number(active.pathway_id)}`, "Resume pathway")}</div>` : empty("Start a course", "Choose a course to generate your full study pathway.", linkTo("/courses", "Explore courses"), "path")}
      </section>
      <section class="panel pad">${sectionHeading("Recent activity", "", linkTo("/borrowing", "View borrowings"))}
        ${data.recent_borrows.length ? `<ul class="activity">${data.recent_borrows.map(loan => `<li><span class="icon-frame">${icon("book")}</span><div><strong><a href="/books/${Number(loan.book_id)}">${escapeHTML(loan.title)}</a></strong><span class="small muted">${dateLabel(loan.return_date || loan.issue_date)}</span></div>${loanBadge(loan)}</li>`).join("")}</ul>` : empty("No borrowing activity", "Borrow a copy to start building your library history.")}
      </section>
    </div>
    ${featured.length ? `<section class="section">${sectionHeading("Explore courses", "", linkTo("/courses", "View all courses"))}
      <div class="course-grid">${featured.map(course => courseCard(course, course.name === "Machine Learning")).join("")}</div></section>` : ""}
    <section class="section">${sectionHeading("Recommended for you", "", linkTo("/recommendations", "View recommendations"))}
      ${picks.length ? `<div class="book-grid">${picks.map(item => bookCard(item.book, item)).join("")}</div>` : empty("Find your next read", "Generate book picks from your interests or a topic you want to learn.", linkTo("/recommendations", "Get recommendations"), "spark")}
    </section>`);
}

async function profile(ctx) {
  const record = await api("/me");
  ctx.render(`${heading("My profile", "Update your account details and the interests used for book recommendations.")}
    <section class="panel pad"><div class="profile-overview"><span class="avatar">${initials(record.name)}</span><div><h3>${escapeHTML(record.name)}</h3><div class="muted small">${record.role === "admin" ? "Administrator" : "Student"} · Joined ${dateLabel(record.date_of_joining)}</div></div></div>
    <form id="profile-form" class="form">
      <div class="form-grid">
        ${field("Full name", `<input name="name" value="${escapeHTML(record.name)}" maxlength="120" autocomplete="name" required>`)}
        ${field("Email address", `<input name="email" type="email" value="${escapeHTML(record.email)}" maxlength="255" autocomplete="email" required>`)}
        ${field("Interests (comma separated)", `<textarea name="interests" maxlength="1200" placeholder="Python, database design, machine learning">${escapeHTML((record.interests || []).join(", "))}</textarea>`, "wide")}
      </div>
      <div class="form-message" role="alert"></div><div class="actions"><button type="submit" class="button primary">Save profile</button></div>
    </form></section>
    <section class="section actions"><button class="button secondary" data-action="logout" type="button">${icon("logout", true)} Sign out</button></section>`);
  ctx.form("profile-form", async values => {
    const { name, email, interests } = Object.fromEntries(values);
    user = await api("/me", { method: "PATCH", body: { name, email, interests: interests.split(",").map(value => value.trim()).filter(Boolean) } });
    notice("Profile saved.");
    refresh();
  });
  ctx.actions("logout", async () => {
    await api("/auth/logout", { method: "POST" });
    user = null;
    go("/", true);
    notice("You’ve signed out.");
  });
}

function notice(message, tone = "") {
  const node = document.createElement("div");
  node.className = `notice ${tone === "error" ? "error" : ""}`;
  node.innerHTML = `${icon(tone === "error" ? "alert" : "check", true)}<span>${escapeHTML(message)}</span>`;
  document.querySelector("#notices").replaceChildren(node);
  window.setTimeout(() => node.remove(), 5300);
}

function explain(error) {
  const details = error.details;
  const missing = details?.missing_prerequisites || details?.blocked_by || details?.missing;
  if (!Array.isArray(missing) || !missing.length) return error.message;
  const names = missing.map(topic => typeof topic === "object" ? topic.name : topic).filter(Boolean);
  return names.length ? `${error.message} ${names.join(", ")}.` : error.message;
}

function context(id, params = []) {
  return {
    user, params, query: new URLSearchParams(location.search),
    render(markup) {
      if (id === viewId) document.querySelector("#main").innerHTML = markup;
    },
    form(target, callback) {
      if (id !== viewId) return;
      const form = document.getElementById(target);
      form?.addEventListener("submit", async event => {
        event.preventDefault();
        if (form.dataset.busy) return;
        const status = form.querySelector(".form-message");
        if (status) status.textContent = "";
        const values = new FormData(form);
        const button = event.submitter || form.querySelector('[type="submit"]');
        form.dataset.busy = "true";
        if (button) {
          button.disabled = true;
          button.setAttribute("aria-busy", "true");
        }
        try {
          await callback(values, form, event);
        } catch (error) {
          if (error.status === 401 && user) {
            sessionExpired();
          } else if (status) {
            status.textContent = explain(error);
          } else {
            notice(explain(error), "error");
          }
        } finally {
          delete form.dataset.busy;
          if (button) {
            button.disabled = false;
            button.removeAttribute("aria-busy");
          }
        }
      });
    },
    actions(name, callback) {
      if (id !== viewId) return;
      app.querySelectorAll(`[data-action="${name}"]`).forEach(button => {
        button.addEventListener("click", async () => {
          if (button.disabled) return;
          button.disabled = true;
          button.setAttribute("aria-busy", "true");
          try {
            await callback(button.dataset, button);
          } catch (error) {
            if (error.status === 401) sessionExpired();
            else notice(explain(error), "error");
          } finally {
            button.disabled = false;
            button.removeAttribute("aria-busy");
          }
        });
      });
    },
    go, refresh, notice,
  };
}

async function load() {
  const id = ++viewId;
  const path = location.pathname;
  if (!user) {
    if (path === "/") landing();
    else if (path === "/login" || path === "/register") auth(path.slice(1));
    else go(`/login?next=${encodeURIComponent(path + location.search)}`, true);
    return;
  }
  if (["/", "/login", "/register"].includes(path)) {
    go(user.role === "admin" ? "/admin" : "/dashboard", true);
    return;
  }
  workspaceFrame(path);
  const match = path.match(/\d+$/) || path.match(/\/(\d+)\/(?:verify|edit)$/);
  const params = match ? [Number(match[1] || match[0])] : [];
  const ctx = context(id, params);
  try {
    if (path === "/dashboard") await dashboard(ctx);
    else if (path === "/profile") await profile(ctx);
    else if (path === "/courses" || path.startsWith("/courses/")) {
      const { courseView } = await import("./courses.js");
      await courseView(path, ctx);
    }
    else if (path === "/catalog" || path.startsWith("/books/") || path === "/borrowing") {
      const { libraryView } = await import("./library.js");
      await libraryView(path, ctx);
    } else if (path === "/recommendations" || path.startsWith("/pathways")) {
      const { studyView } = await import("./study.js");
      await studyView(path, ctx);
    } else if (path === "/admin") {
      const { adminView } = await import("./admin.js");
      await adminView(ctx);
    } else {
      ctx.render(empty("Page not found", "Choose a section to continue in your workspace.", linkTo("/dashboard", "Back to overview", "back"), "alert"));
    }
  } catch (error) {
    if (id !== viewId) return;
    if (error.status === 401) sessionExpired();
    else ctx.render(empty("This page could not load", error.message, linkTo("/dashboard", "Back to overview", "back"), "alert"));
  }
}

async function refresh() {
  const scrollPosition = window.scrollY;
  const expectedView = viewId + 1;
  await load();
  if (viewId === expectedView) window.scrollTo(0, scrollPosition);
}

function go(to, replace = false) {
  const url = new URL(to, location.origin);
  if (url.origin !== location.origin) return;
  history[replace ? "replaceState" : "pushState"]({}, "", url);
  load();
  window.scrollTo(0, 0);
  document.querySelector("#main")?.focus({ preventScroll: true });
}

async function sessionExpired() {
  user = null;
  try {
    await api("/session");
  } catch {
    // The sign-in screen remains available while the server reconnects.
  }
  go(`/login?next=${encodeURIComponent(location.pathname + location.search)}`, true);
  notice("Your session ended. Please sign in again.", "error");
}

document.addEventListener("click", event => {
  const anchor = event.target.closest("a[href]");
  if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || anchor.target || anchor.hasAttribute("download")) return;
  const target = new URL(anchor.href);
  if (target.origin !== location.origin || target.hash) return;
  event.preventDefault();
  go(target.pathname + target.search);
});
document.addEventListener("error", event => {
  if (event.target instanceof HTMLImageElement && event.target.hasAttribute("data-optional-cover")) event.target.remove();
}, true);
window.addEventListener("popstate", load);

try {
  const session = await api("/session");
  user = session.user;
  load();
} catch (error) {
  landing();
  notice(error.message, "error");
}
