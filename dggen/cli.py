"""Command-line interface: argument parsing and the top-level generation loop."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from itertools import cycle, islice
from pathlib import Path

from dggen import __version__, config
from dggen.character import Character
from dggen.data import ProfessionNotFound, find_profession, load_data
from dggen.pdf import SheetWriter
from dggen.rng import Rng
from dggen.logging_setup import init_logger
from dggen.text import generate_label, parse_date

logger = logging.getLogger("dggen")


def get_options(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse options and arguments. `argv` defaults to sys.argv[1:] (override for testing)."""
    parser = argparse.ArgumentParser(description=config.DESCRIPTION)
    gen = parser.add_argument_group(
        title="Character generation",
        description="Character generation options",
    )
    data = parser.add_argument_group(title="Data", description="Data file locations")
    doc = parser.add_argument_group(title="Document options", description="Document options")
    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        default=0,
        help="specify up to three times to increase verbosity, "
        "i.e. -v to see warnings, -vv for information messages, or -vvv for debug messages.",
    )
    parser.add_argument("-V", "--version", action="version", version=__version__)
    doc.add_argument(
        "-o",
        "--output",
        action="store",
        type=Path,
        default=Path(f"DeltaGreenPregen-{datetime.now():%Y-%m-%d-%H-%M}.pdf"),
        help="Output PDF file. Defaults to %(default)s.",
    )
    gen.add_argument(
        "-t",
        "--type",
        action="store",
        help="Select single profession to generate. Accepts either the profession's data key "
        "(e.g. 'agent') or its display label (e.g. 'Federal Agent'), case-insensitive.",
    )
    doc.add_argument("-T", "--title", action="store", help="Document title for cover page.")
    gen.add_argument("-l", "--label", action="store", help="Override profession label.")
    gen.add_argument(
        "-c",
        "--count",
        type=int,
        action="store",
        help="Generate this many characters of each profession.",
    )
    gen.add_argument(
        "-e",
        "--employer",
        action="store",
        help="Set employer for all generated characters, overriding the profession's own "
        "employer/division (if any) and the auto-generated value.",
    )
    gen.add_argument(
        "--no-employer",
        action="store_false",
        dest="auto_employer",
        default=True,
        help="Don't auto-generate an employer for professions that don't already specify one; "
        "leave the field blank unless --employer is also given.",
    )
    gen.add_argument(
        "--name",
        action="store",
        help="Override generated name. Accepts either the sheet's 'SURNAME, Given' order "
        "directly, or natural reading order (e.g. 'Given Surname'), which is reformatted "
        "automatically. Best used with -c 1.",
    )
    gen.add_argument(
        "--education",
        action="store",
        help="Set education and occupational history for all generated characters, overriding "
        "the auto-generated value.",
    )
    gen.add_argument(
        "--no-education",
        action="store_false",
        dest="auto_education",
        default=True,
        help="Don't auto-generate education/occupational history; leave the field blank unless "
        "--education is also given.",
    )
    gen.add_argument(
        "--sex",
        action="store",
        choices=["male", "female"],
        help="Set sex for all generated characters, instead of alternating.",
    )
    gen.add_argument(
        "--birth-year",
        action="store",
        type=int,
        help="Set exact birth year for all generated characters, instead of a random age.",
    )
    gen.add_argument(
        "--birthdate",
        action="store",
        type=parse_date,
        help="Set exact birthdate for all generated characters, e.g. '1986-11-24' or "
        "'November 24, 1986'. Takes precedence over --birth-year.",
    )
    gen.add_argument(
        "--seed",
        action="store",
        type=int,
        default=None,
        help="Seed the random number generator for reproducible output. Same seed + same options "
        "yields identical characters.",
    )
    gen.add_argument(
        "-u",
        "--unequipped",
        action="store_false",
        dest="equip",
        help="Don't generate equipment.",
        default=True,
    )

    data.add_argument(
        "--names",
        nargs="?",
        const="en_US",
        default=None,
        metavar="LOCALE",
        help="Use Faker for person name generation instead of data files. "
        "Optionally specify locale, e.g. en_GB (default: en_US).",
    )
    data.add_argument(
        "--professions",
        action="store",
        type=Path,
        default=config.DEFAULT_PROFESSIONS,
        help="Data file for professions - defaults to %(default)s",
    )
    data.add_argument(
        "--male-given-names",
        action="store",
        type=Path,
        default=config.DEFAULT_MALE_NAMES,
        help="Data file for male given names - defaults to %(default)s",
    )
    data.add_argument(
        "--female-given-names",
        action="store",
        type=Path,
        default=config.DEFAULT_FEMALE_NAMES,
        help="Data file for female given names - defaults to %(default)s",
    )
    data.add_argument(
        "--surnames",
        action="store",
        type=Path,
        default=config.DEFAULT_SURNAMES,
        help="Data file for family names - defaults to %(default)s",
    )
    data.add_argument(
        "--towns",
        action="store",
        type=Path,
        default=config.DEFAULT_TOWNS,
        help="Data file for towns - defaults to %(default)s",
    )
    data.add_argument(
        "--equipment",
        action="store",
        type=Path,
        default=config.DEFAULT_EQUIPMENT,
        help="Data file for equipment - defaults to %(default)s",
    )
    data.add_argument(
        "--distinguishing-features",
        action="store",
        type=Path,
        default=config.DEFAULT_DISTINGUISHING,
        help="Data file for distinguishing features - defaults to %(default)s",
    )
    data.add_argument(
        "--education-data",
        action="store",
        type=Path,
        default=config.DEFAULT_EDUCATION_DATA,
        help="Data file for auto-generated education/occupational history - defaults to "
        "%(default)s",
    )
    data.add_argument(
        "--employer-data",
        action="store",
        type=Path,
        default=config.DEFAULT_EMPLOYER_DATA,
        help="Data file for auto-generated employers - defaults to %(default)s",
    )
    gen.add_argument(
        "-a",
        "--min-age",
        action="store",
        type=int,
        help="Minimum age of characters - defaults to %(default)s.",
        default=25,
    )
    gen.add_argument(
        "-A",
        "--max-age",
        action="store",
        type=int,
        help="Maximum age of characters - defaults to %(default)s.",
        default=55,
    )
    gen.add_argument(
        "-n",
        "--nationality",
        default="U.S.A.",
        action="store",
        help="Set nationality for all generated characters.",
    )
    gen.add_argument(
        "--veterancy",
        action="store_true",
        dest="veterancy",
        help="Grant additional experience due to age.",
        default=False,
    )
    gen.add_argument(
        "--no-damaged",
        action="store_false",
        dest="damaged",
        help="Don't generate damaged veterans.",
        default=True,
    )
    doc.add_argument(
        "--oconus",
        action="store_true",
        dest="oconus",
        help="Outside of Continental United States?",
        default=False,
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = get_options(argv)
    init_logger(options.verbosity)
    logger.debug(options)

    rng = Rng(options.seed)
    data = load_data(options, rng)

    try:
        professions = (
            [find_profession(data.professions, options.type)]
            if options.type
            else list(data.professions.values())
        )
    except ProfessionNotFound as exc:
        logger.error("%s", exc)
        return 2

    pages_per_sheet = 2 if options.equip else 1
    writer = SheetWriter(options.output, pages_per_sheet=pages_per_sheet)
    writer.add_cover(options.title, options.oconus)
    if len(professions) > 1:
        writer.generate_toc(professions, pages_per_sheet)

    for profession in professions:
        writer.bookmark(generate_label(profession))
        for sex in islice(
            cycle([options.sex] if options.sex else ["female", "male"]),
            options.count or profession.number_to_generate,
        ):
            character = Character.generate(
                data=data,
                rng=rng,
                sex=sex,
                profession=profession,
                label_override=options.label,
                employer_override=options.employer,
                name_override=options.name,
                education_override=options.education,
                min_age=options.min_age,
                max_age=options.max_age,
                birth_year=options.birth_year,
                birthdate=options.birthdate,
                nationality=options.nationality,
                veterancy_enabled=options.veterancy,
                damaged=options.damaged,
                auto_education=options.auto_education,
                auto_employer=options.auto_employer,
            )
            if options.equip:
                character.equip(profession.equipment_kit)
            character.print_footnotes()

            writer.add_page(character.d)
            if pages_per_sheet >= 2:
                writer.add_page_2(character.e)

    writer.save_pdf()
    logger.info("Wrote %s", options.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
