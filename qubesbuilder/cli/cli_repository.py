import datetime
from typing import Dict, Any, List, Union

import click
import yaml

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.cli.cli_exc import CliError
from qubesbuilder.component import QubesComponent, ComponentError
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.helpers import PluginManager
from qubesbuilder.plugins import PluginError
from qubesbuilder.plugins.publish import PublishPlugin, COMPONENT_REPOSITORIES
from qubesbuilder.plugins.template import TemplateBuilderPlugin, TEMPLATE_REPOSITORIES
from qubesbuilder.plugins.upload import UploadPlugin
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
    manager = PluginManager(config.get_plugins_dirs())
    if repository_publish in COMPONENT_REPOSITORIES:
        plugins = manager.get_component_instances(
            stage="publish",
            components=components,
            distributions=distributions,
            config=config,
        )
    elif repository_publish in TEMPLATE_REPOSITORIES:
        plugins = manager.get_template_instances(
            stage="publish", templates=templates, config=config
        )
    else:
        raise CliError(f"Unknown repository '{repository_publish}'")

    for p in plugins:
        p.run(
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
            try:
                kwargs = {
                    "plugins_dirs": config.get_plugins_dirs(),
                    "executor": config.get_executor_from_config(stage_name="publish"),
                    "artifacts_dir": config.get_artifacts_dir(),
                    "verbose": config.verbose,
                    "debug": config.debug,
                    "qubes_release": config.get("qubes-release", {}),
                    "backend_vmm": config.get("backend-vmm", "xen"),
                    "gpg_client": config.get("gpg-client", "gpg"),
                    "sign_key": config.get("sign-key", {}),
                    "min_age_days": config.get("min-age-days", 5),
                    "repository_publish": config.get("repository-publish", {}),
                }
                plugin = PublishPlugin(component=component, dist=dist, **kwargs)
            except ComponentError:
                release_status[component.name][dist.distribution][
                    "status"
                ] = "no source"
                continue

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

            # We may have nothing to do for this component-distribution
            if not plugin.parameters["build"]:
                continue

            # FIXME: we pick the first build target found as we have checks
            #  for all being processed for all stages
            publish_info = plugin.get_dist_artifacts_info(
                stage="publish", basename=plugin.parameters["build"][0].mangle()
            )

            try:
                found = False
                for repo_name in COMPONENT_REPOSITORIES:
                    days = 0
                    if not all(
                        plugin.is_published(
                            basename=build.mangle(), repository=repo_name
                        )
                        for build in plugin.parameters["build"]
                    ):
                        continue
                    # Find the publish repository timestamp
                    for repo in publish_info.get("repository-publish", []):
                        if repo["name"] == repo_name:
                            publish_date = datetime.datetime.strptime(
                                repo["timestamp"], "%Y%m%d%H%M"
                            )
                            days = (datetime.datetime.utcnow() - publish_date).days
                            break

                    release_status[component.name][dist.distribution][
                        "status"
                    ] = "released"
                    release_status[component.name][dist.distribution].setdefault(
                        "repo", []
                    )
                    release_status[component.name][dist.distribution]["repo"].append(
                        {
                            "name": repo_name,
                            "days": days,
                            "min-age-days": config.get("min-age-days", 5),
                        }
                    )
                    found = True
            except (PluginError, ValueError, TypeError) as e:
                raise CliError(
                    f"{component}:{dist}: Failed to process status ({str(e)})."
                )

            if not found:
                if all(
                    plugin.get_dist_artifacts_info(
                        stage="build", basename=build.mangle()
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
        kwargs = {
            "plugins_dirs": config.get_plugins_dirs(),
            "executor": config.get_executor_from_config(stage_name="publish"),
            "artifacts_dir": config.get_artifacts_dir(),
            "verbose": config.verbose,
            "debug": config.debug,
            "qubes_release": config.get("qubes-release", {}),
            "backend_vmm": config.get("backend-vmm", "xen"),
            "gpg_client": config.get("gpg-client", "gpg"),
            "sign_key": config.get("sign-key", {}),
            "min_age_days": config.get("min-age-days", 5),
            "repository_publish": config.get("repository-publish", {}),
            "repository_upload_remote_host": config.get(
                "repository-upload-remote-host", {}
            ),
        }
        plugin = TemplateBuilderPlugin(template=template, **kwargs)
        try:
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
                    release_status[template.name]["status"] = "released"
                    release_status[template.name].setdefault("repo", [])
                    release_status[template.name]["repo"].append(
                        {
                            "name": repo_name,
                            "days": days,
                            "min-age-days": config.get("min-age-days", 5),
                        }
                    )
                    found = True
                    set_template_tag = True
        except (PluginError, ValueError) as e:
            raise CliError(f"{template}: Failed to process status ({str(e)}).")

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
    plugins: List[Union[UploadPlugin, TemplateBuilderPlugin]] = []
    if repository_publish in COMPONENT_REPOSITORIES:
        for dist in distributions:
            plugins += UploadPlugin(dist=dist, config=config)  # type: ignore
    elif repository_publish in TEMPLATE_REPOSITORIES:
        for tmpl in templates:
            plugins += TemplateBuilderPlugin(template=tmpl, config=config)  # type: ignore
    for p in plugins:
        p.run(stage="upload", repository_publish=repository_publish)


repository.add_command(publish)
repository.add_command(unpublish)
repository.add_command(check_release_status_for_component)
repository.add_command(check_release_status_for_template)
repository.add_command(upload)
