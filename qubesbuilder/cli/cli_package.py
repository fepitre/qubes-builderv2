from typing import List

import click

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.common import STAGES, STAGES_ALIAS
from qubesbuilder.component import QubesComponent
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.helpers import get_plugins


@aliased_group("package", chain=True)
def package():
    """
    Package CLI
    """


def _component_stage(
    config: Config,
    components: List[QubesComponent],
    distributions: List[QubesDistribution],
    stage_name: str,
):
    """
    Generic function to trigger stage for a standard component
    """
    click.echo(f"Running stage: {stage_name}")

    kwargs = {
        "plugins_dir": config.get_plugins_dir(),
        "executor": config.get_executor_from_config(stage_name=stage_name),
        "artifacts_dir": config.get_artifacts_dir(),
        "verbose": config.verbose,
        "debug": config.debug,
        "skip_if_exists": config.get("reuse-fetched-source", False),
        "skip_git_fetch": config.get("skip-git-fetch", False),
        "do_merge": config.get("do-merge", False),
        "fetch_versions_only": config.get("fetch-versions-only", False),
        "backend_vmm": config.get("backend-vmm", "xen"),
        "use_qubes_repo": config.get("use-qubes-repo", {}),
        "gpg_client": config.get("gpg-client", "gpg"),
        "sign_key": config.get("sign-key", {}),
        "min_age_days": config.get("min-age-days", 5),
        "qubes_release": config.get("qubes-release", {}),
        "repository_publish": config.get("repository-publish", {}),
        "repository_upload_remote_host": config.get(
            "repository-upload-remote-host", {}
        ),
    }

    plugins = get_plugins(
        stage=stage_name,
        components=components,
        distributions=distributions,
        **kwargs,
    )
    for p in plugins:
        p.run(stage=stage_name)


@click.command(name="all", short_help="Run all package stages.")
@click.pass_obj
def _all_package_stage(obj: ContextObj):
    for s in STAGES:
        _component_stage(
            config=obj.config,
            components=obj.components,
            distributions=obj.distributions,
            stage_name=s,
        )


@package.command()
@click.pass_obj
def fetch(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="fetch",
    )


@package.command()
@click.pass_obj
def prep(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="prep",
    )


@package.command()
@click.pass_obj
def build(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="build",
    )


@package.command()
@click.pass_obj
def post(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="post",
    )


@package.command()
@click.pass_obj
def verify(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="verify",
    )


@package.command()
@click.pass_obj
def sign(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="sign",
    )


@package.command()
@click.pass_obj
def publish(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="publish",
    )


@package.command()
@click.pass_obj
def upload(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="upload",
    )


@package.command()
@click.pass_obj
def init_cache(obj: ContextObj):
    _component_stage(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        stage_name="init-cache",
    )


package.add_command(init_cache, name="init-cache")
package.add_command(prep)
package.add_command(build)
package.add_command(post)
package.add_command(verify)
package.add_command(sign)
package.add_command(publish)
package.add_command(upload)
package.add_command(_all_package_stage)

package.add_alias(**STAGES_ALIAS)
