"""Generation is an explicit, ordered list of steps rather than a hand-written sequence of ifs."""

from __future__ import annotations

import pytest

from dggen.character import Character
from dggen.options import GenerationOptions
from dggen.rng import Rng
from dggen.rules.pipeline import PIPELINE, Step, enabled_steps


def test_the_order_is_pinned():
    """The order is the RNG draw order: reordering silently changes every seeded character (and
    the golden snapshot), so a change here should be a deliberate, reviewed diff."""
    assert [step.name for step in PIPELINE] == [
        "demographics",
        "employer",
        "stats",
        "skills",
        "education",
        "veterancy",
        "derived attributes",
    ]


@pytest.mark.parametrize(
    ("options", "expected_missing"),
    [
        (GenerationOptions(), {"veterancy"}),
        (GenerationOptions(veterancy_enabled=True), set()),
        (GenerationOptions(auto_employer=False), {"employer", "veterancy"}),
        (GenerationOptions(auto_education=False), {"education", "veterancy"}),
        (
            GenerationOptions(auto_employer=False, auto_education=False, veterancy_enabled=True),
            {"employer", "education"},
        ),
    ],
    ids=["default", "veterancy", "no-employer", "no-education", "neither-with-veterancy"],
)
def test_options_switch_steps_on_and_off(options, expected_missing):
    ran = {step.name for step in enabled_steps(options)}
    assert {step.name for step in PIPELINE} - ran == expected_missing


def test_every_step_is_a_step_with_a_runnable():
    for step in PIPELINE:
        assert isinstance(step, Step)
        assert callable(step.run)
        assert callable(step.enabled)


class TestCustomPipelines:
    def test_generate_runs_the_given_steps_in_order(self, data):
        calls: list[tuple[str, object]] = []
        steps = (
            Step("first", lambda char, _options: calls.append(("first", char.sex))),
            Step("second", lambda _char, options: calls.append(("second", options.min_age))),
        )
        Character.generate(
            data=data,
            rng=Rng(1),
            sex="female",
            profession=data.professions["agent"],
            options=GenerationOptions(min_age=33),
            pipeline=steps,
        )
        assert calls == [("first", "female"), ("second", 33)]

    def test_a_disabled_step_is_skipped(self, data):
        calls = []
        steps = (
            Step("on", lambda _char, _options: calls.append("on")),
            Step(
                "off", lambda _char, _options: calls.append("off"), enabled=lambda _options: False
            ),
        )
        Character.generate(
            data=data,
            rng=Rng(1),
            sex="male",
            profession=data.professions["agent"],
            pipeline=steps,
        )
        assert calls == ["on"]

    def test_inserting_a_step_changes_the_character(self, data):
        """Adding behaviour is one entry in a list, not an edit to Character.generate."""

        def keen(char, _options):
            char.skills["alertness"] = 99

        steps = (*PIPELINE, Step("keen", keen))
        char = Character.generate(
            data=data,
            rng=Rng(1),
            sex="male",
            profession=data.professions["agent"],
            pipeline=steps,
        )
        assert char.skills["alertness"] == 99

    def test_the_default_pipeline_is_what_generate_uses(self, data):
        def make(**extra):
            return Character.generate(
                data=data,
                rng=Rng(5),
                sex="male",
                profession=data.professions["agent"],
                **extra,
            )

        assert make().stats == make(pipeline=PIPELINE).stats
