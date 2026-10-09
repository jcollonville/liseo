from liseo.kobo import inspect_kobo, parse_version


VERSION = "N506110012345,1,4.38.21908,4.3.8842,4.3.8842,00000000-0000-0000-0000-000000000376\n"


def test_parse_version_fields():
    info = parse_version(VERSION)
    assert info["serial"] == "N506110012345"
    assert info["firmware"] == "4.38.21908"
    assert info["model_code"] == "376"
    assert info["model_name"] == "Kobo Clara HD"


def test_unknown_model_keeps_the_code():
    info = parse_version("SERIAL,1,4.1.0,4.1.0,4.1.0,00000000-0000-0000-0000-000000000399")
    assert info["model_code"] == "399"
    assert "399" in info["model_name"]


def test_inspect_fake_volume(tmp_path):
    kobo = tmp_path / ".kobo"
    kobo.mkdir()
    (kobo / "version").write_text(VERSION, encoding="utf-8")
    (kobo / "KoboReader.sqlite").write_bytes(b"not-a-book")
    adobe = tmp_path / ".adobe-digital-editions"
    adobe.mkdir()
    (adobe / "activation.xml").write_text("<activation/>", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    library = tmp_path / "Victor Hugo"
    library.mkdir()
    (library / "Les Miserables.epub").write_bytes(b"epub")
    liseo = tmp_path / "Liseo"
    liseo.mkdir()
    (liseo / "Deja la.kepub.epub").write_bytes(b"kepub")
    (tmp_path / ".hidden.epub").write_bytes(b"hidden")

    info = inspect_kobo(tmp_path)
    assert info["is_kobo"] is True
    assert info["error"] is None
    assert info["firmware"] == "4.38.21908"
    assert info["model_name"] == "Kobo Clara HD"
    assert info["authorized"] is True
    assert info["book_count"] == 2
    names = {book["name"] for book in info["books"]}
    assert names == {"Les Miserables.epub", "Deja la.kepub.epub"}


def test_missing_activation_is_reported(tmp_path):
    kobo = tmp_path / ".kobo"
    kobo.mkdir()
    (kobo / "version").write_text(VERSION, encoding="utf-8")
    info = inspect_kobo(tmp_path)
    assert info["is_kobo"] is True
    assert info["authorized"] is False
    assert info["book_count"] == 0


def test_not_a_kobo(tmp_path):
    (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
    info = inspect_kobo(tmp_path)
    assert info["is_kobo"] is False
    assert "kobo" in str(info["error"]).lower()
