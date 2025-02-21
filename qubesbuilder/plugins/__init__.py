# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2021 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later
from collections import namedtuple
from pathlib import Path, PurePosixPath
from typing import List, Dict, Any, Optional

import dateutil.parser
import yaml
from dateutil.parser import parse as parsedate

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.exc import QubesBuilderError
from qubesbuilder.log import QubesBuilderLogger
from qubesbuilder.template import QubesTemplate


class PackagePath(PurePosixPath):
    def mangle(self):
        return str(self).replace("/", "_")


class PluginError(QubesBuilderError):
    """
    Base plugin exception
    """

    def __init__(self, *args, additional_info=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.additional_info = additional_info or {}


JobReferenceBase = namedtuple(
    "JobReferenceBase", ["component", "dist", "template", "stage", "build"]
)
JobReferenceBase.__new__.__defaults__ = (None, None, None, None, None)


class JobReference(JobReferenceBase):
    __slots__ = ()

    def __repr__(self):
        parts = []
        if self.component is not None:
            parts.append(f"component={self.component.name}")
        if self.dist is not None:
            parts.append(f"dist={self.dist.distribution}")
        if self.template is not None:
            parts.append(f"template={self.template.name}")
        if self.stage is not None:
            parts.append(f"stage={self.stage}")
        if self.build is not None:
            parts.append(f"build={self.build}")
        return (
            f"JobReference({', '.join(parts)})" if parts else "JobReference()"
        )


class Dependency:
    def __init__(self, reference, builder_object):
        self.reference = reference
        if builder_object not in ["plugin", "component", "job"]:
            raise QubesBuilderError(
                f"Unsupported dependency type '{builder_object}'."
            )
        self.builder_object = builder_object


class PluginDependency(Dependency):
    def __init__(self, reference):
        super().__init__(reference=reference, builder_object="plugin")


class ComponentDependency(Dependency):
    def __init__(self, reference):
        super().__init__(reference=reference, builder_object="component")


class JobDependency(Dependency):
    def __init__(self, reference: JobReference):
        super().__init__(reference=reference, builder_object="job")


def get_artifact_path(config, job_ref: JobReference) -> Path:
    if job_ref.template:
        artifacts_path = (
            config.templates_dir
            / f"{job_ref.template.name}.{job_ref.stage}.yml"
        )
    elif job_ref.dist and job_ref.component:
        base_dir = (
            config.artifacts_dir
            / "components"
            / job_ref.component.name
            / job_ref.component.get_version_release()
            / job_ref.dist.distribution
            / job_ref.stage
        )
        if not job_ref.build:
            raise PluginError(
                "JobReference for DistributionComponentPlugin requires a build identifier."
            )
        basename = PackagePath(job_ref.build).mangle()
        filename = Plugin.get_artifacts_info_filename(job_ref.stage, basename)
        artifacts_path = base_dir.resolve() / filename
    elif job_ref.component:
        base_dir = (
            config.artifacts_dir
            / "components"
            / job_ref.component.name
            / job_ref.component.get_version_release()
            / "nodist"
            / job_ref.stage
        )
        if not job_ref.build:
            raise PluginError(
                "JobReference for ComponentPlugin requires a build identifier."
            )
        basename = PackagePath(job_ref.build).mangle()
        filename = Plugin.get_artifacts_info_filename(job_ref.stage, basename)
        artifacts_path = base_dir.resolve() / filename
    else:
        raise PluginError(
            "Missing distribution, component or template in JobReference!"
        )
    return artifacts_path


class Plugin:
    """
    Generic plugin
    """

    name = "_undefined_"
    stages: List[str] = []
    priority: int = 10
    dependencies: List[Dependency] = []

    @classmethod
    def from_args(cls, **kwargs):
        raise NotImplementedError

    @classmethod
    def get_artifacts_info_filename(cls, stage: str, basename: str):
        return f"{basename}.{stage}.yml"

    def __init__(self, config, stage, **kwargs):
        # Qubes builder config
        self.config = config

        # Plugin manager
        self.manager = self.config.get_plugin_manager()

        # Default placeholders
        self._placeholders: Dict[str, Any] = {}

        # Plugin parameters
        self._parameters: Dict[str, Any] = {}

        # Environment
        self.environment = {}
        if self.config.verbose:
            self.environment["VERBOSE"] = "1"
        if self.config.debug:
            self.environment["DEBUG"] = "1"
        self.environment["BACKEND_VMM"] = self.config.backend_vmm

        # Logger
        self.log = QubesBuilderLogger.getChild(self.name, self)

        # Stage
        self.stage = stage

        # Executor
        self.executor = self.config.get_executor_from_config(stage, self)

        # Dependencies
        self.dependencies = []  # type: List[Dependency]

    def get_artifact_context(self) -> dict:
        """
        Returns a dictionary of objects needed by ArtifactLocator.
        Base implementation returns only the config.
        Subclasses should extend this as needed.
        """
        return {"config": self.config}

    def check_dependencies(self):
        for dependency in self.dependencies:
            if dependency.builder_object == "plugin":
                if (
                    dependency.builder_object == "plugin"
                    and not self.manager.entities.get(
                        dependency.reference, None
                    )
                ):
                    raise PluginError(f"Cannot find plugin '{dependency}'.")
            elif dependency.builder_object == "component":
                component = self.config.get_components(
                    filtered_components=[dependency.reference]
                )
                if not component:
                    raise PluginError(
                        f"Cannot find component '{dependency}' in configuration file."
                    )
                if not self.config.sources_dir / dependency.reference:
                    raise PluginError(
                        f"Cannot find source component '{dependency.reference}' in artifacts."
                        f"Is package fetch stage done for '{dependency.reference}'"
                    )
                self.log.info(
                    f"dependency '{dependency.reference}' (commit hash: {component[0].get_source_commit_hash()})"
                )
            elif dependency.builder_object == "job":
                artifact_path = get_artifact_path(
                    self.config,
                    dependency.reference,
                )
                if not artifact_path or not artifact_path.exists():
                    # FIXME: improve formatting
                    raise PluginError(
                        f"Error retrieving artifact path for job dependency '{str(dependency.reference)}'"
                    )
            else:
                raise PluginError(
                    f"Unknown dependency associated with builder object '{dependency.builder_object}'."
                )

    def run(self):
        log_file = self.log.get_log_file()
        if log_file:
            self.log.info(f"Log file: {log_file}")
        self.check_dependencies()

    def update_parameters(self, stage: str):
        self._parameters.setdefault(stage, {})

    def update_placeholders(self, stage: str):
        self._placeholders.setdefault(stage, self.executor.get_placeholders())

    def get_placeholders(self, stage: str):
        self.update_placeholders(stage)
        return self._placeholders[stage]

    def get_parameters(self, stage: str):
        self.update_parameters(stage)
        return self._parameters[stage]

    def get_cache_dir(self) -> Path:
        return (self.config.artifacts_dir / "cache").resolve()

    def get_sources_dir(self) -> Path:
        return (self.config.artifacts_dir / "sources").resolve()

    def get_repository_dir(self) -> Path:
        return (self.config.artifacts_dir / "repository").resolve()

    def get_repository_publish_dir(self) -> Path:
        return (self.config.artifacts_dir / "repository-publish").resolve()

    def get_distfiles_dir(self) -> Path:
        return (self.config.artifacts_dir / "distfiles").resolve()

    def get_templates_dir(self) -> Path:
        return (self.config.artifacts_dir / "templates").resolve()

    def get_installer_dir(self) -> Path:
        return (self.config.artifacts_dir / "installer").resolve()

    def get_iso_dir(self) -> Path:
        return (self.config.artifacts_dir / "iso").resolve()

    def get_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path
    ) -> Dict:
        fileinfo = artifacts_dir / self.get_artifacts_info_filename(
            stage, basename
        )
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = f"{basename}: Failed to read info from {stage} stage."
                raise PluginError(msg) from e
        return {}

    def default_copy_in(self, plugins_dir: Path, sources_dir: Path):
        copy_in = [(self.manager.entities[self.name].directory, plugins_dir)]
        for dependency in self.dependencies:
            if dependency.builder_object == "plugin":
                copy_in.append(
                    (
                        self.manager.entities[dependency.reference].directory,
                        plugins_dir,
                    )
                )
            if dependency.builder_object == "component":
                copy_in.append(
                    (
                        (self.config.sources_dir / dependency.reference),
                        sources_dir,
                    )
                )
        return copy_in


