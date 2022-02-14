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
from qubesbuilder.plugins.template import TemplatePlugin


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
        source_plugin = RPMSourcePlugin(
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
        build_plugin = RPMBuildPlugin(
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
    if dist.is_deb() and not component.is_template():
        sign_plugin = DEBSignPlugin(
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    elif dist.is_rpm() or component.is_template():
        sign_plugin = RPMSignPlugin(
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
    if dist.is_deb() and not component.is_template():
        publish_plugin = DEBPublishPlugin(
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    elif dist.is_rpm() or component.is_template():
        publish_plugin = RPMPublishPlugin(
            component, dist, executor, plugins_dir, artifacts_dir, **kwargs
        )
    else:
        raise PluginError(f"{dist}: unsupported dist.")
    return publish_plugin


def getTemplatePlugin(
    component: QubesComponent,
    template: QubesTemplate,
    plugins_dir: Path,
    executor: Executor,
    artifacts_dir: Path,
    **kwargs,
):
    template_plugin = TemplatePlugin(
        component, template, executor, plugins_dir, artifacts_dir, **kwargs
    )
    return template_plugin
