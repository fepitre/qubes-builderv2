from typing import List

import click

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.component import QubesComponent
from qubesbuilder.config import Config, STAGES, STAGES_ALIAS
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.plugins.fetch import FetchPlugin
from qubesbuilder.plugins.helpers import (
    getSourcePlugin,
    getBuildPlugin,
    getSignPlugin,
    getPublishPlugin,
)
from qubesbuilder.plugins.upload import UploadPlugin


@aliased_group("package", chain=True)
def package():
    """
    Package CLI
    """


# FIXME: Find a better design to register necessary plugins for each stage
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
    executor = config.get_stages()[stage_name]["executor"]

    for component in components:
        # Component plugins
        fetch_plugin = FetchPlugin(
            component=component,
            plugins_dir=config.get_plugins_dir(),
            executor=executor,
            artifacts_dir=config.get_artifacts_dir(),
            verbose=config.verbose,
            debug=config.debug,
            skip_if_exists=config.get("reuse-fetched-source", False),
            skip_git_fetch=config.get("skip-git-fetch", False),
            do_merge=config.get("do-merge", False),
            fetch_versions_only=config.get("fetch-versions-only", False),
        )
        fetch_plugin.run(stage=stage_name)

        # Distribution plugins
        for dist in distributions:
            source_plugin = getSourcePlugin(
                component=component,
                dist=dist,
                plugins_dir=config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                skip_if_exists=config.get("reuse-fetched-source", False),
                backend_vmm=config.get("backend-vmm", "xen"),
            )
            build_plugin = getBuildPlugin(
                component=component,
                dist=dist,
                plugins_dir=config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                use_qubes_repo=config.get("use-qubes-repo", {}),
                backend_vmm=config.get("backend-vmm", "xen"),
            )
            sign_plugin = getSignPlugin(
                component=component,
                dist=dist,
                plugins_dir=config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                gpg_client=config.get("gpg-client", "gpg"),
                sign_key=config.get("sign-key", {}),
                backend_vmm=config.get("backend-vmm", "xen"),
            )
            publish_plugin = getPublishPlugin(
                component=component,
                dist=dist,
                plugins_dir=config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                gpg_client=config.get("gpg-client", "gpg"),
                sign_key=config.get("sign-key", {}),
                qubes_release=config.get("qubes-release", {}),
                repository_publish=config.get("repository-publish", {}),
                backend_vmm=config.get("backend-vmm", "xen"),
            )

            for plugin in [source_plugin, build_plugin, sign_plugin, publish_plugin]:
                plugin.run(stage=stage_name)

    for dist in distributions:
        upload_plugin = UploadPlugin(
            dist=dist,
            plugins_dir=config.get_plugins_dir(),
            executor=executor,
            artifacts_dir=config.get_artifacts_dir(),
            verbose=config.verbose,
            debug=config.debug,
            qubes_release=config.get("qubes-release", {}),
            repository_publish=config.get("repository-publish", {}),
            repository_upload_remote_host=config.get(
                "repository-upload-remote-host", {}
            ),
        )
        upload_plugin.run(stage=stage_name)


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


package.add_command(fetch)
package.add_command(prep)
package.add_command(build)
package.add_command(post)
package.add_command(verify)
package.add_command(sign)
package.add_command(publish)
package.add_command(upload)
package.add_command(_all_package_stage)

package.add_alias(**STAGES_ALIAS)
