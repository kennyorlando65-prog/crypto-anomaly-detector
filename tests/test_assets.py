"""Tests for the tracked asset list."""

from __future__ import annotations

from engine.assets import DEFAULT_ASSETS, MAX_ASSETS, tracked_assets


def test_default_asset_count_is_eight():
    """The shipped default is 8, chosen for the free-tier budget."""
    assert len(DEFAULT_ASSETS) == 8


def test_default_assets_have_required_fields():
    """Every asset needs an id, a symbol and a name for the UI."""
    for asset in DEFAULT_ASSETS:
        assert asset["id"] and asset["symbol"] and asset["name"]


def test_default_asset_ids_are_unique():
    """A duplicate id would double-count an asset in every aggregate."""
    ids = [a["id"] for a in DEFAULT_ASSETS]
    assert len(ids) == len(set(ids))


def test_env_override_selects_assets(monkeypatch):
    """A comma-separated override must narrow the list."""
    monkeypatch.setenv("TRACKED_ASSETS", "bitcoin,ethereum")
    selected = tracked_assets()
    assert [a["id"] for a in selected] == ["bitcoin", "ethereum"]


def test_env_override_is_capped(monkeypatch):
    """The hard ceiling must be enforced, not merely documented."""
    monkeypatch.setenv("TRACKED_ASSETS", ",".join(f"coin{i}" for i in range(100)))
    assert len(tracked_assets()) == MAX_ASSETS


def test_blank_env_override_falls_back_to_defaults(monkeypatch):
    """An empty override must not produce an empty dashboard."""
    monkeypatch.setenv("TRACKED_ASSETS", "   ")
    assert tracked_assets() == DEFAULT_ASSETS


def test_unknown_ids_are_passed_through(monkeypatch):
    """CoinGecko is the authority on what exists, so unknown ids pass through."""
    monkeypatch.setenv("TRACKED_ASSETS", "some-new-coin")
    selected = tracked_assets()
    assert selected[0]["id"] == "some-new-coin"
    assert selected[0]["symbol"] == "SOME-N"
