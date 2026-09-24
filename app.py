from flask import Flask, render_template, request, redirect
import sqlite3
from difflib import SequenceMatcher
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------- DATABASE ----------------

def init_db():

    conn = sqlite3.connect("lostlink.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            contact TEXT NOT NULL
        )
    """)

    # Check existing columns
    columns = conn.execute(
        "PRAGMA table_info(items)"
    ).fetchall()

    column_names = [column[1] for column in columns]

    # Add image column if it doesn't already exist
    if "image" not in column_names:
        conn.execute(
            "ALTER TABLE items ADD COLUMN image TEXT"
        )

    conn.commit()
    conn.close()


# ---------------- AI TEXT MATCHING ----------------

def similarity(text1, text2):

    return SequenceMatcher(
        None,
        str(text1).lower().strip(),
        str(text2).lower().strip()
    ).ratio()


def calculate_match(item1, item2):

    name_score = similarity(
        item1[2],
        item2[2]
    )

    description_score = similarity(
        item1[3],
        item2[3]
    )

    location_score = similarity(
        item1[4],
        item2[4]
    )

    final_score = (
        name_score * 0.50 +
        description_score * 0.30 +
        location_score * 0.20
    )

    return round(final_score * 100)


# ---------------- HOME ----------------

@app.route("/")
def home():

    conn = sqlite3.connect("lostlink.db")

    items = conn.execute("""
        SELECT * FROM items
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        items=items
    )


# ---------------- REPORT ----------------

@app.route("/report", methods=["POST"])
def report():

    item_type = request.form["item_type"]
    item_name = request.form["item_name"]
    description = request.form["description"]
    location = request.form["location"]
    contact = request.form["contact"]

    image_file = request.files.get("image")

    image_name = ""

    if image_file and image_file.filename:

        image_name = secure_filename(
            image_file.filename
        )

        image_file.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                image_name
            )
        )

    conn = sqlite3.connect("lostlink.db")

    conn.execute("""
        INSERT INTO items
        (
            item_type,
            item_name,
            description,
            location,
            contact,
            image
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        item_type,
        item_name,
        description,
        location,
        contact,
        image_name
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# ---------------- AI MATCH ----------------

@app.route("/match/<int:item_id>")
def match(item_id):

    conn = sqlite3.connect("lostlink.db")

    current = conn.execute("""
        SELECT * FROM items
        WHERE id = ?
    """, (item_id,)).fetchone()

    all_items = conn.execute("""
        SELECT * FROM items
        WHERE id != ?
    """, (item_id,)).fetchall()

    conn.close()

    if current is None:
        return "Item not found"

    matches = []

    for item in all_items:

        # Lost → Found
        if current[1] == "Lost" and item[1] != "Found":
            continue

        # Found → Lost
        if current[1] == "Found" and item[1] != "Lost":
            continue

        score = calculate_match(
            current,
            item
        )

        if score >= 30:
            matches.append(
                (item, score)
            )

    matches.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return render_template(
        "matches.html",
        current=current,
        matches=matches
    )


# ---------------- START ----------------

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )