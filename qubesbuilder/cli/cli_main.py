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

from datetime import datetime
from pathlib import Path
from typing import List
import re
import click

from qubesbuilder.cli.cli_base import ContextObj, aliased_group
from qubesbuilder.cli.cli_config import config
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.cli.cli_installer import installer
from qubesbuilder.cli.cli_package import package
from qubesbuilder.cli.cli_repository import repository
from qubesbuilder.cli.cli_template import template
from qubesbuilder.common import STAGES
from qubesbuilder.config import Config, deep_merge
from qubesbuilder.log import get_logger, init_logging

log = get_logger("cli")

ALLOWED_KEY_PATTERN = r"[A-Za-z0-9]+"


def parse_dict_from_array(array):
    if not array:
        raise ValueError("Empty array found!")
    if not re.match(ALLOWED_KEY_PATTERN, array[0]):
        raise ValueError(f"Invalid key found: '{array[0]}'.")
    if len(array) > 1:
        result = {array[0]: parse_dict_from_array(array[1:])}
    else:
        if "=" in array[0]:
            key, value = array[0].split("=")
            if not re.match(ALLOWED_KEY_PATTERN, key):
                raise ValueError(f"Invalid key found: '{array[0]}'.")
            result = {key: value}
        else:
            result = {array[0]: True}
    return result


def parse_config_entry_from_array(array):
    result = {}
    for s in array:
        result = deep_merge(result, parse_dict_from_array(s.split(":")))
    return result


def init_context_obj(
    builder_conf: str,
    verbose: int = None,
    debug: bool = None,
    log_file: str = None,
    component: List = None,
    distribution: List = None,
    template: List = None,
    option: List = None,
):

    try:
        options = parse_config_entry_from_array(option) if option else {}
    except ValueError as e:
        raise CliError(f"Failed to parse CLI options: '{str(e)}'")

    config = Config(builder_conf)

    for opt in [
        "git",
        "executor",
        "force-fetch",
        "skip-git-fetch",
        "fetch-versions-only",
        "backend-vmm",
        "use-qubes-repo",
        "gpg-client",
        "sign-key",
        "min-age-days",
        "qubes-release",
        "repository-publish",
        "repository-upload-remote-host",
        "template-root-size",
        "template-root-with-partitions",
        "iso",
    ]:
        config.set(opt, config.get(opt, options.get(opt)))

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
@click.option("--verbose/--no-verbose", default=None, is_flag=True, help="Increase log verbosity.")
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
