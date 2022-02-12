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

import shutil
from pathlib import Path

import yaml

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.build import BuildError
from qubesbuilder.plugins.build_deb import provision_local_repository
from qubesbuilder.plugins.sign import SignPlugin, SignError

log = get_logger("sign_deb")


class DEBSignPlugin(SignPlugin):
    """
    DEBSignPlugin manages DEB distribution sign.
    """

    plugin_dependencies = ["sign", "build_deb"]

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

        if stage == "sign":
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

            # Build artifacts (source included)
            build_artifacts_dir = self.get_component_dir(stage="build")
            # Sign artifacts
            artifacts_dir = self.get_component_dir(stage)

            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir)
            artifacts_dir.mkdir(parents=True)

            keyring_dir = artifacts_dir / "keyring"
            keyring_dir.mkdir(mode=0o700)

            # Export public key and generate local keyring
            sign_key_asc = artifacts_dir / f"{sign_key}.asc"
            cmd = [
                f"{self.gpg_client} --armor --export {sign_key} > {sign_key_asc}",
                f"gpg2 --homedir {keyring_dir} --import {sign_key_asc}",
            ]
            try:
                self.executor.run(cmd)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to export public signing key."
                raise SignError(msg) from e

            for directory in self.parameters["build"]:
                # Read information from build stage
                with open(build_artifacts_dir / f"{directory}_build_info.yml") as f:
                    build_info = yaml.safe_load(f.read())

                if not build_info.get("changes", None):
                    log.info(
                        f"{self.component}:{self.dist}:{directory}: Nothing to sign."
                    )
                    continue
                try:
                    log.info(
                        f"{self.component}:{self.dist}:{directory}: Signing from '{build_info['changes']}' info."
                    )
                    cmd = [
                        f"debsign -k{sign_key} -p{self.gpg_client} --no-re-sign {build_artifacts_dir / build_info['changes']}"
                    ]
                    self.executor.run(cmd)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to sign Debian packages."
                    raise SignError(msg) from e

                # Re-provision builder local repository with signatures
                repository_dir = self.get_repository_dir() / self.dist.distribution
                try:
                    # We use build_info that contains source_info and build_artifacts_dir
                    # which contains sources files.
                    provision_local_repository(
                        debian_directory=directory,
                        component=self.component,
                        dist=self.dist,
                        repository_dir=repository_dir,
                        source_info=build_info,
                        packages_list=build_info["packages"],
                        build_artifacts_dir=build_artifacts_dir,
                    )
                except BuildError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to re-provision local repository."
                    raise SignError(msg) from e
