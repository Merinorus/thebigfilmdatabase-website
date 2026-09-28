import pytest

pytest.importorskip("nh3", reason="Import checks require the install dependency group")

from app.utils.text import clean_imported_text, validate_imported_text


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('Agfa… <i>"ADOX HR-50"</i>', 'Agfa… "ADOX HR-50"'),
        ("IR = <b>I</b>sopan <b>R</b>ecord", "IR = Isopan Record"),
        ("<p>First<br>second</p><p>Third</p>", "First second Third"),
        ("<ul><li>First</li><li>Second</li></ul>", "First Second"),
        ("B&amp;W &lt; 100 &gt; 50 &#233; &quot;film&quot;", 'B&W < 100 > 50 é "film"'),
        ("Fujicolor 業務記錄用 – café", "Fujicolor 業務記錄用 – café"),
        ("  Film\xa0 \t100\n  ISO  ", "Film 100 ISO"),
        ('<script>alert(1)</script><style>body{}</style><!--hidden--><b onclick="x()">Film</b>', "Film"),
        ("<i>Unclosed", "Unclosed"),
        ("", ""),
        ("B&W < 100", "B&W < 100"),
        ('<a href="javascript:alert(1)">Film</a><img src=x onerror="alert(1)">', "Film"),
        ('<svg onload="alert(1)"></svg><iframe src="javascript:alert(1)"></iframe>Film', "Film"),
        ("&lt;script&gt;alert(1)&lt;/script&gt;", "<script>alert(1)</script>"),
    ],
)
def test_clean_imported_text(source, expected):
    assert clean_imported_text(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "<script>alert(1)</script>",
        '<b onclick="alert(1)">Film</b>',
        '<a href="jav&#x61;script:alert(1)">Film</a>',
        '<a href="java&#10;script:alert(1)">Film</a>',
        '<a href="data:text/html,x">Film</a>',
        '<span style="background:url(x)">Film</span>',
        '<iframe srcdoc="x"></iframe>',
        "<svg/onload=alert(1)>",
        "<math>x</math>",
        "&lt;script&gt;alert(1)&lt;/script&gt;",
        "&amp;lt;img src=x onerror=alert(1)&amp;gt;",
    ],
)
def test_import_guard_rejects_active_content(source):
    with pytest.raises(ValueError):
        validate_imported_text(source)


@pytest.mark.parametrize(
    "source",
    [
        "IR = <b>I</b>sopan <b>R</b>ecord",
        "Film < 1947",
        "FiLM>iN",
        "B&W",
        '<a href="https://example.com">Film</a>',
        "<i>Unclosed",
        "Film &amp; Co",
    ],
)
def test_import_guard_accepts_text_and_formatting(source):
    validate_imported_text(source)


@pytest.mark.parametrize("column", range(12))
def test_import_rejects_attack_in_any_column_before_touching_database(tmp_path, monkeypatch, column):
    import csv
    import sqlite3

    pytest.importorskip("pandas")
    from app.config import settings
    from app.install import update_db

    db_path = tmp_path / "films.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE films (name TEXT)")
        db.execute("INSERT INTO films VALUES ('Existing film')")
    original = db_path.read_bytes()
    row = ["12", "100123", "Film", "", "", "4", "", "", "", "", "2", "film.jpg"]
    row[column] = "<script>alert(1)</script>"
    with (tmp_path / "film_database.csv").open("w", newline="") as output:
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["header"] * 12)
        writer.writerow(row)
    monkeypatch.setattr(settings, "FILM_DATABASE_REPO_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DB_SQLITE_FILEPATH", str(db_path))
    with pytest.raises(ValueError, match="Unsafe CSV content at record 2, column"):
        update_db()
    assert db_path.read_bytes() == original


@pytest.mark.parametrize("picture", ["https://evil.test/a.jpg", "../a.jpg", "x.svg", "javascript:alert(1)"])
def test_import_rejects_unsafe_picture(tmp_path, monkeypatch, picture):
    import csv

    pytest.importorskip("pandas")
    from app.config import settings
    from app.install import update_db

    with (tmp_path / "film_database.csv").open("w", newline="") as output:
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["header"] * 12)
        writer.writerow(["", "", "Film", "", "", "", "", "", "", "", "2", picture])
    db_path = tmp_path / "films.db"
    monkeypatch.setattr(settings, "FILM_DATABASE_REPO_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DB_SQLITE_FILEPATH", str(db_path))
    with pytest.raises(ValueError, match="column picture"):
        update_db()
    assert not db_path.exists()


def test_import_cleans_text_and_preserves_slugs(tmp_path, monkeypatch):
    import csv
    import sqlite3

    pytest.importorskip("pandas")
    from app.config import settings
    from app.install import update_db
    from app.utils.url import UniqueUrlGenerator, normalize_unique_slugs

    names = ["Film\xa0  100", "Film\xa0  100"]
    with (tmp_path / "film_database.csv").open("w", newline="") as output:
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["header"] * 12)
        for name in names:
            writer.writerow(
                [
                    "12",
                    "100123",
                    name,
                    "<b>I</b>sopan<br>Film &amp; Co",
                    "<i>Maker</i>",
                    "4",
                    "",
                    "",
                    "",
                    "",
                    "2",
                    "film.jpg",
                ]
            )
    db_path = tmp_path / "films.db"
    monkeypatch.setattr(settings, "FILM_DATABASE_REPO_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DB_SQLITE_FILEPATH", str(db_path))
    update_db()
    generator = UniqueUrlGenerator(normalize=False)
    expected_slugs = normalize_unique_slugs([generator.generate(name) for name in names])
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT name, og_film_or_information, manufacturer, url_name, dx_extract, dx_full, picture FROM films ORDER BY rowid"
        ).fetchall()
        assert [row[3] for row in rows] == expected_slugs
        assert rows[0][:3] == ("Film 100", "Isopan Film & Co", "Maker")
        assert rows[0][4:] == ("0012", "100123", "film.jpg")
        assert db.execute("SELECT count(*) FROM films WHERE films MATCH 'Isopan'").fetchone()[0] == len(names)

    # An invalid import must leave the previous database intact.
    with (tmp_path / "film_database.csv").open("w", newline="") as output:
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["header"] * 12)
        writer.writerow(["", "", "<i></i>", "", "", "", "", "", "", "", "2", ""])
    with pytest.raises(ValueError, match="names must not be empty"):
        update_db()
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM films").fetchone()[0] == len(names)
