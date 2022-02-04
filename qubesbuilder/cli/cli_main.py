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

from pathlib import Path
from typing import List

import click

from qubesbuilder.cli.cli_base import ContextObj, aliased_group
from qubesbuilder.config import Config
from qubesbuilder.dist import Dist
from qubesbuilder.log import get_logger, init_logging
from qubesbuilder.plugins.helpers import getSourcePlugin, getBuildPlugin, \
    getSignPlugin, getPublishPlugin

log = get_logger("cli")


@aliased_group("qb", invoke_without_command=True, chain=True)
@click.option("--verbose/--no-verbose", default=None, is_flag=True,
              help="Output logs.")
@click.option("--debug/--no-debug", default=None, is_flag=True,
              help="Print full traceback on exception.")
@click.option("--builder-conf", default="builder.yml",
              help="Path to configuration file (default: builder.yml).")
@click.option("--component", "-c", default=None, multiple=True,
              help="Override component in configuration file (can be repeated).")
@click.option("--distribution", "-d", default=None, multiple=True,
              help="Override distribution in configuration file (can be repeated).")
@click.pass_context
def main(ctx: click.Context, verbose: int, debug: bool, builder_conf: str,
         component: List = None, distribution: List = None):
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

    if component:
        components = []
        for component_name in component:
            for comp in ctx.obj.components:
                if comp.name == component_name:
                    components.append(comp)
        ctx.obj.components = components

    if distribution:
        distributions = []
        for distribution_name in distribution:
            distributions.append(Dist(distribution_name))
        ctx.obj.distributions = distributions


#
# Generic function to trigger stage
#
# FIXME: Find a better design to register necessary plugins for each stage.
def _stage(obj: ContextObj, stage_name: str):
    click.echo(f"Running stage: {stage_name}")
    executor = obj.config.get_stages()[stage_name]["executor"]

    for component in obj.components:
        for dist in obj.distributions:
            plugins = [
                getSourcePlugin(
                    component=component,
                    dist=dist,
                    plugins_dir=obj.config.get_plugins_dir(),
                    executor=executor,
                    artifacts_dir=obj.config.get_artifacts_dir(),
                    verbose=obj.config.verbose,
                    debug=obj.config.debug,
                    skip_if_exists=obj.config.get("reuse-fetched-source")
                ),
                getBuildPlugin(
                    component=component,
                    dist=dist,
                    plugins_dir=obj.config.get_plugins_dir(),
                    executor=executor,
                    artifacts_dir=obj.config.get_artifacts_dir(),
                    verbose=obj.config.verbose,
                    debug=obj.config.debug,
                    use_qubes_repo=obj.config.get("use-qubes-repo")
                ),
                getSignPlugin(
                    component=component,
                    dist=dist,
                    plugins_dir=obj.config.get_plugins_dir(),
                    executor=executor,
                    artifacts_dir=obj.config.get_artifacts_dir(),
                    verbose=obj.config.verbose,
                    debug=obj.config.debug,
                    gpg_client=obj.config.get("gpg-client"),
                    sign_key=obj.config.get("sign-key")
                ),
                getPublishPlugin(
                    component=component,
                    dist=dist,
                    plugins_dir=obj.config.get_plugins_dir(),
                    executor=executor,
                    artifacts_dir=obj.config.get_artifacts_dir(),
                    verbose=obj.config.verbose,
                    debug=obj.config.debug,
                    gpg_client=obj.config.get("gpg-client"),
                    sign_key=obj.config.get("sign-key"),
                    qubes_release=obj.config.get("qubes-release"),
                    publish_repository=obj.config.get("publish-repository")
                )
            ]
            for plugin in plugins:
                plugin.run(stage=stage_name)


#
# Fetch
#

@click.command()
@click.pass_obj
def fetch(obj: ContextObj):
    _stage(obj=obj, stage_name="fetch")


#
# Prep
#

@click.command()
@click.pass_obj
def prep(obj: ContextObj):
    _stage(obj=obj, stage_name="prep")


#
# Build
#

@click.command()
@click.pass_obj
def build(obj: ContextObj):
    _stage(obj=obj, stage_name="build")


#
# Post
#

@click.command()
@click.pass_obj
def post(obj: ContextObj):
    _stage(obj=obj, stage_name="post")


#
# Verify
#

@click.command()
@click.pass_obj
def verify(obj: ContextObj):
    _stage(obj=obj, stage_name="verify")


#
# Sign
#

@click.command()
@click.pass_obj
def sign(obj: ContextObj):
    _stage(obj=obj, stage_name="sign")


#
# Publish
#

@click.command()
@click.pass_obj
def publish(obj: ContextObj):
    _stage(obj=obj, stage_name="publish")


#
#
#


main.add_command(fetch)
main.add_command(prep)
main.add_command(build)
main.add_command(post)
main.add_command(verify)
main.add_command(sign)
main.add_command(publish)
main.add_alias(**{
    "f": "fetch",
    "pr": "prep",
    "b": "build",
    "po": "post",
    "v": "verify",
    "s": "sign",
    "pu": "publish",
})
