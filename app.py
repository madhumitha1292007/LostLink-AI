from flask import Flask, render_template, request, redirect
import sqlite3
from difflib import SequenceMatcher
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ================= DATABASE =================

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

    # Add image column if missing
    if "image" not in column_names:
        conn.execute(
            "ALTER TABLE items ADD COLUMN image TEXT"
        )

    # Add delete PIN column if missing
    if "delete_pin" not in column_names:
        conn.execute(
            "ALTER TABLE items ADD COLUMN delete_pin TEXT"
        )

    conn.commit()
    conn.close()


# ================= AI MATCHING =================

def similarity(text1, text2):
    return SequenceMatcher(
        None,
        str(text1).lower().strip(),
        str(text2).lower().strip()
    ).ratio()


def calculate_match(item1, item2):

    # Item name = 50%
    name_score = similarity(
        item1[2],
        item2[2]
    )

    # Description = 30%
    description_score = similarity(
        item1[3],
        item2[3]
    )

    # Location = 20%
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


# ================= HOME PAGE =================

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


# ================= REPORT ITEM =================

@app.route("/report", methods=["POST"])
def report():

    item_type = request.form["item_type"]
    item_name = request.form["item_name"]
    description = request.form["description"]
    location = request.form["location"]
    contact = request.form["contact"]

    # Delete PIN
    delete_pin = request.form["delete_pin"]

    # Image upload
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

    # Save to database
    conn = sqlite3.connect("lostlink.db")

    conn.execute("""
        INSERT INTO items
        (
            item_type,
            item_name,
            description,
            location,
            contact,
            image,
            delete_pin
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        item_type,
        item_name,
        description,
        location,
        contact,
        image_name,
        delete_pin
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# ================= AI MATCH =================

@app.route("/match/<int:item_id>")
def match(item_id):

    conn = sqlite3.connect("lostlink.db")

    # Current item
    current = conn.execute("""
        SELECT * FROM items
        WHERE id = ?
    """, (item_id,)).fetchone()

    # Other items
    all_items = conn.execute("""
        SELECT * FROM items
        WHERE id != ?
    """, (item_id,)).fetchall()

    conn.close()

    if current is None:
        return "Item not found"

    matches = []

    for item in all_items:

        # Lost item should match Found item
        if current[1] == "Lost" and item[1] != "Found":
            continue

        # Found item should match Lost item
        if current[1] == "Found" and item[1] != "Lost":
            continue

        score = calculate_match(
            current,
            item
        )

        # Only show matches above 30%
        if score >= 30:
            matches.append(
                (item, score)
            )

    # Highest score first
    matches.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return render_template(
        "matches.html",
        current=current,
        matches=matches
    )


# ================= DELETE REPORT =================

@app.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):

    # PIN entered by user
    pin = request.form["delete_pin"]

    conn = sqlite3.connect("lostlink.db")

    # Get stored PIN + image
    item = conn.execute("""
        SELECT delete_pin, image
        FROM items
        WHERE id = ?
    """, (item_id,)).fetchone()

    # Report doesn't exist
    if item is None:

        conn.close()

        return "Report not found"


    stored_pin = item[0]
    image_name = item[1]


    # Check PIN
    if stored_pin != pin:

        conn.close()

        return """
        <h2>❌ Wrong Delete PIN</h2>
        <p>Please enter the PIN you created while reporting this item.</p>
        <a href="/">Go Back</a>
        """


    # Delete database record
    conn.execute("""
        DELETE FROM items
        WHERE id = ?
    """, (item_id,))

    conn.commit()
    conn.close()


    # Delete uploaded image also
    if image_name:

        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            image_name
        )

        if os.path.exists(image_path):

            try:
                os.remove(image_path)
            except:
                pass


    return redirect("/")


# ================= START APP =================

# Initialize database when app starts
init_db()


if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )