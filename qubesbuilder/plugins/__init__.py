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

from pathlib import Path, PurePosixPath
from typing import List, Dict, Any

import dateutil.parser
import yaml
from dateutil.parser import parse as parsedate

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.template import QubesTemplate


# from qubesbuilder.config import Config


class PackagePath(PurePosixPath):
    def mangle(self):
        return str(self).replace("/", "_")


class PluginError(Exception):
    """
    Base plugin exception
    """

    pass


class Plugin:
    """
    Generic plugin
    """

    stages: List[str] = []
    priority: int = 10
    dependencies: List[str] = []

    @classmethod
    def from_args(cls, **kwargs):
        return []

    def __init__(self, config, manager, **kwargs):
        # Qubes builder config
        self.config = config

        # Plugin manager
        self.manager = manager

        # Default placeholders
        self._placeholders: Dict[str, Any] = {}

        # Plugin parameters
        self._parameters: dict = {}

        self.environment = {}
        if self.config.verbose:
            self.environment["VERBOSE"] = "1"
        if self.config.debug:
            self.environment["DEBUG"] = "1"

        self.environment["BACKEND_VMM"] = self.config.backend_vmm

    def run(self, stage: str):
        pass

    def update_parameters(self, stage: str):
        pass

    def update_placeholders(self, stage: str):
        # Executor
        executor = self.config.get_executor_from_config(stage)

        # Default placeholders
        self._placeholders.update(
            {
                "@BUILDER_DIR@": executor.get_builder_dir(),
                "@BUILD_DIR@": executor.get_build_dir(),
                "@PLUGINS_DIR@": executor.get_plugins_dir(),
                "@DISTFILES_DIR@": executor.get_distfiles_dir(),
            }
        )

    def get_parameters(self, stage: str):
        self.update_parameters(stage)
        return self._parameters

    def get_placeholders(self, stage: str):
        self.update_placeholders(stage)
        return self._placeholders

    def get_temp_dir(self):
        path = self.config.artifacts_dir / "tmp"
        return path.resolve()

    def get_cache_dir(self):
        path = self.config.artifacts_dir / "cache"
        return path.resolve()

    def get_sources_dir(self):
        path = self.config.artifacts_dir / "sources"
        return path.resolve()

    def get_repository_dir(self):
        path = self.config.artifacts_dir / "repository"
        return path.resolve()

    def get_repository_publish_dir(self):
        path = self.config.artifacts_dir / "repository-publish"
        return path.resolve()

    def get_distfiles_dir(self):
        path = self.config.artifacts_dir / "distfiles"
        return path.resolve()

    def get_templates_dir(self):
        path = self.config.artifacts_dir / "templates"
        return path.resolve()

    def get_installer_dir(self):
        path = self.config.artifacts_dir / "installer"
        return path.resolve()

    def get_iso_dir(self):
        path = self.config.artifacts_dir / "iso"
        return path.resolve()


class ComponentPlugin(Plugin):
    """
    Component plugin
    """

    dependencies: List[str] = []

    @classmethod
    def from_args(cls, **kwargs):
        instances = []
        if kwargs.get("stage") in cls.stages:
            for component in kwargs.get("components", []):
                instances.append(cls(component=component, **kwargs))
        return instances

    def __init__(
        self, component: QubesComponent, config, manager: PluginManager, **kwargs
    ):
        super().__init__(config=config, manager=manager, **kwargs)
        self.component = component
        self._source_hash = ""

    def update_placeholders(self, stage: str):
        super().update_placeholders(stage)

        executor = self.config.get_executor_from_config(stage)
        self._placeholders.update(
            {
                "@SOURCE_DIR@": executor.get_builder_dir() / self.component.name,
                "@BACKEND_VMM@": self.config.backend_vmm,
            }
        )

    @staticmethod
    def get_artifacts_info_filename(stage: str, basename: str):
        return f"{basename}.{stage}.yml"

    def get_component_distfiles_dir(self):
        path = self.get_distfiles_dir() / self.component.name
        return path

    def get_component_artifacts_dir(self, stage: str):
        path = self.config.artifacts_dir / "components" / self.component.name
        path = path / f"{self.component.version}-{self.component.release}"
        path = path / "nodist" / stage
        return path.resolve()

    def get_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ) -> Dict:
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        fileinfo = artifacts_dir / self.get_artifacts_info_filename(stage, basename)
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = f"{self.component}:{basename}: Failed to read info from {stage} stage."
                raise PluginError(msg) from e
        return {}

    def save_artifacts_info(
        self, stage: str, basename: str, info: dict, artifacts_dir: Path = None
    ):
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(
                artifacts_dir / self.get_artifacts_info_filename(stage, basename), "w"
            ) as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = (
                f"{self.component}:{basename}: Failed to write info for {stage} stage."
            )
            raise PluginError(msg) from e

    def delete_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ):
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        info_path = artifacts_dir / self.get_artifacts_info_filename(stage, basename)
        if info_path.exists():
            info_path.unlink()

    def check_stage_artifacts(self, stage: str, artifacts_dir: Path = None):
        for build in self.get_parameters(stage).get("build", []):
            build_bn = build.mangle()
            if not self.get_artifacts_info(
                stage=stage, basename=build_bn, artifacts_dir=artifacts_dir
            ):
                msg = f"Missing '{stage}' stage artifacts for {build_bn}!"
                raise PluginError(msg)


