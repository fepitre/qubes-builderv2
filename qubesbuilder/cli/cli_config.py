import click
import json
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
    result = obj.config.get(var)
    if not result:
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


@config.command(name="get-component")
@click.option(
    "--attribute",
    "-a",
    default=None,
    help="Print component attribute (if exists).",
)
@click.pass_obj
def get_component(obj: ContextObj, attribute: str):
    for c in obj.components:
        result = c
        if attribute:
            try:
                result = result.__getattribute__(attribute)
            except AttributeError:
                return
        if isinstance(result, str):
            click.secho(result)
        else:
            click.secho(yaml.dump(result))


config.add_command(get_var)
config.add_command(get_component)
