import json
import pathlib

import click
import yaml

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.cli.cli_exc import CliError


@aliased_group("config", chain=True)
def config():
    """
    Config CLI
    """


@config.command(name="get-var")
@click.argument("var")
@click.option(
    "--json",
    "-j",
    "print_json",
    default=False,
    is_flag=True,
    help="Print output in JSON format.",
)
@click.option(
    "--yaml",
    "-y",
    "print_yaml",
    default=False,
    is_flag=True,
    help="Print output in YAML format.",
)
@click.pass_obj
def get_var(obj: ContextObj, var: str, print_json: bool, print_yaml: bool):
    if hasattr(obj.config, var.replace("-", "_")):
        result = getattr(obj.config, var.replace("-", "_"))
        if isinstance(result, pathlib.Path):
            result = str(result)
    else:
        result = obj.config.get(var)
    if result is None:
        return
    if print_json:
        click.secho(json.dumps(result))
    elif print_yaml:
        click.secho(yaml.dump(result))
    elif isinstance(result, list):
        final_result = []
        for r in result:
            if isinstance(r, str):
                final_result.append(r)
            elif isinstance(r, dict):
                final_result.append(list(r.keys())[0])
            else:
                CliError(f"Unexpected type value in '{var}'.")
        click.secho(" ".join(final_result))
    elif not isinstance(result, str):
        click.secho(json.dumps(result))
    else:
        click.secho(result)


@config.command(name="get-components")
@click.option(
    "--attribute",
    "-a",
    default=None,
    help="Print component attribute (if exists).",
)
@click.pass_obj
def get_components(obj: ContextObj, attribute: str):
    for c in obj.components:
        result = c
        if attribute:
            try:
                if attribute == "source_hash":
                    result = result.get_source_hash()
                elif attribute == "source_commit_hash":
                    result = result.get_source_commit_hash()
                else:
                    result = result.__getattribute__(attribute)
            except AttributeError:
                return
        click.secho(str(result))


@config.command(name="get-distributions")
@click.option(
    "--host",
    default=False,
    is_flag=True,
    help="Print host distributions.",
)
@click.option(
    "--vm",
    default=False,
    is_flag=True,
    help="Print host distributions.",
)
@click.pass_obj
def get_distributions(obj: ContextObj, host: bool, vm: bool):
    for d in obj.distributions:
        if not host and not vm:
            click.secho(d.distribution)
        else:
            if d.package_set == "host" and host:
                click.secho(d.name)
            elif d.package_set == "vm" and vm:
                click.secho(d.name)


@config.command(name="get-templates")
@click.pass_obj
def get_templates(obj: ContextObj):
    for t in obj.templates:
        click.secho(t)


config.add_command(get_var)
config.add_command(get_components)
config.add_command(get_distributions)
config.add_command(get_templates)
