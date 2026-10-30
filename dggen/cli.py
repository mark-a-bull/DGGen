"""Command-line interface: argument parsing and the top-level generation loop."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from itertools import cycle, islice
from pathlib import Path

from dggen import __version__, config
from dggen.character import Character
from dggen.data import (
    InvalidLocaleError,
    ProfessionNotFoundError,
    ambiguous_keys,
    find_profession,
    load_data,
)
from dggen.logging_setup import init_logger
from dggen.pdf import SheetWriter
from dggen.pools import PoolError
from dggen.rng import Rng
from dggen.text import TemplateError, format_details, generate_label, parse_date

logger = logging.getLogger("dggen")


def _positive_int(value: str) -> int:
    """argparse type for counts: a whole number of at least 1."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {number}")
    return number


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
        "--pdf",
        action="store_true",
        help="Write a PDF (path set by -o/--output) in addition to printing character details. "
        "Without --pdf, -t/--type is required and defaults to generating one character; with "
        "--pdf, omitting -t generates every profession's full roster as before.",
    )
    doc.add_argument(
        "-o",
        "--output",
        action="store",
        type=Path,
        default=Path(f"DeltaGreenPregen-{datetime.now():%Y-%m-%d-%H-%M}.pdf"),
        help="Output PDF file, only used with --pdf. Defaults to %(default)s.",
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
        type=_positive_int,
        action="store",
        help="Generate this many characters of each profession. Defaults to the profession's "
        "own roster size with --pdf, otherwise 1.",
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
        default=config.DEFAULT_MALE_NAMES,
        help="Pool of male given names - a dggen/data/pools/ id (see "
        "dggen/data/pools/README.md), or a path to your own file. Defaults to %(default)s",
    )
    data.add_argument(
        "--female-given-names",
        action="store",
        default=config.DEFAULT_FEMALE_NAMES,
        help="Pool of female given names - a dggen/data/pools/ id, or a path to your own file. "
        "Defaults to %(default)s",
    )
    data.add_argument(
        "--surnames",
        action="store",
        default=config.DEFAULT_SURNAMES,
        help="Pool of family names - a dggen/data/pools/ id, or a path to your own file. "
        "Defaults to %(default)s",
    )
    data.add_argument(
        "--towns",
        action="store",
        default=config.DEFAULT_TOWNS,
        help="Pool of towns - a dggen/data/pools/ id, or a path to your own file. Use "
        "'towns/uk' for the bundled UK town list. Defaults to %(default)s",
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
        help="Grant additional experience due to age.",
    )
    gen.add_argument(
        "--no-damaged",
        action="store_false",
        dest="damaged",
        help="Don't generate damaged veterans.",
    )
    doc.add_argument(
        "--oconus",
        action="store_true",
        help="Outside of Continental United States?",
    )

    options = parser.parse_args(argv)
    if not options.pdf and not options.type:
        parser.error(
            "-t/--type is required unless --pdf is given (otherwise this would print every "
            "profession's full roster as text). Pass --pdf to generate full rosters as before.",
        )
    if options.min_age < 0:
        parser.error(f"-a/--min-age must not be negative, got {options.min_age}")
    if options.min_age > options.max_age:
        parser.error(
            f"-a/--min-age ({options.min_age}) must not exceed -A/--max-age ({options.max_age})",
        )
    today = datetime.now().date()
    if options.birthdate and options.birthdate > today:
        parser.error(f"--birthdate {options.birthdate} is in the future")
    if options.birth_year and options.birth_year >= today.year:
        parser.error(f"--birth-year must be before {today.year}, got {options.birth_year}")
    if options.pdf and not options.output.resolve().parent.is_dir():
        # Fail now, not after the whole roster has been generated.
        parser.error(f"-o/--output directory does not exist: {options.output.resolve().parent}")
    return options


def main(argv: list[str] | None = None) -> int:
    # Names from --names locales (or --name) can be non-Latin, and a redirected Windows stdout is
    # often a legacy codepage that can't encode them. Degrade the console text rather than letting
    # the print abort the whole run before the PDF is written.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    options = get_options(argv)
    init_logger(options.verbosity)
    logger.debug(options)

    rng = Rng(options.seed)

    try:
        data = load_data(options, rng)
        professions = (
            [find_profession(data.professions, options.type)]
            if options.type
            else list(data.professions.values())
        )
    except (
        ProfessionNotFoundError,
        PoolError,
        InvalidLocaleError,
        OSError,
        json.JSONDecodeError,
        TemplateError,
    ) as exc:
        logger.error("%s", exc)
        return 2

    if options.type and (candidates := ambiguous_keys(data.professions, options.type)):
        # Not a logger.warning: that is hidden unless -v is given, and this changes the output.
        print(
            f"note: {options.type!r} matches {len(candidates)} professions "
            f"({', '.join(candidates)}); using {candidates[0]}. Pass a key to choose.",
            file=sys.stderr,
        )

    writer = None
    pages_per_sheet = 2 if options.equip else 1
    if options.pdf:
        writer = SheetWriter(options.output, pages_per_sheet=pages_per_sheet)
        writer.add_cover(options.title, options.oconus)
        if len(professions) > 1:
            writer.generate_toc(professions, pages_per_sheet, options.count)

    for profession in professions:
        if writer:
            writer.bookmark(generate_label(profession))
        count = options.count or (profession.number_to_generate if options.pdf else 1)
        for sex in islice(
            cycle([options.sex] if options.sex else ["female", "male"]),
            count,
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

            print(format_details(character))
            print()

            if writer:
                writer.add_page(character.d)
                if pages_per_sheet >= 2:
                    writer.add_page_2(character.e)

    if writer:
        writer.save_pdf()
        logger.info("Wrote %s", options.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
