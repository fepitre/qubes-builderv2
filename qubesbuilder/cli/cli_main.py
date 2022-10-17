# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2022 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
QubesBuilder command-line interface.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import click

from qubesbuilder.cli.cli_base import ContextObj, aliased_group
from qubesbuilder.cli.cli_config import config
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.cli.cli_installer import installer
from qubesbuilder.cli.cli_package import package
from qubesbuilder.cli.cli_repository import repository
from qubesbuilder.cli.cli_template import template
from qubesbuilder.common import STAGES, str_to_bool
from qubesbuilder.config import Config, deep_merge
from qubesbuilder.log import get_logger, init_logging

log = get_logger("cli")

ALLOWED_KEY_PATTERN = r"[A-Za-z0-9_+-]+"


# Function to validate allowed key values in a dict
def validate_identifier(identifier):
    if re.match(ALLOWED_KEY_PATTERN, identifier) and not any(
        [
            identifier in ("-", "_"),
            identifier.startswith("-"),
            identifier.endswith("-"),
            identifier.startswith("_"),
            identifier.endswith("_"),
        ]
    ):
        return

    raise ValueError(f"Invalid key identifier found: '{identifier}'.")


def parse_dict_from_cli(s):
    index_dict = None
    index_array = None

    # Determine if split identifier "+" or ":" is present
    if ":" in s:
        index_dict = s.index(":")
    # We may have '+components', '+plugins', etc.
    if "+" in s[1:]:
        index_array = s[1:].index("+") + 1

    # If both are present, find the first one and split according to the first one
    if index_dict and index_array:
        split_identifier = ":" if index_dict < index_array else "+"
    elif index_dict:
        split_identifier = ":"
    elif index_array:
        split_identifier = "+"
    else:
        split_identifier = None

    # If no split identifier is found, there is nothing more to parse
    if split_identifier:
        if split_identifier == "+" and s.startswith("+"):
            parsed_identifier, remaining_content = s[1:].split(split_identifier, 1)
            parsed_identifier = "+" + parsed_identifier
        else:
            parsed_identifier, remaining_content = s.split(split_identifier, 1)
    else:
        remaining_content = None
        parsed_identifier = s

    if remaining_content:
        # Validate key
        validate_identifier(parsed_identifier)

        if split_identifier == ":":
            if "=" not in remaining_content:
                raise ValueError(f"Cannot find '=' in '{remaining_content}'")
            result = {parsed_identifier: parse_dict_from_cli(remaining_content)}
        else:
            result = {parsed_identifier: [parse_dict_from_cli(remaining_content)]}
    else:
        if "=" not in s:
            result = s
        else:
            if s.count("=") != 1:
                raise ValueError("Too much '=' found.")
            key, val = s.split("=", 1)

            # Validate key
            validate_identifier(key)

            if val.lower() in ("true", "false", "1", "0"):
                val = str_to_bool(val)
            result = {key: val}
    return result


def parse_config_from_cli(array):
    result: Dict[str, Any] = {}
    for s in array:
        parsed_dict = parse_dict_from_cli(s)
        result = deep_merge(result, parsed_dict, allow_append=True)
    return result


def init_context_obj(
    builder_conf: str,
    verbose: int = None,
    debug: bool = None,
    log_file: str = None,
    component: Optional[List] = None,
    distribution: Optional[List] = None,
    template: Optional[List] = None,
    option: List = None,
):

    try:
        options = parse_config_from_cli(option) if option else {}
    except ValueError as e:
        raise CliError(f"Failed to parse CLI options: '{str(e)}'")

    config = Config(conf_file=builder_conf, options=options)
    obj = ContextObj(config)

    # verbose or debug is overridden by cli options
    if verbose is not None:
        obj.config.set("verbose", verbose)

    if debug is not None:
        obj.config.set("debug", debug)

    if log_file:
        file_path = Path(log_file).resolve()
    else:
        logs_dir = config.get_logs_dir()
        file_path = (logs_dir / datetime.utcnow().strftime("%Y%m%d%H%M")).with_suffix(
            ".log"
        )

    obj.log_file = file_path
    obj.components = obj.config.get_components(component)
    obj.distributions = obj.config.get_distributions(distribution)
    obj.templates = obj.config.get_templates(template)

    return obj


@aliased_group("qb")
@click.option(
    "--verbose/--no-verbose", default=None, is_flag=True, help="Increase log verbosity."
)
@click.option(
    "--debug/--no-debug",
    default=None,
    is_flag=True,
    help="Print full traceback on exception.",
)
@click.option(
    "--builder-conf",
    default="builder.yml",
    help="Path to configuration file (default: builder.yml).",
)
@click.option(
    "--log-file",
    default=None,
    help="Path to log file to be created.",
)
@click.option(
    "--component",
    "-c",
    default=None,
    multiple=True,
    help="Specify component to treat (can be repeated).",
)
@click.option(
    "--distribution",
    "-d",
    default=None,
    multiple=True,
    help="Set distribution to treat (can be repeated).",
)
@click.option(
    "--template",
    "-t",
    default=None,
    multiple=True,
    help="Set template to treat (can be repeated).",
)
@click.option(
    "--option",
    "-o",
    default=None,
    multiple=True,
    help="Set builder configuration value (can be repeated).",
)
@click.pass_context
def main(
    ctx: click.Context,
    verbose: int,
    debug: bool,
    builder_conf: str,
    log_file: str,
    component: List,
    distribution: List,
    template: List,
    option: List,
):
    """
    Main CLI

    """
    obj = init_context_obj(
        builder_conf=builder_conf,
        verbose=verbose,
        debug=debug,
        log_file=log_file,
        component=component,
        distribution=distribution,
        template=template,
        option=option,
    )

    if obj.config.verbose:
        init_logging(level="DEBUG" if verbose else "INFO", file_path=obj.log_file)
    else:
        init_logging(level="WARNING", file_path=obj.log_file)

    ctx.obj = obj

    # debug mode is also provided by builder configuration
    ctx.command.debug = ctx.obj.config.debug  # type: ignore

    if debug is not None:
        ctx.command.debug = True  # type: ignore


main.epilog = f"""Stages:
    {' '.join(STAGES)}

Option:
    Input value for option is of the form:

        1. key=value
        2. parent-key:key=value
        3. key+value

    It allows to set configuration dict values or appending array values.
    In the three forms, 'value' can be chained by one of the three forms to set value at deeper level.

    For example:
        force-fetch=true
        executor:type=qubes
        executor:options:dispvm=qubes-builder-dvm
        components+lvm2
        components+kernel:branch=stable-5.15

Remark:
    The Qubes OS components are separated into two groups: standard components
    and template components. Standard components will produce distribution
    packages to be installed in TemplateVMs or StandaloneVMs, while template
    components will produce template packages to be installed via qvm-template.
"""

main.add_command(package)
main.add_command(template)
main.add_command(repository)
main.add_command(installer)
main.add_command(config)