class ComponentPlugin(Plugin):
    """
    Component plugin
    """

    @classmethod
    def from_args(cls, **kwargs):
        if kwargs.get("stage") in cls.stages and kwargs.get("component"):
            return cls(**kwargs)

    def __init__(
        self,
        component: QubesComponent,
        config,
        stage: str,
        **kwargs,
    ):
        self.component = component
        super().__init__(config=config, stage=stage, **kwargs)
        self._source_hash = ""

    def update_placeholders(self, stage: str):
        super().update_placeholders(stage)
        self._placeholders[stage].update(
            {
                "@SOURCE_DIR@": self.executor.get_builder_dir()
                / self.component.name,
                "@BACKEND_VMM@": self.config.backend_vmm,
            }
        )

    def get_component_distfiles_dir(self) -> Path:
        return (self.config.distfiles_dir / self.component.name).resolve()

    def get_component_artifacts_dir(self, stage: str) -> Path:
        path = (
            self.config.artifacts_dir
            / "components"
            / self.component.name
            / self.component.get_version_release()
            / "nodist"
            / stage
        )
        return path.resolve()

    def get_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Optional[Path] = None
    ) -> Dict:
        a_dir: Path = artifacts_dir or self.get_component_artifacts_dir(stage)
        return super().get_artifacts_info(stage, basename, a_dir)

    def save_artifacts_info(
        self,
        stage: str,
        basename: str,
        info: dict,
        artifacts_dir: Optional[Path] = None,
    ):
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(
                artifacts_dir
                / self.get_artifacts_info_filename(stage, basename),
                "w",
            ) as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = f"{self.component}:{basename}: Failed to write info for {stage} stage."
            raise PluginError(msg) from e

    def delete_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Optional[Path] = None
    ):
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        info_path = artifacts_dir / self.get_artifacts_info_filename(
            stage, basename
        )
        if info_path.exists():
            info_path.unlink()

    def check_stage_artifacts(
        self, stage: str, artifacts_dir: Optional[Path] = None
    ):
        for build in self.get_parameters(stage).get("build", []):
            build_bn = build.mangle()
            if not self.get_artifacts_info(
                stage=stage, basename=build_bn, artifacts_dir=artifacts_dir
            ):
                msg = f"Missing '{stage}' stage artifacts for {build_bn}!"
                raise PluginError(msg)


