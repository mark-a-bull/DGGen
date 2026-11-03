"""One seed reproduces a whole roster: the RNG is the only source of randomness and the clock is
injectable, so results don't depend on which `Data` object was loaded or what day it is."""

from __future__ import annotations

import re
from datetime import date

from dggen import character as character_module
from dggen.data import load_data
from dggen.options import DataSources, GenerationOptions
from dggen.rng import Rng
from dggen.roster import generate_roster


def _names(data, seed, professions=("agent",), count=4):
    chosen = [data.professions[key] for key in professions]
    roster = generate_roster(data, Rng(seed), chosen, GenerationOptions(), count=count)
    return [char.name for _, char in roster]


class TestDataHoldsNoRandomness:
    def test_one_loaded_data_serves_any_number_of_seeds(self):
        data = load_data(DataSources())
        assert _names(data, 7) == _names(data, 7)  # same seed, same data object: same names
        assert _names(data, 7) != _names(data, 8)

    def test_two_separately_loaded_data_objects_agree(self):
        assert _names(load_data(DataSources()), 3) == _names(load_data(DataSources()), 3)

    def test_the_fixture_data_works_with_any_seed(self, data):
        assert _names(data, 11) == _names(data, 11)

    def test_faker_names_come_from_the_same_stream(self):
        """`--names` used its own generator, so --seed did not govern it with everything else."""
        data = load_data(DataSources(names_locale="en_US"))
        assert _names(data, 5) == _names(data, 5)
        assert _names(data, 5) != _names(data, 6)


class TestTheClockIsInjectable:
    def test_age_is_measured_against_the_injected_day(self, make_character):
        char = make_character(birthdate=date(1990, 6, 1), today=date(2020, 6, 1))
        assert char.age == 30
        assert make_character(birthdate=date(1990, 6, 1), today=date(2020, 5, 31)).age == 29

    def test_birth_year_age_uses_the_injected_day(self, make_character):
        char = make_character(birth_year=1990, today=date(2020, 12, 31))
        assert char.age == 30  # every possible birthday in 2020 has passed by Dec 31

    def test_default_day_is_today(self, make_character):
        assert make_character().today == date.today()

    def test_education_year_follows_the_injected_day(self, make_character, data):
        today = date(2020, 6, 1)
        char = make_character(birthdate=date(1990, 6, 1), today=today)  # age 30
        match = re.search(r"(\d{4})\.$", char.education)
        assert match, char.education
        year = int(match.group(1))
        grad_ages = {tier.grad_age for tier in data.education.tier_defaults.values()}
        assert year <= today.year
        assert (char.age - (today.year - year)) in grad_ages  # grad_age = age - years since


def test_the_real_clock_is_never_read_when_a_date_is_supplied(make_character, monkeypatch):
    """Anything that reads the real date makes results depend on when the suite runs (the golden
    snapshot would have started failing on 1 January 2027). A supplied `today` must be enough."""

    class NoClock(date):
        @classmethod
        def today(cls):
            raise AssertionError("the real clock was read")

    monkeypatch.setattr(character_module, "date", NoClock)
    char = make_character(
        today=date(2020, 1, 1), birthdate=date(1990, 6, 1), veterancy_enabled=True
    )
    assert char.today == date(2020, 1, 1)
    assert char.age == 29
