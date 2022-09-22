from typing import List

import click

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.common import STAGES, STAGES_ALIAS
from qubesbuilder.config import Config
from qubesbuilder.helpers import PluginManager
from qubesbuilder.template import QubesTemplate


@aliased_group("template", chain=True)
def template():
    """
    Template CLI
    """


def _template_stage(
    config: Config,
    templates: List[QubesTemplate],
    stage_name: str,
    template_timestamp: str = None,
):
    """
    Generic function to trigger stage for a template component
    """
    click.echo(f"Running template stage: {stage_name}")

    # Qubes templates
    manager = PluginManager(directories=config.get_plugins_dirs())
    plugins = manager.get_template_instances(
        stage=stage_name, config=config, templates=templates
    )
    for p in plugins:
        p.run(stage=stage_name, template_timestamp=template_timestamp)


@click.command(name="all", short_help="Run all template stages.")
@click.pass_obj
def _all_template_stage(obj: ContextObj):
    for s in STAGES:
        _template_stage(config=obj.config, templates=obj.templates, stage_name=s)


@template.command()
@click.pass_obj
def fetch(obj: ContextObj):
    _template_stage(config=obj.config, templates=obj.templates, stage_name="fetch")


@template.command()
@click.option(
    "--template-timestamp",
    default=None,
    help="Provide template timestamp to use (format must be '%Y%m%d%H%M').",
)
@click.pass_obj
def prep(obj: ContextObj, template_timestamp: str):
    _template_stage(
        config=obj.config,
        templates=obj.templates,
        stage_name="prep",
        template_timestamp=template_timestamp,
    )


@template.command()
@click.pass_obj
def build(obj: ContextObj):
    _template_stage(config=obj.config, templates=obj.templates, stage_name="build")


@template.command()
@click.pass_obj
def post(obj: ContextObj):
    _template_stage(config=obj.config, templates=obj.templates, stage_name="post")


@template.command()
@click.pass_obj
def verify(obj: ContextObj):
    _template_stage(config=obj.config, templates=obj.templates, stage_name="verify")


@template.command()
@click.pass_obj
def sign(obj: ContextObj):
    _template_stage(config=obj.config, templates=obj.templates, stage_name="sign")


@template.command()
@click.pass_obj
def publish(obj: ContextObj):
    _template_stage(config=obj.config, templates=obj.templates, stage_name="publish")


@template.command()
@click.pass_obj
def upload(obj: ContextObj):
    _template_stage(config=obj.config, templates=obj.templates, stage_name="upload")


template.add_command(fetch)
template.add_command(prep)
template.add_command(build)
template.add_command(post)
template.add_command(verify)
template.add_command(sign)
template.add_command(publish)
template.add_command(upload)
template.add_command(_all_template_stage)

template.add_alias(**STAGES_ALIAS)