class DistributionPlugin(Plugin):
    def __init__(self, dist, config, stage, **kwargs):
        self.dist = dist
        super().__init__(config=config, stage=stage, **kwargs)

    @classmethod
    def supported_distribution(cls, distribution):
        raise NotImplementedError

    @classmethod
    def from_args(cls, **kwargs):
        if kwargs.get("stage") in cls.stages and cls.supported_distribution(
            kwargs.get("dist")
        ):
            return cls(**kwargs)


def get_stage_options(stage: str, options: dict):
    stages = options.get("stages", [])
    s = next((s for s in stages if stage in s), {})
    return s.get(stage, {})


class DistributionComponentPlugin(DistributionPlugin, ComponentPlugin):
    @classmethod
    def from_args(cls, **kwargs):
        if (
            kwargs.get("stage") in cls.stages
            and kwargs.get("component")
            and cls.supported_distribution(kwargs.get("dist"))
        ):
            return cls(**kwargs)

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        config,
        stage: str,
        **kwargs,
    ):
        self.dist = dist
        ComponentPlugin.__init__(
            self,
            component=component,
            config=config,
            stage=stage,
            **kwargs,
        )

    def run(self):
        super().run()

        if not self.get_parameters(self.stage).get("build", []):
            self.log.info(f"{self.component}:{self.dist}: Nothing to be done.")
            return

    def update_parameters(self, stage: str):
        super().update_parameters(stage)

        parameters = self.component.get_parameters(self.get_placeholders(stage))

        # host/vm -> rpm/deb/archlinux
        self._parameters[stage].update(
            parameters.get(self.dist.package_set, {}).get(self.dist.type, {})
        )
        # host/vm -> fedora/debian/ubuntu/archlinux
        self._parameters[stage].update(
            parameters.get(self.dist.package_set, {}).get(
                self.dist.fullname, {}
            )
        )
        # Per distribution (e.g. host-fc42) overrides per package set (e.g. host)
        self._parameters[stage].update(
            parameters.get(self.dist.distribution, {}).get(self.dist.type, {})
        )

        self._parameters[stage]["build"] = [
            PackagePath(build)
            for build in self._parameters[stage].get("build", [])
        ]
        # Check conflicts when mangle paths
        mangle_builds = [
            build.mangle() for build in self._parameters[stage].get("build", [])
        ]
        if len(set(mangle_builds)) != len(self._parameters[stage]["build"]):
            raise PluginError(
                f"{self.component}:{self.dist}: Conflicting build paths"
            )

    def get_config_stage_options(self, stage: str):
        stage_options = {}
        stage_options.update(get_stage_options(stage, self.dist.kwargs))
        stage_options.update(get_stage_options(stage, self.component.kwargs))
        return stage_options

    def get_dist_component_artifacts_dir_history(
        self, stage: str
    ) -> List[Path]:
        path = (
            self.config.artifacts_dir / "components" / self.component.name
        ).resolve()
        return list(path.glob(f"*/{self.dist.distribution}/{stage}"))

    def get_dist_component_artifacts_dir(self, stage: str) -> Path:
        path = (
            self.config.artifacts_dir
            / "components"
            / self.component.name
            / self.component.get_version_release()
            / self.dist.distribution
            / stage
        )
        return path.resolve()

    def get_dist_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Optional[Path] = None
    ) -> Dict:
        return self.get_artifacts_info(
            stage,
            basename,
            artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )

    def save_dist_artifacts_info(
        self,
        stage: str,
        basename: str,
        info: dict,
        artifacts_dir: Optional[Path] = None,
    ):
        return self.save_artifacts_info(
            stage,
            basename,
            info,
            artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )

    def delete_dist_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Optional[Path] = None
    ):
        return self.delete_artifacts_info(
            stage,
            basename,
            artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )

    def check_dist_stage_artifacts(
        self, stage: str, artifacts_dir: Optional[Path] = None
    ):
        return self.check_stage_artifacts(
            stage, artifacts_dir or self.get_dist_component_artifacts_dir(stage)
        )

    def has_component_packages(self, stage: str):
        self.update_parameters(stage)
        return self.component.has_packages and self.get_parameters(stage).get(
            "build", []
        )


