"""Crosswalks: committed files validate; counting rules hold."""

from pathlib import Path

from oab.crosswalk import Crosswalk, coverage, load_crosswalks, text_digest, validate_crosswalk

ROOT = Path(__file__).resolve().parent.parent

FRAMEWORK = {
    "id": "demo",
    "version": "1",
    "title": "Demo",
    "publisher": "Demo",
    "source": "https://example.org",
    "denominators": {"X": 10},
}


def _mapping(**overrides) -> dict:
    base = {
        "generator": "bank-recon-missing-fee",
        "target_id": "X.I.A",
        "target_item": 1,
        "relationship": "subset-of",
        "rationale": "semantic",
        "strength": 7,
        "status": "proposed",
        "comment": "demo",
    }
    return {**base, **overrides}


def _cw(*mappings: dict) -> Crosswalk:
    return Crosswalk(Path("demo.toml"), FRAMEWORK, list(mappings))


def test_committed_crosswalks_validate():
    crosswalks = load_crosswalks(ROOT / "crosswalks")
    assert crosswalks
    for cw in crosswalks:
        assert validate_crosswalk(cw) == [], cw.path


def test_rejects_unknown_generator_and_bad_vocabulary():
    failures = validate_crosswalk(
        _cw(_mapping(generator="nope", relationship="related", rationale="vibes"))
    )
    assert any("generator" in f for f in failures)
    assert any("relationship" in f for f in failures)
    assert any("rationale" in f for f in failures)


def test_strength_ten_reserved_for_equal():
    assert validate_crosswalk(_cw(_mapping(strength=10)))
    assert validate_crosswalk(_cw(_mapping(relationship="equal", strength=9)))
    assert not validate_crosswalk(_cw(_mapping(relationship="equal", strength=10)))


def test_reviewed_needs_reviewer_and_target_in_denominators():
    assert validate_crosswalk(_cw(_mapping(status="reviewed")))
    assert not validate_crosswalk(_cw(_mapping(status="reviewed", reviewer="CPA reviewer")))
    assert validate_crosswalk(_cw(_mapping(target_id="Y.I.A")))


def test_duplicate_mapping_rejected():
    assert validate_crosswalk(_cw(_mapping(), _mapping()))


def test_coverage_counts_each_item_once_by_strongest_link():
    cw = _cw(
        _mapping(relationship="intersects-with", strength=3),
        _mapping(generator="classify-operating-expense", relationship="superset-of", strength=8),
        _mapping(target_item=2, relationship="superset-of", strength=6),
        _mapping(target_item=3, relationship="intersects-with", strength=2),
    )
    counts = coverage(cw)["X"]
    # Item 1 covered once; a weak superset-of only counts as touched.
    assert counts == {
        "total": 10,
        "covered": 1,
        "partial": 0,
        "touched": 2,
        "unreviewed": 3,
    }


def test_subset_of_is_partial_not_covered():
    counts = coverage(_cw(_mapping(strength=9)))["X"]
    assert (counts["covered"], counts["partial"]) == (0, 1)


def test_text_digest_folds_case_and_whitespace():
    assert text_digest("Reconcile  the\ncash.") == text_digest("reconcile the cash.")
    assert text_digest("a").startswith("sha256:")