class DistributionPlugin(Plugin):
    def __init__(self, dist, config, manager, **kwargs):
        super().__init__(config=config, manager=manager, **kwargs)
        self.dist = dist

    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        raise NotImplementedError

    @classmethod
    def from_args(cls, **kwargs):
        instances = []
        if kwargs.get("stage", None) in cls.stages:
            for dist in kwargs.get("distributions", []):
                if not cls.supported_distribution(dist):
                    continue
                instances.append(cls(dist=dist, **kwargs))
        return instances


class DistributionComponentPlugin(DistributionPlugin, ComponentPlugin):
    """
    Distribution Component plugin

    Entry points:
        - PACKAGE-SET
        - PACKAGE_SET-DISTRIBUTION_NAME
    """

    dependencies: List[str] = []

    @classmethod
    def from_args(cls, **kwargs):
        instances = []
        if kwargs.get("stage", None) in cls.stages:
            for component in kwargs.get("components", []):
                for dist in kwargs.get("distributions", []):
                    if not cls.supported_distribution(dist):
                        continue
                    instances.append(cls(component=component, dist=dist, **kwargs))
        return instances

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        config,
        manager: PluginManager,
    ):
        super().__init__(dist=dist, component=component, config=config, manager=manager)

    def update_parameters(self, stage: str):
        super().update_parameters(stage)

        # Per distribution (e.g. host-fc42) overrides per package set (e.g. host)
        parameters = self.component.get_parameters(self.get_placeholders(stage))

        self._parameters.update(
            parameters.get(self.dist.package_set, {}).get(self.dist.type, {})
        )
        self._parameters.update(
            parameters.get(self.dist.distribution, {}).get(self.dist.type, {})
        )

        self._parameters["build"] = [
            PackagePath(build) for build in self._parameters.get("build", [])
        ]
        # For retro-compatibility
        if self.dist.type == "rpm":
            self._parameters["build"] += [
                PackagePath(spec) for spec in self._parameters.get("spec", [])
            ]
        # Check conflicts when mangle paths
        mangle_builds = [build.mangle() for build in self._parameters.get("build", [])]
        if len(set(mangle_builds)) != len(self._parameters["build"]):
            raise PluginError(f"{self.component}:{self.dist}: Conflicting build paths")

    def get_dist_component_artifacts_dir_history(self, stage: str):
        path = (
            self.config.artifacts_dir / "components" / self.component.name
        ).resolve()
        return list(path.glob(f"*/{self.dist.distribution}/{stage}"))

    def get_dist_component_artifacts_dir(self, stage: str):
        path = self.config.artifacts_dir / "components" / self.component.name
        path = path / f"{self.component.version}-{self.component.release}"
        path = path / self.dist.distribution / stage
        return path.resolve()

    def get_dist_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ) -> Dict:
        return self.get_artifacts_info(
            stage=stage,
            basename=basename,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )

    def save_dist_artifacts_info(
        self, stage: str, basename: str, info: dict, artifacts_dir: Path = None
    ):
        return self.save_artifacts_info(
            stage=stage,
            basename=basename,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
            info=info,
        )

    def delete_dist_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ):
        return self.delete_artifacts_info(
            stage=stage,
            basename=basename,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )

    def check_dist_stage_artifacts(self, stage: str, artifacts_dir: Path = None):
        return self.check_stage_artifacts(
            stage=stage,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )


class TemplatePlugin(DistributionPlugin):
    def __init__(self, template: QubesTemplate, config, manager: PluginManager):
        super().__init__(config=config, manager=manager, dist=template.distribution)
        self.template = template

    @classmethod
    def supported_template(cls, template: QubesTemplate):
        raise NotImplementedError

    @classmethod
    def from_args(cls, templates, **kwargs):
        instances = []
        for template in templates:
            if not cls.supported_template(template):
                continue
            instances.append(cls(template=template, **kwargs))
        return instances

    def get_artifacts_info(self, stage: str) -> Dict:
        fileinfo = self.get_templates_dir() / f"{self.template.name}.{stage}.yml"
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = f"{self.template}: Failed to read info from {stage} stage."
                raise PluginError(msg) from e
        return {}

    def save_artifacts_info(self, stage: str, info: dict):
        artifacts_dir = self.get_templates_dir()
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(artifacts_dir / f"{self.template}.{stage}.yml", "w") as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = f"{self.template}: Failed to write info for {stage} stage."
            raise PluginError(msg) from e

    def delete_artifacts_info(self, stage: str):
        artifacts_dir = self.get_templates_dir()
        info_path = artifacts_dir / f"{self.template}.{stage}.yml"
        if info_path.exists():
            info_path.unlink()

    def get_template_timestamp(self) -> str:
        if not self.template.timestamp:
            # Read information from build stage
            if not (
                self.get_templates_dir() / f"build_timestamp_{self.template.name}"
            ).exists():
                raise PluginError(f"{self.template}: Cannot find build timestamp.")
            with open(
                self.get_templates_dir() / f"build_timestamp_{self.template.name}"
            ) as f:
                data = f.read().splitlines()

            try:
                self.template.timestamp = parsedate(data[0]).strftime("%Y%m%d%H%M")
            except (dateutil.parser.ParserError, IndexError) as e:
                msg = f"{self.template}: Failed to parse build timestamp format."
                raise PluginError(msg) from e
        return self.template.timestamp


class RPMDistributionPlugin(DistributionPlugin):
    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        return distribution.is_rpm()


class DEBDistributionPlugin(DistributionPlugin):
    @classmethod
    def supported_distribution(cls, distribution: QubesDistribution):
        return distribution.is_deb()
