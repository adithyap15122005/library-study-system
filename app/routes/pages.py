from flask import Blueprint, render_template


pages = Blueprint("pages", __name__)


@pages.get("/")
@pages.get("/login")
@pages.get("/register")
@pages.get("/dashboard")
@pages.get("/catalog")
@pages.get("/books/<int:book_id>")
@pages.get("/borrowing")
@pages.get("/recommendations")
@pages.get("/pathways")
@pages.get("/pathways/new")
@pages.get("/pathways/<int:pathway_id>")
@pages.get("/pathways/<int:pathway_id>/verify")
@pages.get("/profile")
@pages.get("/admin")
def shell(**_):
    return render_template("index.html")
