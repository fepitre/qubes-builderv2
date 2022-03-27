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
import datetime
import os
from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.publish import PublishPlugin, PublishError, MIN_AGE_DAYS

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
        repository_publish: dict,
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
            repository_publish=repository_publish,
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

    def run(
        self, stage: str, repository_publish: str = None, ignore_min_age: bool = False
    ):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        # Update parameters
        self.update_parameters()

        # Check if we have Debian related content defined
        if not self.parameters.get("build", []):
            log.info(f"{self.component}:{self.dist}: Nothing to be done.")
            return

        if stage == "publish":
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
            build_artifacts_dir = self.get_dist_component_artifacts_dir(stage="build")
            # Sign artifacts
            sign_artifacts_dir = self.get_dist_component_artifacts_dir(stage="sign")
            keyring_dir = sign_artifacts_dir / "keyring"
            # Publish artifacts
            publish_artifacts_dir = self.get_dist_component_artifacts_dir(
                stage="publish"
            )
            # repository-publish directory
            artifacts_dir = self.get_repository_publish_dir() / self.dist.type

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

            # Check if publish repository is valid
            if not repository_publish:
                repository_publish = self.repository_publish.get(
                    "components", "current-testing"
                )
            if repository_publish not in (
                "current",
                "current-testing",
                "security-testing",
                "unstable",
            ):
                msg = (
                    f"{self.component}:{self.dist}: "
                    f"Refusing to publish components into '{repository_publish}'."
                )
                raise PublishError(msg)

            if repository_publish == "current":
                nothing_to_publish = False
                # If publish repository is 'current' we check that all packages provided by all
                # build directories are published in testing repositories first.
                for directory in self.parameters["build"]:
                    failure_msg = (
                        f"{self.component}:{self.dist}:{directory}: "
                        f"Refusing to publish to 'current' as packages are not "
                        f"uploaded to 'current-testing' or 'security-testing' "
                        f"for at least {MIN_AGE_DAYS} days."
                    )
                    # Check packages are published
                    publish_info = self.get_artifacts_info(
                        stage=stage, basename=directory
                    )
                    if not publish_info:
                        raise PublishError(failure_msg)

                    # Check for valid repositories under which packages are published
                    if publish_info.get("repository-publish", None) not in (
                        "security-testing",
                        "current-testing",
                        "current",
                    ):
                        raise PublishError(failure_msg)
                    # If publish repository is 'current' we check the next spec file
                    if publish_info["repository-publish"] == "current":
                        log.info(
                            f"{self.component}:{self.dist}:{directory}: "
                            f"Already published to 'current'."
                        )
                        nothing_to_publish = True
                        continue
                    # Check minimum day that packages are available for testing
                    publish_date = datetime.datetime.utcfromtimestamp(
                        os.stat(
                            publish_artifacts_dir / f"{directory}.publish.yml"
                        ).st_mtime
                    )
                    # Check that packages have been published before threshold_date
                    threshold_date = datetime.datetime.utcnow() - datetime.timedelta(
                        days=MIN_AGE_DAYS
                    )
                    if not ignore_min_age and publish_date > threshold_date:
                        raise PublishError(failure_msg)

                if nothing_to_publish:
                    log.info(
                        f"{self.component}:{self.dist}: Already published to '{repository_publish}'."
                    )
                    return

            for directory in self.parameters["build"]:
                # Read information from build stage
                build_info = self.get_artifacts_info(stage="build", basename=directory)

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
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to check signatures."
                    raise PublishError(msg) from e

                # Publishing packages
                try:
                    log.info(
                        f"{self.component}:{self.dist}:{directory}: Publishing packages."
                    )
                    changes_file = build_artifacts_dir / build_info["changes"]
                    target_dir = (
                        artifacts_dir / f"{self.qubes_release}/{self.dist.package_set}"
                    )

                    # reprepro options to ignore surprising binary and arch
                    reprepro_options = f"--ignore=surprisingbinary --ignore=surprisingarch -b {target_dir}"

                    # set debian suite according to publish repository
                    debian_suite = self.dist.name
                    if repository_publish == "current-testing":
                        debian_suite += "-testing"
                    elif repository_publish == "security-testing":
                        debian_suite += "-securitytesting"
                    elif repository_publish == "unstable":
                        debian_suite += "-unstable"

                    # reprepro command
                    cmd = [
                        f"reprepro {reprepro_options} include {debian_suite} {changes_file}"
                    ]
                    self.executor.run(cmd)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to publish packages."
                    raise PublishError(msg) from e

                # Save package information we published for committing into current
                info = build_info
                info["repository-publish"] = repository_publish
                self.save_artifacts_info(stage=stage, basename=directory, info=info)
