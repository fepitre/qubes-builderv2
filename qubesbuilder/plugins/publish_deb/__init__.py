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
from pathlib import Path

import yaml

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.publish import PublishPlugin, PublishError

log = get_logger("publish_deb")


class DEBPublishPlugin(PublishPlugin):
    """
    DEGBPublishPlugin manages DEB distribution publication.
    """

    plugin_dependencies = ["publish"]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        qubes_release: str,
        gpg_client: str,
        sign_key: dict,
        publish_repository: dict,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(
            component=component,
            dist=dist,
            plugins_dir=plugins_dir,
            executor=executor,
            artifacts_dir=artifacts_dir,
            qubes_release=qubes_release,
            gpg_client=gpg_client,
            sign_key=sign_key,
            publish_repository=publish_repository,
            verbose=verbose,
            debug=debug,
        )

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        super().update_parameters()

        # Per distribution (e.g. vm-bookworm) overrides per package set (e.g. vm)
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get(self.dist.package_set, {}).get("deb", {}))
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("deb", {})
        )

    def run(self, stage: str):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage == "publish":
            # Update parameters
            self.update_parameters()

            # Check if we have Debian related content defined
            if not self.parameters.get("build", []):
                log.info(f"{self.component}:{self.dist}: Nothing to be done.")
                return

            # Check if we have a signing key provided
            sign_key = self.sign_key.get(
                self.dist.distribution, None
            ) or self.sign_key.get("deb", None)
            if not sign_key:
                log.info(f"{self.component}:{self.dist}: No signing key found.")
                return

            # Check if we have a gpg client provided
            if not self.gpg_client:
                log.info(f"{self.component}: Please specify GPG client to use!")
                return

            # Check publish repository is valid
            publish_repository = self.publish_repository.get(
                "components", "current-testing"
            )
            if publish_repository not in (
                "current-testing",
                "security-testing",
                "unstable",
            ):
                msg = (
                    f"{self.component}:{self.dist}: "
                    f"Refusing to publish components into '{publish_repository}'."
                )
                raise PublishError(msg)

            # Build artifacts (source included)
            build_artifacts_dir = self.get_component_dir(stage="build")
            # Sign artifacts
            sign_artifacts_dir = self.get_component_dir(stage="sign")
            keyring_dir = sign_artifacts_dir / "keyring"
            # Publish artifacts
            artifacts_dir = self.get_repository_publish_dir() / self.dist.family

            if not sign_artifacts_dir.exists():
                raise PublishError("Cannot find keyring from sign stage.")

            # Create publish repository skeleton
            create_skeleton_cmd = [
                f"{self.plugins_dir}/publish_deb/scripts/create-skeleton",
                self.qubes_release,
                str(artifacts_dir),
            ]
            cmd = [" ".join(create_skeleton_cmd)]
            try:
                self.executor.run(cmd)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to create repository skeleton."
                raise PublishError(msg) from e

            for directory in self.parameters["build"]:
                # Read information from build stage
                with open(build_artifacts_dir / f"{directory}_build_info.yml") as f:
                    build_info = yaml.safe_load(f.read())

                if not build_info.get("changes", None):
                    log.info(
                        f"{self.component}:{self.dist}:{directory}: Nothing to sign."
                    )
                    continue

                # Verify signatures
                try:
                    log.info(
                        f"{self.component}:{self.dist}:{directory}: Verifying signatures."
                    )
                    cmd = []
                    for file in ("dsc", "changes", "buildinfo"):
                        fname = build_artifacts_dir / build_info[file]
                        cmd += [f"gpg2 -q --homedir {keyring_dir} --verify {fname}"]
                    self.executor.run(cmd)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to sign packages."
                    raise PublishError(msg) from e

                # Publishing packages
                try:
                    log.info(
                        f"{self.component}:{self.dist}:{directory}: Publishing packages."
                    )
                    changes_file = build_artifacts_dir / build_info["changes"]
                    target_dir = (
                        artifacts_dir
                        / f"{self.qubes_release}/{publish_repository}/{self.dist.package_set}"
                    )
                    reprepro_options = f"--ignore=surprisingbinary --ignore=surprisingarch -b {target_dir}"
                    cmd = [
                        f"reprepro {reprepro_options} include {self.dist.name} {changes_file}"
                    ]
                    self.executor.run(cmd)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to publish packages."
                    raise PublishError(msg) from e
