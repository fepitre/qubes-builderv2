import datetime
from typing import Dict, Any, List

import click
import yaml

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.plugins.helpers import getPublishPlugin, getTemplatePlugin
from qubesbuilder.plugins.publish import (
    COMPONENT_REPOSITORIES,
    PluginError,
)
from qubesbuilder.plugins.template import TEMPLATE_REPOSITORIES
from qubesbuilder.plugins.upload import UploadPlugin
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.component import QubesComponent
from qubesbuilder.template import QubesTemplate


@aliased_group("repository", chain=True)
def repository():
    """
    Repository CLI
    """


def _publish(
    config: Config,
    components: List[QubesComponent],
    distributions: List[QubesDistribution],
    templates: List[QubesTemplate],
    repository_publish: str,
    ignore_min_age: bool = False,
    unpublish: bool = False,
):
    executor = config.get_stages()["publish"]["executor"]
    if repository_publish in COMPONENT_REPOSITORIES:
        for component in components:
            for dist in distributions:
                publish_plugin = getPublishPlugin(
                    component=component,
                    dist=dist,
                    plugins_dir=config.get_plugins_dir(),
                    executor=executor,
                    artifacts_dir=config.get_artifacts_dir(),
                    verbose=config.verbose,
                    debug=config.debug,
                    gpg_client=config.get("gpg-client", "gpg"),
                    sign_key=config.get("sign-key"),
                    qubes_release=config.get("qubes-release"),
                    repository_publish=config.get("repository-publish"),
                    backend_vmm=config.get("backend-vmm", "xen"),
                )
                publish_plugin.run(
                    stage="publish",
                    repository_publish=repository_publish,
                    ignore_min_age=ignore_min_age,
                    unpublish=unpublish,
                )
    elif repository_publish in TEMPLATE_REPOSITORIES:
        for tmpl in templates:
            publish_plugin = getTemplatePlugin(
                template=tmpl,
                plugins_dir=config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                gpg_client=config.get("gpg-client", "gpg"),
                sign_key=config.get("sign-key"),
                qubes_release=config.get("qubes-release"),
                repository_publish=config.get("repository-publish"),
                repository_upload_remote_host=config.get(
                    "repository-upload-remote-host", {}
                ),
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
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        templates=obj.templates,
        repository_publish=repository_publish,
        ignore_min_age=ignore_min_age,
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
    _publish(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
        templates=obj.templates,
        repository_publish=repository_publish,
        unpublish=True,
    )


#
# check-release-status
#


@click.command(
    name="check-release-status-for-component",
    short_help="Check release status for a given component",
)
@click.pass_obj
def check_release_status_for_component(obj: ContextObj):
    release_status = _check_release_status_for_component(
        config=obj.config,
        components=obj.components,
        distributions=obj.distributions,
    )
    click.secho(yaml.dump(release_status))


def _check_release_status_for_component(config, components, distributions):
    release_status: Dict[str, Any] = {}
    for component in components:
        release_status.setdefault(component.name, {})
        for dist in distributions:
            release_status[component.name].setdefault(dist.distribution, {})
            plugin = getPublishPlugin(
                component=component,
                dist=dist,
                plugins_dir=config.get_plugins_dir(),
                executor=config.get_stages()["publish"]["executor"],
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                gpg_client=config.get("gpg-client", "gpg"),
                sign_key=config.get("sign-key"),
                qubes_release=config.get("qubes-release"),
                repository_publish=config.get("repository-publish"),
                backend_vmm=config.get("backend-vmm", "xen"),
            )

            fetch_info = plugin.get_dist_artifacts_info(
                "fetch",
                "source",
                artifacts_dir=plugin.get_component_artifacts_dir("fetch"),
            )
            if not fetch_info:
                release_status[component.name][dist.distribution][
                    "status"
                ] = "no fetch artifacts"
                continue

            # we may have nothing to be done for this distribution
            if not plugin.parameters.get("build", []):
                release_status[component.name][dist.distribution][
                    "status"
                ] = "no packages defined"
                continue

            vtags = fetch_info.get("git-version-tags", [])
            if vtags:
                release_status[component.name][dist.distribution]["tag"] = vtags[0]
            else:
                release_status[component.name][dist.distribution][
                    "tag"
                ] = "no version tag"

            try:
                # Ensure we have all publish artifacts info
                plugin.check_dist_stage_artifacts("publish")
            except PluginError:
                release_status[component.name][dist.distribution][
                    "status"
                ] = "not released"
                continue

            found = False
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
                                repo["timestamp"], "%Y%m%d%H%M"
                            )
                            days = (datetime.datetime.utcnow() - publish_date).days
                            break
                    release_status[component.name][dist.distribution].setdefault(
                        "status", []
                    )
                    release_status[component.name][dist.distribution]["status"].append(
                        {"repo": repo_name, "days": days}
                    )
                    found = True

            if not found:
                if all(
                    plugin.get_dist_artifacts_info(
                        stage="build", basename=build.with_suffix("").name
                    )
                    for build in plugin.parameters["build"]
                ):
                    status = "built, not released"
                else:
                    status = "not released"
                release_status[component.name][dist.distribution]["status"] = status

    return release_status


