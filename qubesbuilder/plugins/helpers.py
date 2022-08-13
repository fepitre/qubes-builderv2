from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.template import QubesTemplate
from qubesbuilder.executors import Executor
from qubesbuilder.plugins import PluginError
from qubesbuilder.plugins.build_deb import DEBBuildPlugin
from qubesbuilder.plugins.build_rpm import RPMBuildPlugin
from qubesbuilder.plugins.publish_deb import DEBPublishPlugin
from qubesbuilder.plugins.publish_rpm import RPMPublishPlugin
from qubesbuilder.plugins.sign_deb import DEBSignPlugin
from qubesbuilder.plugins.sign_rpm import RPMSignPlugin
from qubesbuilder.plugins.source_deb import DEBSourcePlugin
from qubesbuilder.plugins.source_rpm import RPMSourcePlugin
from qubesbuilder.plugins.chroot_deb import DEBChrootPlugin
from qubesbuilder.plugins.chroot_rpm import RPMChrootPlugin


from qubesbuilder.plugins.template_rpm import RPMTemplateBuilderPlugin
from qubesbuilder.plugins.template_debian import DEBTemplateBuilderPlugin
from qubesbuilder.plugins.template_whonix import WhonixTemplateBuilderPlugin


def getSourcePlugin(
    component: QubesComponent,
    dist: QubesDistribution,
    plugins_dir: Path,
    executor: Executor,
    artifacts_dir: Path,
    **kwargs,
):
    if dist.is_deb():
        source_plugin = DEBSourcePlugin(
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    elif dist.is_rpm():
        source_plugin = RPMSourcePlugin(  # type: ignore
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    else:
        raise PluginError(f"{dist}: unsupported dist.")
    return source_plugin


def getBuildPlugin(
    component: QubesComponent,
    dist: QubesDistribution,
    plugins_dir: Path,
    executor: Executor,
    artifacts_dir: Path,
    **kwargs,
):
    if dist.is_deb():
        build_plugin = DEBBuildPlugin(
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    elif dist.is_rpm():
        build_plugin = RPMBuildPlugin(  # type: ignore
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    else:
        raise PluginError(f"{dist}: unsupported dist.")
    return build_plugin


def getSignPlugin(
    component: QubesComponent,
    dist: QubesDistribution,
    plugins_dir: Path,
    executor: Executor,
    artifacts_dir: Path,
    **kwargs,
):
    if dist.is_deb():
        sign_plugin = DEBSignPlugin(
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    elif dist.is_rpm():
        sign_plugin = RPMSignPlugin(  # type: ignore
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    else:
        raise PluginError(f"{dist}: unsupported dist.")
    return sign_plugin


def getPublishPlugin(
    component: QubesComponent,
    dist: QubesDistribution,
    plugins_dir: Path,
    executor: Executor,
    artifacts_dir: Path,
    **kwargs,
):
    if dist.is_deb():
        publish_plugin = DEBPublishPlugin(
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    elif dist.is_rpm():
        publish_plugin = RPMPublishPlugin(  # type: ignore
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    else:
        raise PluginError(f"{dist}: unsupported dist.")
    return publish_plugin


def getTemplatePlugin(
    template: QubesTemplate,
    plugins_dir: Path,
    executor: Executor,
    artifacts_dir: Path,
    **kwargs,
):

    if template.distribution.is_deb():
        if template.flavor in ("whonix-gateway", "whonix-workstation"):
            template_plugin = WhonixTemplateBuilderPlugin(
                template, executor, plugins_dir, artifacts_dir, **kwargs
            )
        else:
            template_plugin = DEBTemplateBuilderPlugin(  # type: ignore
                template, executor, plugins_dir, artifacts_dir, **kwargs
            )
    elif template.distribution.is_rpm():
        template_plugin = RPMTemplateBuilderPlugin(  # type: ignore
            template, executor, plugins_dir, artifacts_dir, **kwargs
        )
    else:
        raise PluginError(f"{template.distribution}: unsupported dist.")
    return template_plugin


def getChrootPlugin(
    dist: QubesDistribution,
    plugins_dir: Path,
    executor: Executor,
    artifacts_dir: Path,
    **kwargs,
):
    if dist.is_deb():
        chroot_plugin = DEBChrootPlugin(  # type: ignore
            dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    elif dist.is_rpm():
        chroot_plugin = RPMChrootPlugin(  # type: ignore
            dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    else:
        raise PluginError(f"{dist}: unsupported dist.")
    return chroot_plugin
