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
from qubesbuilder.cli.cli_template import template
from qubesbuilder.config import Config, STAGES
from qubesbuilder.distribution import QubesDistribution
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
@click.pass_context
def main(
    ctx: click.Context,
    verbose: int,
    debug: bool,
    builder_conf: str,
    component: List = None,
    distribution: List = None,
    template: List = None,
):
    """
    Main CLI

    """
    config = Config(builder_conf)
    ctx.obj = ContextObj(config)

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

    ctx.obj.components = ctx.obj.config.get_components()
    ctx.obj.distributions = ctx.obj.config.get_distributions()
    ctx.obj.templates = ctx.obj.config.get_templates()

    if component:
        components = []
        for component_name in component:
            for comp in ctx.obj.components:
                if comp.name == component_name:
                    components.append(comp)
        ctx.obj.components = components

    if template:
        templates = []
        for template_name in template:
            for tmpl in ctx.obj.templates:
                if tmpl.name == template_name:
                    templates.append(tmpl)
        ctx.obj.templates = templates

    # We ensure that requested distribution for template is in
    # actual distributions for components.
    for tmpl in ctx.obj.templates:
        if tmpl.distribution not in ctx.obj.distributions:
            ctx.obj.distributions.append(tmpl.distribution)

    if distribution:
        distributions = []
        for distribution_name in distribution:
            distributions.append(QubesDistribution(distribution_name))
        ctx.obj.distributions = distributions


main.epilog = f"""Stages:
    {' '.join(STAGES)}

Remark:
    The Qubes OS components are separated in two groups: standard and template
    components. Standard components will produce distributions packages and
    template components will produce template packages.
"""

main.add_command(package)
main.add_command(template)
