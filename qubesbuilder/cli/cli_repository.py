import click

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.plugins.helpers import (
    getPublishPlugin,
)


@aliased_group("repository", chain=True)
def repository():
    """
    Repository CLI
    """


#
# Packages
#


def _publish_to_repository(
    obj: ContextObj, publish_repository: str, ignore_min_age: bool = False
):
    executor = obj.config.get_stages()["publish"]["executor"]
    for component in obj.components:
        if component.is_template():
            continue
        for dist in obj.distributions:
            publish_plugin = getPublishPlugin(
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
                publish_repository=obj.config.get("publish-repository"),
            )
            publish_plugin.run(
                stage="publish",
                publish_repository=publish_repository,
                ignore_min_age=ignore_min_age,
            )


# current


@click.command(
    name="publish-to-current", short_help="Publish packages to 'current' repository."
)
@click.option(
    "--ignore-min-age",
    default=False,
    is_flag=True,
    help="Override minimum age for authorizing publication into 'current'.",
)
@click.pass_obj
def publish_to_current(obj: ContextObj, ignore_min_age: bool):
    _publish_to_repository(
        obj, publish_repository="current", ignore_min_age=ignore_min_age
    )


# current-testing


@click.command(
    name="publish-to-current-testing",
    short_help="Publish packages to 'current-testing' repository.",
)
@click.pass_obj
def publish_to_current_testing(obj: ContextObj):
    _publish_to_repository(obj, publish_repository="current-testing")


# security-testing


@click.command(
    name="publish-to-security-testing",
    short_help="Publish packages to 'security-testing' repository.",
)
@click.pass_obj
def publish_to_security_testing(obj: ContextObj):
    _publish_to_repository(obj, publish_repository="current-testing")


# unstable


@click.command(
    name="publish-to-unstable",
    short_help="Publish packages to 'unstable' repository.",
)
@click.pass_obj
def publish_to_unstable(obj: ContextObj):
    _publish_to_repository(obj, publish_repository="unstable")


repository.add_command(publish_to_current)
repository.add_command(publish_to_current_testing)
repository.add_command(publish_to_security_testing)
repository.add_command(publish_to_unstable)


#
# Templates
#


def _publish_template_to_repository(
    obj: ContextObj, publish_repository: str, ignore_min_age: bool = False
):
    executor = obj.config.get_stages()["publish"]["executor"]
    for component in obj.components:
        if not component.is_template():
            continue
        for tmpl in obj.templates:
            publish_plugin = getPublishPlugin(
                component=component,
                template=tmpl,
                dist=tmpl.distribution,
                plugins_dir=obj.config.get_plugins_dir(),
                executor=executor,
                artifacts_dir=obj.config.get_artifacts_dir(),
                verbose=obj.config.verbose,
                debug=obj.config.debug,
                gpg_client=obj.config.get("gpg-client"),
                sign_key=obj.config.get("sign-key"),
                qubes_release=obj.config.get("qubes-release"),
                publish_repository=obj.config.get("publish-repository"),
            )
            publish_plugin.run(
                stage="publish",
                publish_repository=publish_repository,
                ignore_min_age=ignore_min_age,
            )


# ITL


@click.command(
    name="publish-to-templates-itl",
    short_help="Publish template to 'templates-itl' repository.",
)
@click.option(
    "--ignore-min-age",
    default=False,
    is_flag=True,
    help="Override minimum age for authorizing publication into 'templates-itl'.",
)
@click.pass_obj
def publish_to_templates_itl(obj: ContextObj, ignore_min_age: bool):
    _publish_template_to_repository(
        obj, publish_repository="templates-itl", ignore_min_age=ignore_min_age
    )


@click.command(
    name="publish-to-templates-itl-testing",
    short_help="Publish template to 'templates-itl-testing' repository.",
)
@click.pass_obj
def publish_to_templates_itl_testing(obj: ContextObj):
    _publish_template_to_repository(obj, publish_repository="templates-itl-testing")


# Community


@click.command(
    name="publish-to-templates-community",
    short_help="Publish template to 'templates-community' repository.",
)
@click.option(
    "--ignore-min-age",
    default=False,
    is_flag=True,
    help="Override minimum age for authorizing publication into 'templates-community'.",
)
@click.pass_obj
def publish_to_templates_community(obj: ContextObj, ignore_min_age: bool):
    _publish_template_to_repository(
        obj, publish_repository="templates-community", ignore_min_age=ignore_min_age
    )


@click.command(
    name="publish-to-templates-community-testing",
    short_help="Publish template to 'templates-community-testing' repository.",
)
@click.pass_obj
def publish_to_templates_community_testing(obj: ContextObj):
    _publish_template_to_repository(
        obj, publish_repository="templates-community-testing"
    )


repository.add_command(publish_to_templates_itl)
repository.add_command(publish_to_templates_itl_testing)
repository.add_command(publish_to_templates_community)
repository.add_command(publish_to_templates_community_testing)