class TemplatePlugin(DistributionPlugin):
    def __init__(
        self,
        template: QubesTemplate,
        config,
        stage: str,
        **kwargs,
    ):
        self.template = template
        super().__init__(
            config=config,
            dist=template.distribution,
            stage=stage,
            **kwargs,
        )

    @classmethod
    def supported_template(cls, template: QubesTemplate):
        raise NotImplementedError

    @classmethod
    def from_args(cls, **kwargs):
        if isinstance(
            kwargs.get("template"), QubesTemplate
        ) and cls.supported_template(kwargs["template"]):
            return cls(**kwargs)

    def get_template_artifacts_info(self, stage: str) -> Dict:
        fileinfo = (
            self.config.templates_dir / f"{self.template.name}.{stage}.yml"
        )
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = (
                    f"{self.template}: Failed to read info from {stage} stage."
                )
                raise PluginError(msg) from e
        return {}

    def save_artifacts_info(self, stage: str, info: dict):
        artifacts_dir = self.config.templates_dir
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(artifacts_dir / f"{self.template}.{stage}.yml", "w") as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = f"{self.template}: Failed to write info for {stage} stage."
            raise PluginError(msg) from e

    def delete_artifacts_info(self, stage: str):
        artifacts_dir = self.config.templates_dir
        info_path = artifacts_dir / f"{self.template}.{stage}.yml"
        if info_path.exists():
            info_path.unlink()

    def get_template_timestamp(self, stage="build") -> str:
        if not self.template.timestamp:
            # Read information from build stage. We need info from 'prep' stage
            # only when retrying timestamp information in 'build' stage if the
            # build occurs in two calls instead of one.
            info = self.get_template_artifacts_info(stage)
            if not info.get("timestamp", None):
                raise PluginError(
                    f"{self.template}: Cannot determine template timestamp. Missing '{stage}' stage?"
                )
            try:
                self.template.timestamp = parsedate(info["timestamp"]).strftime(
                    "%Y%m%d%H%M"
                )
            except (dateutil.parser.ParserError, IndexError) as e:
                msg = (
                    f"{self.template}: Failed to parse build timestamp format."
                )
                raise PluginError(msg) from e
        return self.template.timestamp


class RPMDistributionPlugin(DistributionPlugin):
    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        return distribution.is_rpm()


class DEBDistributionPlugin(DistributionPlugin):
    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        return distribution.is_deb() or distribution.is_ubuntu()


class ArchlinuxDistributionPlugin(DistributionPlugin):
    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        return distribution.is_archlinux()


class GentooDistributionPlugin(DistributionPlugin):
    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        return distribution.is_gentoo()

class WindowsDistributionPlugin(DistributionPlugin):
    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        return distribution.is_windows()
