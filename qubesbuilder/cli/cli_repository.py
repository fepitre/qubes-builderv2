import click
import datetime

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.plugins.helpers import getPublishPlugin, getTemplatePlugin
from qubesbuilder.plugins.upload import UploadPlugin
from qubesbuilder.plugins.publish import (
    COMPONENT_REPOSITORIES,
    PluginError,
)
from qubesbuilder.plugins.template import TEMPLATE_REPOSITORIES


@aliased_group("repository", chain=True)
def repository():
    """
    Repository CLI
    """


def _publish(
    obj: ContextObj,
    repository_publish: str,
    ignore_min_age: bool = False,
    unpublish: bool = False,
):
    executor = obj.config.get_stages()["publish"]["executor"]
    if repository_publish in COMPONENT_REPOSITORIES:
        for component in obj.components:
            for dist in obj.distributions:
                publish_plugin = getPublishPlugin(
                    component=component,
                    dist=dist,
                    plugins_dir=obj.config.get_plugins_dir(),
                    executor=executor,
                    artifacts_dir=obj.config.get_artifacts_dir(),
                    verbose=obj.config.verbose,
                    debug=obj.config.debug,
                    gpg_client=obj.config.get("gpg-client", "gpg"),
                    sign_key=obj.config.get("sign-key"),
                    qubes_release=obj.config.get("qubes-release"),
                    repository_publish=obj.config.get("repository-publish"),
                    backend_vmm=obj.config.get("backend-vmm", "xen"),
                )
                publish_plugin.run(
                    stage="publish",
                    repository_publish=repository_publish,
                    ignore_min_age=ignore_min_age,
                    unpublish=unpublish,
                )
    elif repository_publish in TEMPLATE_REPOSITORIES:
        for tmpl in obj.templates:
            publish_plugin = getTemplatePlugin(
                template=tmpl,
                plugins_dir=obj.config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=obj.config.get_artifacts_dir(),
                verbose=obj.config.verbose,
                debug=obj.config.debug,
                gpg_client=obj.config.get("gpg-client", "gpg"),
                sign_key=obj.config.get("sign-key"),
                qubes_release=obj.config.get("qubes-release"),
                repository_publish=obj.config.get("repository-publish"),
            )
            publish_plugin.run(
                stage="publish",
                repository_publish=repository_publish,
                ignore_min_age=ignore_min_age,
                unpublish=unpublish,
            )


#
# Publish
#


@click.command(
    name="publish",
    short_help="Publish packages or templates to provided repository.",
)
@click.argument("repository_publish", nargs=1)
@click.option(
    "--ignore-min-age",
    default=False,
    is_flag=True,
    help="Override minimum age for authorizing publication into 'current'.",
)
@click.pass_obj
def publish(obj: ContextObj, repository_publish: str, ignore_min_age: bool = False):
    _publish(
        obj=obj, repository_publish=repository_publish, ignore_min_age=ignore_min_age
    )


#
# Unpublish
#


@click.command(
    name="unpublish",
    short_help="Unpublish packages or templates from provided repository.",
)
@click.argument("repository_publish", nargs=1)
@click.pass_obj
def unpublish(obj: ContextObj, repository_publish: str):
    _publish(obj=obj, repository_publish=repository_publish, unpublish=True)


#
# check-release-status
#


@click.command(
    name="check-release-status-for-component",
    short_help="Check release status for a given component",
)
@click.option(
    "--abort-no-version",
    default=False,
    is_flag=True,
    help="Abort if no version tag is present.",
)
@click.option(
    "--abort-on-empty",
    default=False,
    is_flag=True,
    help="Abort when no packages are defined.",
)
@click.option(
    "--no-print-version",
    default=False,
    is_flag=True,
    help="Skip printing version number, only release status.",
)
@click.pass_obj
def check_release_status_for_component(
    obj: ContextObj,
    abort_no_version: bool,
    abort_on_empty: bool,
    no_print_version: bool,
):
    for component in obj.components:
        for dist in obj.distributions:
            plugin = getPublishPlugin(
                component=component,
                dist=dist,
                plugins_dir=obj.config.get_plugins_dir(),
                executor=obj.config.get_stages()["publish"]["executor"],
                artifacts_dir=obj.config.get_artifacts_dir(),
                verbose=obj.config.verbose,
                debug=obj.config.debug,
                gpg_client=obj.config.get("gpg-client", "gpg"),
                sign_key=obj.config.get("sign-key"),
                qubes_release=obj.config.get("qubes-release"),
                repository_publish=obj.config.get("repository-publish"),
                backend_vmm=obj.config.get("backend-vmm", "xen"),
            )

            fetch_info = plugin.get_dist_artifacts_info(
                stage="fetch", basename="source"
            )
            if abort_on_empty and not plugin.parameters.get("build", []):
                raise CliError("No packages defined.")

            vtags = fetch_info.get("git-version-tags", [])
            if not vtags:
                if not no_print_version:
                    click.secho("no version tag")
                if abort_no_version:
                    CliError("No version tag!")
            else:
                if not no_print_version:
                    click.secho(vtags[0])

            try:
                # Ensure we have all publish artifacts info
                plugin.check_dist_stage_artifacts("publish")

                for repo_name in COMPONENT_REPOSITORIES:
                    days = 0
                    if all(
                        plugin.is_published(
                            basename=build.with_suffix("").name, repository=repo_name
                        )
                        for build in plugin.parameters["build"]
                    ):
                        # FIXME: we pick the first build target found as we have checks for all
                        #  being processed for all stages and not repository publish is not empty
                        publish_info = plugin.get_dist_artifacts_info(
                            stage="publish", basename=plugin.parameters["build"][0]
                        )
                        for repo in publish_info.get("repository-publish", []):
                            if repo["name"] == repo_name:
                                publish_date = datetime.datetime.strptime(
                                    repo["timestamp"], "%Y%m%d%H%MZ"
                                )
                                days = (datetime.datetime.utcnow() - publish_date).days
                                break
                        click.secho(repo_name)
                        click.secho(f"{days} days ago")
            except PluginError:
                click.secho("not released")


#
# Upload
#
@click.command(
    name="upload",
    short_help="Upload packages to remove location.",
)
@click.pass_obj
def upload(obj: ContextObj):
    executor = obj.config.get_stages()["publish"]["executor"]
    for dist in obj.distributions:
        upload_plugin = UploadPlugin(
            dist=dist,
            plugins_dir=obj.config.get_plugins_dir(),
            executor=executor,
            artifacts_dir=obj.config.get_artifacts_dir(),
            verbose=obj.config.verbose,
            debug=obj.config.debug,
            qubes_release=obj.config.get("qubes-release", {}),
            repository_upload_remote_host=obj.config.get(
                "repository-upload-remote-host", {}
            ),
        )
        upload_plugin.run(stage="upload")


repository.add_command(publish)
repository.add_command(unpublish)
repository.add_command(check_release_status_for_component)
repository.add_command(upload)
