"""ui_strings.json (KQ-010): the KidQuest page's child-facing copy is content, validated like the rest."""

import copy
import re

import pytest

from app.domain.kidquest.content import CONTENT_DIR, load_raw, validate_content
from tests.conftest import REPO_ROOT

KIDQUEST_JS = REPO_ROOT / "static" / "js" / "kidquest.js"
PAGE_TEMPLATE = REPO_ROOT / "app" / "web" / "templates" / "kidquest_world.html"
# Keys the page builds at run time from server data: resource names and layout kinds.
DYNAMIC_PREFIXES = ("resources.", "world.kind_")


@pytest.fixture
def raw():
    data, problems = load_raw(CONTENT_DIR)
    assert problems == []
    return copy.deepcopy(data)


def all_keys(raw) -> set[str]:
    return {f"{group}.{key}" for group, entries in raw["ui_strings"]["strings"].items() for key in entries}


def keys_used_by_page() -> set[str]:
    script = KIDQUEST_JS.read_text(encoding="utf-8")
    template = PAGE_TEMPLATE.read_text(encoding="utf-8")
    used = set(re.findall(r"'([a-z_]+\.[a-z_]+)'", script))
    used |= set(re.findall(r"strings\.([a-z_]+\.[a-z_]+)", template))
    used |= {f"entry.{where}" for where in re.findall(r'kidquest_entry\((?:.|\n)*?"(home|quiz)"\s*\)', (REPO_ROOT / "app" / "api" / "routes.py").read_text())}
    return used


def test_shipped_ui_strings_are_valid(raw):
    assert validate_content(raw) == []


def test_every_key_the_page_uses_exists(raw):
    missing = sorted(key for key in keys_used_by_page() if key not in all_keys(raw) and not key.startswith(DYNAMIC_PREFIXES))
    assert missing == []


def test_every_string_is_used(raw):
    used = keys_used_by_page()
    unused = sorted(key for key in all_keys(raw) if key not in used and not key.startswith(DYNAMIC_PREFIXES))
    assert unused == []


def test_dynamic_keys_cover_the_content(raw):
    strings = raw["ui_strings"]["strings"]
    assert set(strings["resources"]) == {"wood", "stone"}  # Every resource in content/kidquest (RESOURCES).
    kinds = {obj["kind"] for obj in raw["layout"]["fixed_objects"]}
    named = {kind for kind in kinds if f"kind_{kind}" in strings["world"]}
    themed = {kind for kind in kinds if all(kind in theme["labels"] for theme in raw["themes"]["themes"])}
    assert named | themed == kinds  # Every fixed object has a child-facing name.


def test_page_script_has_no_child_facing_literals():
    """Copy lives in content: the prototype's literals must not reappear in the production script."""
    script = KIDQUEST_JS.read_text(encoding="utf-8")
    for literal in ("Langkah 1 dari 2", "Ayo hitung kayunya", "Pulau Tunas", "Bahanmu", "Belum tepat", "Kirim<",
                    "Rumah Pertama", "Kampung Ceria", "Hebat!", "kayu yang kurang", "Rp"):
        assert literal not in script, literal


@pytest.mark.parametrize("mutate, message", [
    (lambda s: s["shell"].__setitem__("menu", " "), "strings.shell.menu: must be non-empty"),
    (lambda s: s["reward"].__setitem__("title", "Dapat Rp 50!"), "must not mention money"),
    (lambda s: s["place"].__setitem__("confirm", "Bangun · {price}"), "unknown placeholder(s) price"),
    (lambda s: s["place"].__setitem__("confirm", "Bangun {cost"), "unbalanced brace"),
    (lambda s: s.__setitem__("Bad-Group", {"a": "b"}), "strings.Bad-Group must be a snake_case group"),
    (lambda s: s["shell"].__setitem__("BadKey", "Teks"), "strings.shell.BadKey: key must be lowercase snake_case"),
    (lambda s: s["shell"].__setitem__("menu", 3), "strings.shell.menu: must be non-empty"),
])
def test_invalid_ui_strings_are_reported(raw, mutate, message):
    mutate(raw["ui_strings"]["strings"])
    problems = validate_content(raw)
    assert any(message in problem for problem in problems), problems


def test_ui_strings_must_be_indonesian(raw):
    raw["ui_strings"]["child_facing_language"] = "en"
    assert any("ui_strings.json: child_facing_language must be 'id'" in problem for problem in validate_content(raw))
