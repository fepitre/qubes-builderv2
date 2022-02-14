# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2022 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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

from pathlib import Path
from datetime import datetime

from qubesbuilder.component import QubesComponent
from qubesbuilder.template import QubesTemplate
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import (
    Plugin,
    PluginError,
    BUILDER_DIR,
    BUILD_DIR,
    CACHE_DIR,
    REPOSITORY_DIR,
    PLUGINS_DIR,
)

log = get_logger("template")


class TemplateError(PluginError):
    pass


class TemplatePlugin(Plugin):
    """
    TemplatePlugin manages distribution build.
    """

    plugin_dependencies = ["source_rpm", "source_deb"]

    def __init__(
        self,
        component: QubesComponent,
        template: QubesTemplate,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool = False,
        debug: bool = False,
        use_qubes_repo: dict = None,
    ):
        super().__init__(
            component=component,
            dist=template.distribution,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.template = template
        self.executor = executor
        self.use_qubes_repo = use_qubes_repo or {}

        self.environment.update(
            {
                "USE_QUBES_REPO_VERSION": self.use_qubes_repo.get("version", None),
                "USE_QUBES_REPO_TESTING": 1
                if self.use_qubes_repo.get("testing", None)
                else 0,
            }
        )

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        super().update_parameters()

        # We call the get_parameters in order to set component version
        self.component.get_parameters(self._placeholders)

    def run(self, stage: str):
        # Update parameters
        self.update_parameters()

        if stage == "build":
            source_dir = BUILDER_DIR / self.component.name
            repository_dir = self.get_repository_dir() / self.dist.distribution
            artifacts_dir = self.get_templates_dir()

            prepared_images = artifacts_dir / "prepared_images"
            qubeized_image = artifacts_dir / "qubeized_images" / self.template.name

            prepared_images.mkdir(parents=True, exist_ok=True)
            qubeized_image.mkdir(parents=True, exist_ok=True)

            template_timestamp = datetime.utcnow().strftime("%Y%m%d%H%MZ")

            self.environment.update(
                {
                    "DIST_WITHOUT_FLAVOR": self.dist.name,
                    "DIST_NAME": self.dist.fullname,
                    "DIST_VER": self.dist.version,
                    "TEMPLATE_NAME": self.template.name,
                    "TEMPLATE_VERSION": self.component.version,
                    "TEMPLATE_FLAVOR": self.template.flavor,
                    "TEMPLATE_OPTIONS": " ".join(self.template.options),
                    "TEMPLATE_TIMESTAMP": template_timestamp,
                    "INSTALL_DIR": "/mnt",
                    "ARTIFACTS_DIR": BUILD_DIR,
                    "PLUGINS_DIR": PLUGINS_DIR,
                    "TEMPLATE_CONTENT_DIR": source_dir,
                    "PACKAGES_DIR": REPOSITORY_DIR,
                    "CACHE_DIR": CACHE_DIR / f"cache_{self.dist.name}",
                }
            )

            rpm = f"qubes-template-{self.template.name}-{self.component.version}-{template_timestamp}.noarch.rpm"

            copy_in = [
                (self.component.source_dir, BUILDER_DIR),
                (self.plugins_dir / "template", PLUGINS_DIR),
                (repository_dir, REPOSITORY_DIR),
            ] + [
                (self.plugins_dir / plugin, PLUGINS_DIR)
                for plugin in self.plugin_dependencies
            ]

            # Copy-in previously prepared base root img
            if (prepared_images / f"{self.template.name}.img").exists():
                copy_in += [
                    (prepared_images / f"{self.template.name}.img", BUILD_DIR / "prepared_images"),
                ]

            copy_out = [
                (
                    BUILD_DIR / "prepared_images" / f"{self.template.name}.img",
                    prepared_images,
                ),
                (
                    BUILD_DIR / "qubeized_images" / self.template.name / "root.img",
                    qubeized_image,
                ),
                (BUILD_DIR / f"build_timestamp_{self.template.name}", artifacts_dir),
                (BUILD_DIR / f"rpmbuild/RPMS/noarch/{rpm}", artifacts_dir / "rpm"),
            ]

            cmd = [f"make -C {PLUGINS_DIR}/template prepare build"]
            try:
                self.executor.run(cmd, copy_in, copy_out, environment=self.environment)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to build template."
                raise TemplateError(msg) from e