@click.command(
    name="check-release-status-for-template",
    short_help="Check release status for a given template",
)
@click.pass_obj
def check_release_status_for_template(
    obj: ContextObj,
):
    release_status = _check_release_status_for_template(
        config=obj.config, templates=obj.templates
    )
    click.secho(yaml.dump(release_status))


def _check_release_status_for_template(config, templates):
    release_status: Dict[str, Any] = {}
    for template in templates:
        release_status.setdefault(template.name, {})
        plugin = getTemplatePlugin(
            template=template,
            plugins_dir=config.get_plugins_dir(),
            executor=config.get_stages()["publish"]["executor"],
            artifacts_dir=config.get_artifacts_dir(),
            verbose=config.verbose,
            debug=config.debug,
            gpg_client=config.get("gpg-client", "gpg"),
            sign_key=config.get("sign-key"),
            qubes_release=config.get("qubes-release"),
            repository_publish=config.get("repository-publish"),
            repository_upload_remote_host=config.get(
                "repository-upload-remote-host", {}
            ),
        )

        found = False
        set_template_tag = False
        for repo_name in TEMPLATE_REPOSITORIES:
            days = 0
            if plugin.is_published(repository=repo_name):
                publish_info = plugin.get_artifacts_info(stage="publish")
                for repo in publish_info.get("repository-publish", []):
                    if repo["name"] == repo_name:
                        publish_date = datetime.datetime.strptime(
                            repo["timestamp"], "%Y%m%d%H%M"
                        )
                        days = (datetime.datetime.utcnow() - publish_date).days
                        break
                release_status[template.name].setdefault("status", [])
                release_status[template.name]["status"].append(
                    {"repo": repo_name, "days": days}
                )
                found = True
                set_template_tag = True

        if not found:
            if plugin.get_artifacts_info(stage="build"):
                status = "built, not released"
                set_template_tag = True
            else:
                status = "not released"
            release_status[template.name]["status"] = status

        if set_template_tag:
            release_status[template.name]["tag"] = plugin.get_template_tag()

    return release_status


#
# Upload
#
@click.command(
    name="upload",
    short_help="Upload packages or templates to remote location.",
)
@click.pass_obj
def upload(obj: ContextObj, repository_publish: str):
    _upload(
        config=obj.config,
        distributions=obj.distributions,
        templates=obj.templates,
        repository_publish=repository_publish,
    )


def _upload(
    config: Config,
    distributions: List[QubesDistribution],
    templates: List[QubesTemplate],
    repository_publish: str,
):
    executor = config.get_stages()["publish"]["executor"]
    if repository_publish in COMPONENT_REPOSITORIES:
        for dist in distributions:
            upload_plugin = UploadPlugin(
                dist=dist,
                plugins_dir=config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                qubes_release=config.get("qubes-release", {}),
                repository_publish=config.get("repository-publish"),
                repository_upload_remote_host=config.get(
                    "repository-upload-remote-host", {}
                ),
            )
            upload_plugin.run(stage="upload", repository_publish=repository_publish)
    elif repository_publish in TEMPLATE_REPOSITORIES:
        for tmpl in templates:
            upload_plugin = getTemplatePlugin(
                template=tmpl,
                plugins_dir=config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=config.get_artifacts_dir(),
                verbose=config.verbose,
                debug=config.debug,
                gpg_client=config.get("gpg-client", "gpg"),
                sign_key=config.get("sign-key"),
                qubes_release=config.get("qubes-release"),
                repository_publish=config.get("repository-publish"),
                repository_upload_remote_host=config.get(
                    "repository-upload-remote-host", {}
                ),
            )
            upload_plugin.run(stage="upload", repository_publish=repository_publish)


repository.add_command(publish)
repository.add_command(unpublish)
repository.add_command(check_release_status_for_component)
repository.add_command(check_release_status_for_template)
repository.add_command(upload)
