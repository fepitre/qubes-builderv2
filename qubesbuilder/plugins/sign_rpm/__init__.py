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
from qubesbuilder.plugins.build import BuildError
from qubesbuilder.plugins.build_rpm import provision_local_repository
from qubesbuilder.plugins.sign import SignPlugin, SignError

log = get_logger("sign_rpm")


class RPMSignPlugin(SignPlugin):
    """
    RPMSignPlugin manages RPM distribution sign.
    """

    plugin_dependencies = ["sign"]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        gpg_client: str,
        sign_key: dict,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(
            component=component,
            dist=dist,
            plugins_dir=plugins_dir,
            executor=executor,
            artifacts_dir=artifacts_dir,
            gpg_client=gpg_client,
            sign_key=sign_key,
            verbose=verbose,
            debug=debug,
        )

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        super().update_parameters()

        # Per distribution (e.g. host-fc42) overrides per package set (e.g. host)
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get(self.dist.package_set, {}).get("rpm", {}))
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("rpm", {})
        )

    def run(self, stage: str):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        # Update parameters
        self.update_parameters()

        # Check if we have a signing key provided
        sign_key = self.sign_key.get(self.dist.distribution, None) or self.sign_key.get(
            "rpm", None
        )
        if not sign_key:
            log.info(f"{self.component}:{self.dist}: No signing key found.")
            return

        # Check if we have a gpg client provided
        if not self.gpg_client:
            log.info(f"{self.component}: Please specify GPG client to use!")
            return

        # Sign stage for standard components
        if stage == "sign":
            # Check if we have RPM related content defined
            if not self.parameters.get("spec", []):
                log.info(f"{self.component}:{self.dist}: Nothing to be done.")
                return

            # Source artifacts
            prep_artifacts_dir = self.get_component_dir(stage="prep")
            # Build artifacts
            build_artifacts_dir = self.get_component_dir(stage="build")
            # Sign artifacts
            artifacts_dir = self.get_component_dir(stage)

            # We ensure to create a clean keyring for RPM
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir)
            db_path = artifacts_dir / "rpmdb"
            sign_key_asc = artifacts_dir / f"{sign_key}.asc"
            cmd = [
                f"mkdir -p {db_path}",
                f"{self.gpg_client} --armor --export {sign_key} > {sign_key_asc}",
                f"rpmkeys --dbpath={db_path} --import {sign_key_asc}",
            ]
            try:
                self.executor.run(cmd)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to create RPM dbpath."
                raise SignError(msg) from e

            for spec in self.parameters["spec"]:
                # spec file basename will be used as prefix for some artifacts
                spec_bn = os.path.basename(spec).replace(".spec", "")

                # Read information from build stage
                with open(build_artifacts_dir / f"{spec_bn}_build_info.yml") as f:
                    build_info = yaml.safe_load(f.read())

                if not build_info.get("rpms", []) and not build_info.get("srpm", None):
                    log.info(f"{self.component}:{self.dist}:{spec}: Nothing to sign.")
                    continue

                packages_list = [
                    build_artifacts_dir / "rpm" / rpm for rpm in build_info["rpms"]
                ]
                packages_list += [prep_artifacts_dir / build_info["srpm"]]

                try:
                    for rpm in packages_list:
                        log.info(
                            f"{self.component}:{self.dist}:{spec}: Signing '{rpm.name}'."
                        )
                        cmd = [
                            f"{self.plugins_dir}/sign_rpm/scripts/sign-rpm "
                            f"--sign-key {sign_key} --db-path {db_path} --rpm {rpm}"
                        ]

                        self.executor.run(cmd)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to sign RPMs."
                    raise SignError(msg) from e

                # Re-provision builder local repository with signatures
                repository_dir = self.get_repository_dir() / self.dist.distribution
                try:
                    provision_local_repository(
                        spec=spec,
                        component=self.component,
                        dist=self.dist,
                        repository_dir=repository_dir,
                        source_info=build_info,
                        packages_list=build_info["rpms"],
                        prep_artifacts_dir=prep_artifacts_dir,
                        build_artifacts_dir=build_artifacts_dir,
                    )
                except BuildError as e:
                    raise SignError from e
