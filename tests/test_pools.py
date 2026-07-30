"""Tests for the auto-discovered value-list pool registry."""

from __future__ import annotations

import pytest

from dggen.pools import Pools, UnknownPool
from dggen.rng import Rng


@pytest.fixture
def pools_root(tmp_path):
    (tmp_path / "names").mkdir()
    (tmp_path / "towns").mkdir()

    (tmp_path / "names" / "male-given.txt").write_text(
        "# a comment, ignored\nAlan\n\nBernard\nCarl\n", encoding="utf-8",
    )
    (tmp_path / "towns" / "us.csv").write_text(
        "town,pop\nBigCity,1000\nSmallTown,10\n", encoding="utf-8",
    )
    (tmp_path / "towns" / "single-column.csv").write_text(
        "town\nOnlyTown\nAnotherTown\n", encoding="utf-8",
    )
    return tmp_path


class TestDiscovery:
    def test_finds_txt_and_csv_pools_by_id(self, pools_root):
        pools = Pools(pools_root)
        assert set(pools.ids()) == {"names/male-given", "towns/us", "towns/single-column"}

    def test_missing_root_directory_yields_no_pools(self, tmp_path):
        pools = Pools(tmp_path / "does-not-exist")
        assert pools.ids() == []


class TestTxtParsing:
    def test_comments_and_blank_lines_are_ignored(self, pools_root):
        pools = Pools(pools_root)
        assert pools.values("names/male-given") == ["Alan", "Bernard", "Carl"]


class TestCsvParsing:
    def test_two_column_csv_is_weighted(self, pools_root):
        pools = Pools(pools_root)
        assert pools.values("towns/us") == ["BigCity", "SmallTown"]

    def test_single_column_csv_behaves_like_a_flat_list(self, pools_root):
        pools = Pools(pools_root)
        assert pools.values("towns/single-column") == ["OnlyTown", "AnotherTown"]

    def test_heavily_weighted_value_dominates_choice(self, pools_root):
        pools = Pools(pools_root)
        rng = Rng(0)
        picks = [pools.choice("towns/us", rng) for _ in range(200)]
        assert picks.count("BigCity") > picks.count("SmallTown")


class TestChoice:
    def test_uniform_pool_is_reproducible_under_a_seed(self, pools_root):
        picks_a = [Pools(pools_root).choice("names/male-given", Rng(42)) for _ in range(10)]
        picks_b = [Pools(pools_root).choice("names/male-given", Rng(42)) for _ in range(10)]
        assert picks_a == picks_b


class TestUnknownPool:
    def test_unregistered_id_raises_with_available_ids_listed(self, pools_root):
        pools = Pools(pools_root)
        with pytest.raises(UnknownPool) as exc:
            pools.values("nonexistent/pool")
        message = str(exc.value)
        assert "nonexistent/pool" in message
        assert "names/male-given" in message

    def test_validate_raises_without_returning_a_value(self, pools_root):
        pools = Pools(pools_root)
        with pytest.raises(UnknownPool):
            pools.validate("nonexistent/pool")
        pools.validate("names/male-given")  # does not raise


class TestExternalFileFallback:
    def test_arbitrary_file_path_outside_root_is_usable(self, pools_root, tmp_path):
        external = tmp_path.parent / "external-list.txt"
        external.write_text("X\nY\nZ\n", encoding="utf-8")
        pools = Pools(pools_root)
        assert pools.values(str(external)) == ["X", "Y", "Z"]

    def test_nonexistent_path_still_raises(self, pools_root):
        pools = Pools(pools_root)
        with pytest.raises(UnknownPool):
            pools.values("no/such/file.txt")
