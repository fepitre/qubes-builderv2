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

import os
import shutil
from pathlib import Path

import yaml

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.publish import PublishPlugin, PublishError

log = get_logger("publish_rpm")


class RPMPublishPlugin(PublishPlugin):
    """
    RPMPublishPlugin manages RPM distribution publication.
    """

    plugin_dependencies = ["publish", "sign_rpm"]

    def __init__(self, component: QubesComponent, dist: QubesDistribution, executor: Executor, plugins_dir: Path,
                 artifacts_dir: Path, qubes_release: str, gpg_client: str, sign_key: dict,
                 publish_repository: dict, verbose: bool = False, debug: bool = False):
        super().__init__(component=component, dist=dist, plugins_dir=plugins_dir, executor=executor,
                         artifacts_dir=artifacts_dir, qubes_release=qubes_release,
                         gpg_client=gpg_client, sign_key=sign_key,
                         publish_repository=publish_repository, verbose=verbose, debug=debug)

        self.executor = executor
        self.verbose = verbose
        self.debug = debug

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        super().update_parameters()

        # Per distribution (e.g. host-fc42) overrides per package set (e.g. host)
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get(self.dist.package_set, {}).get("rpm", {}))
        self.parameters.update(parameters.get(self.dist.distribution, {}).get("rpm", {}))

    def run(self, stage: str):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage == "publish":
            # Update parameters
            self.update_parameters()

            # Check if we have RPM related content defined
            if not self.parameters.get("spec", []):
                log.info(f"{self.component}:{self.dist}: Nothing to be done.")
                return

            # Check publish repository is valid
            if self.component.is_template():
                publish_repository = self.publish_repository.get("templates", "templates-itl-testing")
                if publish_repository not in \
                        ("templates-itl-testing", "templates-community-testing"):
                    msg = f"{self.component}:{self.dist}: " \
                          f"Refusing to publish templates into '{publish_repository}'."
                    raise PublishError(msg)
            else:
                publish_repository = self.publish_repository.get("components", "current-testing")
                if publish_repository not in \
                        ("current-testing", "security-testing", "unstable"):
                    msg = f"{self.component}:{self.dist}: " \
                          f"Refusing to publish components into '{publish_repository}'."
                    raise PublishError(msg)

            # Check if we have a signing key provided
            sign_key = self.sign_key.get(self.dist.distribution, None) or \
                       self.sign_key.get("rpm", None)
            if not sign_key:
                log.info(f"{self.component}:{self.dist}: No signing key found.")
                return

            # Check if we have a gpg client provided
            if not self.gpg_client:
                log.info(f"{self.component}: Please specify GPG client to use!")
                return

            # Source artifacts
            prep_artifacts_dir = self.get_component_dir(stage="prep")
            # Build artifacts
            build_artifacts_dir = self.get_component_dir(stage="build")
            # Sign artifacts
            sign_artifacts_dir = self.get_component_dir(stage="sign")
            # Publish artifacts
            artifacts_dir = self.get_repository_publish_dir() / self.dist.family

            # Ensure dbpath from sign stage (still) exists
            db_path = sign_artifacts_dir / 'rpmdb'
            if not db_path.exists():
                msg = f"{self.component}: {self.dist}: Failed to find RPM DB path."
                raise PublishError(msg)

            # Create publish repository skeleton
            comps = self.plugins_dir / f"publish_rpm/comps/comps-{self.dist.package_set}.xml"
            create_skeleton_cmd = [
                f"{self.plugins_dir}/publish_rpm/scripts/create-skeleton", self.qubes_release,
                self.dist.package_set, self.dist.name, str(artifacts_dir.absolute()),
                str(comps.absolute()),
            ]
            bash_cmd = [" ".join(create_skeleton_cmd)]
            cmd = ["/bin/bash", "-c", " && ".join(bash_cmd)]
            try:
                self.executor.run(cmd)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to create repository skeleton."
                raise PublishError(msg) from e

            for spec in self.parameters["spec"]:
                # spec file basename will be used as prefix for some artifacts
                spec_bn = os.path.basename(spec).replace(".spec", "")

                # Read information from build stage
                with open(build_artifacts_dir / f"{spec_bn}_build_info.yml") as f:
                    build_info = yaml.safe_load(f.read())

                if not build_info.get("rpms", []) and not build_info.get("srpm", None):
                    log.info(f"{self.component}:{self.dist}:{spec}: Nothing to publish.")
                    continue

                packages_list = [build_artifacts_dir / "rpm" / rpm for rpm in build_info["rpms"]]
                packages_list += [prep_artifacts_dir / build_info["srpm"]]

                # We check that signature exists (--check-only option)
                log.info(f"{self.component}:{self.dist}:{spec}: Verifying signatures.")
                try:
                    for rpm in packages_list:
                        bash_cmd = [
                            f"{self.plugins_dir}/sign_rpm/scripts/sign-rpm "
                            f"--sign-key {sign_key} --db-path {db_path} --rpm {rpm} --check-only"
                        ]
                        cmd = ["/bin/bash", "-c", " && ".join(bash_cmd)]
                        self.executor.run(cmd)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to check signatures."
                    raise PublishError(msg) from e

                # Publish packages with hardlinks to built RPMs
                log.info(f"{self.component}:{self.dist}:{spec}: Publishing RPMs.")
                target_dir = artifacts_dir / f"{self.qubes_release}/{publish_repository}/{self.dist.package_set}/{self.dist.name}"
                try:
                    for rpm in packages_list:
                        target_path = target_dir / "rpm" / rpm.name
                        target_path.unlink(missing_ok=True)
                        # target_path.hardlink_to(rpm)
                        os.link(rpm, target_path)
                except (ValueError, PermissionError, NotImplementedError) as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to publish packages."
                    raise PublishError(msg) from e

                # Createrepo published RPMs
                log.info(f"{self.component}:{self.dist}:{spec}: Updating metadata.")
                bash_cmd = [f"cd {target_dir}", "createrepo_c -g comps.xml ."]
                try:
                    shutil.rmtree(target_dir / "repodata")
                    cmd = ["/bin/bash", "-c", " && ".join(bash_cmd)]
                    self.executor.run(cmd)
                except (ExecutorError, OSError) as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to 'createrepo_c'"
                    raise PublishError(msg) from e

                # Sign metadata
                log.info(f"{self.component}:{self.dist}:{spec}: Signing metadata.")
                repomd = target_dir / 'repodata/repomd.xml'
                bash_cmd = [
                    f"{self.gpg_client} --detach-sign --armor -u {sign_key} {repomd} > {repomd}.asc"
                ]
                try:
                    cmd = ["/bin/bash", "-c", " && ".join(bash_cmd)]
                    self.executor.run(cmd)
                except (ExecutorError, OSError) as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to 'createrepo_c'"
                    raise PublishError(msg) from e
