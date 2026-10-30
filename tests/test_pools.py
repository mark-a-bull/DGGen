"""Tests for the auto-discovered value-list pool registry."""

from __future__ import annotations

import pytest

from dggen.pools import InvalidPoolError, PoolError, Pools, UnknownPoolError
from dggen.rng import Rng


@pytest.fixture
def pools_root(tmp_path):
    (tmp_path / "names").mkdir()
    (tmp_path / "towns").mkdir()

    (tmp_path / "names" / "male-given.txt").write_text(
        "# a comment, ignored\nAlan\n\nBernard\nCarl\n",
        encoding="utf-8",
    )
    (tmp_path / "towns" / "us.csv").write_text(
        "town,pop\nBigCity,1000\nSmallTown,10\n",
        encoding="utf-8",
    )
    (tmp_path / "towns" / "single-column.csv").write_text(
        "town\nOnlyTown\nAnotherTown\n",
        encoding="utf-8",
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
        with pytest.raises(UnknownPoolError) as exc:
            pools.values("nonexistent/pool")
        message = str(exc.value)
        assert "nonexistent/pool" in message
        assert "names/male-given" in message

    def test_validate_raises_without_returning_a_value(self, pools_root):
        pools = Pools(pools_root)
        with pytest.raises(UnknownPoolError):
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
        with pytest.raises(UnknownPoolError):
            pools.values("no/such/file.txt")


class TestMalformedFiles:
    """A bad pool file must fail up front with a message naming the file, not as a raw
    IndexError/ValueError partway through generating a roster."""

    @staticmethod
    def _pool(tmp_path, name, content, *, binary=False):
        path = tmp_path / name
        if binary:
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return Pools(tmp_path / "none")  # no discovered pools; we pass the file path instead

    @pytest.mark.parametrize(
        ("name", "content", "fragment"),
        [
            ("ragged.csv", "town,pop\nA,5\nB\n", "missing a weight"),
            ("words.csv", "town,pop\nA,lots\n", "not a whole number"),
            ("thousands.csv", "town,pop\nA,1,000\n", "more than 2 columns"),
            ("negative.csv", "town,pop\nA,-3\n", "negative"),
            ("allzero.csv", "town,pop\nA,0\nB,0\n", "weights are all zero"),
            ("empty.txt", "", "no values"),
            ("comments-only.txt", "# nothing here\n\n", "no values"),
            ("header-only.csv", "town,pop\n", "no values"),
        ],
    )
    def test_bad_content_raises_invalid_pool_naming_the_file(
        self,
        tmp_path,
        name,
        content,
        fragment,
    ):
        pools = self._pool(tmp_path, name, content)
        with pytest.raises(InvalidPoolError) as exc:
            pools.validate(str(tmp_path / name))
        assert name in str(exc.value)
        assert fragment in str(exc.value)

    def test_non_utf8_file_raises_invalid_pool(self, tmp_path):
        pools = self._pool(tmp_path, "latin.txt", "caf\xe9\n".encode("latin-1"), binary=True)
        with pytest.raises(InvalidPoolError, match="UTF-8"):
            pools.validate(str(tmp_path / "latin.txt"))

    def test_bad_bundled_style_file_fails_at_construction(self, tmp_path):
        (tmp_path / "broken.csv").write_text("town,pop\nA,lots\n", encoding="utf-8")
        with pytest.raises(InvalidPoolError):
            Pools(tmp_path)

    def test_both_errors_share_a_base_class_the_cli_can_catch(self):
        assert issubclass(InvalidPoolError, PoolError)
        assert issubclass(UnknownPoolError, PoolError)

    def test_utf8_bom_is_not_part_of_the_first_value(self, tmp_path):
        path = tmp_path / "bom.txt"
        path.write_bytes(b"\xef\xbb\xbfAlpha\nBeta\n")
        assert Pools(tmp_path / "none").values(str(path)) == ["Alpha", "Beta"]

    def test_utf8_bom_csv(self, tmp_path):
        path = tmp_path / "bom.csv"
        path.write_bytes(b"\xef\xbb\xbftown,pop\nAlpha,2\n")
        assert Pools(tmp_path / "none").values(str(path)) == ["Alpha"]

    def test_indented_comment_line_is_still_a_comment(self, tmp_path):
        path = tmp_path / "indented.txt"
        path.write_text("Alpha\n   # a note\nBeta\n", encoding="utf-8")
        assert Pools(tmp_path / "none").values(str(path)) == ["Alpha", "Beta"]

    def test_zero_weight_rows_are_allowed_but_never_chosen(self, tmp_path):
        path = tmp_path / "some-zero.csv"
        path.write_text("town,pop\nNever,0\nAlways,5\n", encoding="utf-8")
        pools = Pools(tmp_path / "none")
        assert {pools.choice(str(path), Rng(seed)) for seed in range(30)} == {"Always"}
