from pathlib import Path

import click

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.config import STAGES, STAGES_ALIAS
from qubesbuilder.plugins.github import GithubPlugin
from qubesbuilder.plugins.helpers import getTemplatePlugin


@aliased_group("template", chain=True)
def template():
    """
    Template CLI
    """


def _template_stage(obj: ContextObj, stage_name: str, template_timestamp: str = None):
    """
    Generic function to trigger stage for a template component
    """
    click.echo(f"Running template stage: {stage_name}")
    executor = obj.config.get_stages()[stage_name]["executor"]

    # Qubes templates
    for tmpl in obj.templates:
        plugins = [
            getTemplatePlugin(
                template=tmpl,
                plugins_dir=obj.config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=obj.config.get_artifacts_dir(),
                verbose=obj.config.verbose,
                debug=obj.config.debug,
                use_qubes_repo=obj.config.get("use-qubes-repo"),
                gpg_client=obj.config.get("gpg-client", "gpg"),
                sign_key=obj.config.get("sign-key"),
                qubes_release=obj.config.get("qubes-release"),
                repository_publish=obj.config.get("repository-publish"),
                repository_upload_remote_host=obj.config.get(
                    "repository-upload-remote-host", {}
                ),
            )
        ]

        for plugin in obj.config.get("plugins", []):
            # For now, we only assume plugin options are provided as dict
            if not isinstance(plugin, dict):
                continue
            if plugin.get("github", None):
                try:
                    github_plugin = GithubPlugin(
                        template=tmpl,
                        plugins_dir=obj.config.get_plugins_dir(),
                        executor=executor,
                        artifacts_dir=obj.config.get_artifacts_dir(),
                        verbose=True,
                        debug=True,
                        qubes_release=obj.config.get("qubes-release"),
                        backend_vmm=obj.config.get("backend-vmm", "xen"),
                        state_dir=Path(plugin["github"]["state-dir"]).resolve(),
                        api_key=plugin["github"]["api-key"],
                        build_report_repo=plugin["github"]["build-report-repo"],
                        build_issues_repo=plugin["github"]["build-issues-repo"],
                        logs_repo=plugin["github"]["logs-repo"],
                        repository_publish=obj.config.get("repository-publish", {}),
                        log_file=obj.log_file,
                    )
                    plugins.append(github_plugin)
                except KeyError as e:
                    raise CliError(
                        f"Failed to initialize GitHub plugin: {str(e)}"
                    ) from e

        for plugin in plugins:
            plugin.run(stage=stage_name, template_timestamp=template_timestamp)


@click.command(name="all", short_help="Run all template stages.")
@click.pass_obj
def _all_template_stage(obj: ContextObj):
    for s in STAGES:
        _template_stage(obj=obj, stage_name=s)


@template.command()
@click.pass_obj
def fetch(obj: ContextObj):
    _template_stage(obj=obj, stage_name="fetch")


@template.command()
@click.option(
    "--template-timestamp",
    default=None,
    help="Provide template timestamp to use (format must be '%Y%m%d%H%MZ').",
)
@click.pass_obj
def pre(obj: ContextObj, template_timestamp: str):
    _template_stage(obj=obj, stage_name="pre", template_timestamp=template_timestamp)


@template.command()
@click.pass_obj
def prep(obj: ContextObj):
    _template_stage(obj=obj, stage_name="prep")


@template.command()
@click.pass_obj
def build(obj: ContextObj):
    _template_stage(obj=obj, stage_name="build")


@template.command()
@click.pass_obj
def post(obj: ContextObj):
    _template_stage(obj=obj, stage_name="post")


@template.command()
@click.pass_obj
def verify(obj: ContextObj):
    _template_stage(obj=obj, stage_name="verify")


@template.command()
@click.pass_obj
def sign(obj: ContextObj):
    _template_stage(obj=obj, stage_name="sign")


@template.command()
@click.pass_obj
def publish(obj: ContextObj):
    _template_stage(obj=obj, stage_name="publish")


@template.command()
@click.pass_obj
def upload(obj: ContextObj):
    _template_stage(obj=obj, stage_name="upload")


template.add_command(fetch)
template.add_command(pre)
template.add_command(prep)
template.add_command(build)
template.add_command(post)
template.add_command(verify)
template.add_command(sign)
template.add_command(publish)
template.add_command(upload)
template.add_command(_all_template_stage)

template.add_alias(**STAGES_ALIAS)
