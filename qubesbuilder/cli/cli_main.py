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
from pathlib import Path
import click

from datetime import datetime

from qubesbuilder.cli.cli_base import ContextObj, aliased_group
from qubesbuilder.cli.cli_package import package
from qubesbuilder.cli.cli_repository import repository
from qubesbuilder.cli.cli_template import template
from qubesbuilder.cli.cli_installer import installer
from qubesbuilder.cli.cli_config import config
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.config import Config
from qubesbuilder.common import STAGES
from qubesbuilder.log import get_logger, init_logging

log = get_logger("cli")


def init_context_obj(
    builder_conf,
    artifacts_dir: str = None,
    verbose: int = None,
    debug: bool = None,
    log_file: str = None,
    component: List = None,
    distribution: List = None,
    template: List = None,
    executor: str = None,
    executor_option: List = None,
):
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

    if artifacts_dir is not None:
        config.set_artifacts_dir(Path(artifacts_dir).resolve())

    obj = ContextObj(config)

    # verbose or debug is overridden by cli options
    if verbose is not None:
        obj.config.verbose = verbose

    if debug is not None:
        obj.config.debug = debug

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
    "--artifacts-dir",
    default=None,
    help="Path to artifacts directory (default: ./artifacts).",
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
    artifacts_dir: str = None,
    log_file: str = None,
    component: List = None,
    distribution: List = None,
    template: List = None,
    executor: str = None,
    executor_option: List = None,
):
    """
    Main CLI

    """
    obj = init_context_obj(
        builder_conf=builder_conf,
        artifacts_dir=artifacts_dir,
        verbose=verbose,
        debug=debug,
        log_file=log_file,
        component=component,
        distribution=distribution,
        template=template,
        executor=executor,
        executor_option=executor_option,
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
