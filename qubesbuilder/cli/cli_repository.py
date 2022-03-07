import click

from qubesbuilder.cli.cli_base import aliased_group, ContextObj
from qubesbuilder.plugins.helpers import getPublishPlugin, getTemplatePlugin


@aliased_group("repository", chain=True)
def repository():
    """
    Repository CLI
    """


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
    executor = obj.config.get_stages()["publish"]["executor"]
    if repository_publish in (
        "current",
        "current-testing",
        "security-testing",
        "unstable",
    ):
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
                    gpg_client=obj.config.get("gpg-client"),
                    sign_key=obj.config.get("sign-key"),
                    qubes_release=obj.config.get("qubes-release"),
                    repository_publish=obj.config.get("repository-publish"),
                )
                publish_plugin.run(
                    stage="publish",
                    repository_publish=repository_publish,
                    ignore_min_age=ignore_min_age,
                )
    elif repository_publish in (
        "templates-itl",
        "templates-itl-testing",
        "templates-community",
        "templates-community-testing",
    ):
        for tmpl in obj.templates:
            publish_plugin = getTemplatePlugin(
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
                repository_publish=obj.config.get("repository-publish"),
            )
            publish_plugin.run(
                stage="publish",
                repository_publish=repository_publish,
                ignore_min_age=ignore_min_age,
            )


repository.add_command(publish)
