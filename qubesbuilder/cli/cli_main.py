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

from typing import List

import click

from qubesbuilder.cli.cli_base import ContextObj, aliased_group
from qubesbuilder.cli.cli_package import package
from qubesbuilder.cli.cli_repository import repository
from qubesbuilder.cli.cli_template import template
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.config import Config, STAGES
from qubesbuilder.log import get_logger, init_logging

log = get_logger("cli")


@aliased_group("qb")
@click.option("--verbose/--no-verbose", default=None, is_flag=True, help="Output logs.")
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
    "--component",
    "-c",
    default=None,
    multiple=True,
    help="Override component in configuration file (can be repeated).",
)
@click.option(
    "--distribution",
    "-d",
    default=None,
    multiple=True,
    help="Override distribution in configuration file (can be repeated).",
)
@click.option(
    "--template",
    "-t",
    default=None,
    multiple=True,
    help="Override template in configuration file (can be repeated).",
)
@click.option(
    "--executor",
    "-e",
    default=None,
    help="Override executor type in configuration file.",
)
@click.option(
    "--executor-option",
    default=None,
    multiple=True,
    help='Override executor options in configuration file provided as "option=value" (can be repeated). '
    'For example, --executor-option image="qubes-builder-fedora:latest"',
)
@click.pass_context
def main(
    ctx: click.Context,
    verbose: int,
    debug: bool,
    builder_conf: str,
    component: List = None,
    distribution: List = None,
    template: List = None,
    executor: str = None,
    executor_option: List = None,
):
    """
    Main CLI

    """
    config = Config(builder_conf)
    if executor:
        executor_config = {"type": executor, "options": {}}
        for raw_option in executor_option or []:
            parsed_option = raw_option.split("=", 1)
            if len(parsed_option) != 2:
                raise CliError("Invalid executor option.")
            option, value = parsed_option
            executor_config["options"][option] = str(value)  # type: ignore
        config.set("executor", executor_config)

    ctx.obj = ContextObj(config)

    # debug mode is also provided by builder configuration
    ctx.command.debug = ctx.obj.config.debug  # type: ignore

    # verbose or debug is overridden by cli options
    if verbose is not None:
        ctx.obj.config.verbose = verbose

    if debug is not None:
        ctx.obj.config.debug = debug
        ctx.command.debug = True  # type: ignore

    if ctx.obj.config.verbose:
        init_logging(level="DEBUG" if verbose else "INFO")
    else:
        init_logging(level="WARNING")

    ctx.obj.components = ctx.obj.config.get_components(component)
    ctx.obj.distributions = ctx.obj.config.get_distributions(distribution)
    ctx.obj.templates = ctx.obj.config.get_templates()

    # FIXME: Find a syntax that would allow CLI template filtering without having it
    #  declared inside the builder.yml.
    if template:
        templates = []
        for template_name in template:
            for tmpl in ctx.obj.templates:
                if tmpl.name == template_name:
                    templates.append(tmpl)
                    break
        ctx.obj.templates = templates


main.epilog = f"""Stages:
    {' '.join(STAGES)}

Remark:
    The Qubes OS components are separated in two groups: standard and template
    components. Standard components will produce distributions packages and
    template components will produce template packages.
"""

main.add_command(package)
main.add_command(template)
main.add_command(repository)
