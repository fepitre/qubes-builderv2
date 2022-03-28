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
from datetime import datetime
from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import RPMDistributionPlugin
from qubesbuilder.plugins.publish import PublishPlugin, PublishError, MIN_AGE_DAYS

log = get_logger("publish_rpm")


class RPMPublishPlugin(PublishPlugin, RPMDistributionPlugin):
    """
    RPMPublishPlugin manages RPM distribution publication.
    """

    plugin_dependencies = ["publish", "sign_rpm"]

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

    def createrepo(self, spec, target_dir):
        log.info(f"{self.component}:{self.dist}:{spec}: Updating metadata.")
        cmd = [f"cd {target_dir}", "createrepo_c -g comps.xml ."]
        try:
            shutil.rmtree(target_dir / "repodata")
            self.executor.run(cmd)
        except (ExecutorError, OSError) as e:
            msg = f"{self.component}:{self.dist}:{spec}: Failed to 'createrepo_c'"
            raise PublishError(msg) from e

    def sign_metadata(self, spec, sign_key, target_dir):
        log.info(f"{self.component}:{self.dist}:{spec}: Signing metadata.")
        repomd = target_dir / "repodata/repomd.xml"
        cmd = [
            f"{self.gpg_client} --batch --no-tty --yes --detach-sign --armor -u {sign_key} {repomd} > {repomd}.asc",
        ]
        try:
            self.executor.run(cmd)
        except (ExecutorError, OSError) as e:
            msg = f"{self.component}:{self.dist}:{spec}:  Failed to sign metadata"
            raise PublishError(msg) from e

    def publish(self, spec, sign_key, db_path, repository_publish):
        # spec file basename will be used as prefix for some artifacts
        spec_bn = spec.with_suffix("").name

        # Read information from build stage
        build_info = self.get_artifacts_info(stage="build", basename=spec_bn)

        if not build_info.get("rpms", []) and not build_info.get("srpm", None):
            log.info(f"{self.component}:{self.dist}:{spec}: Nothing to publish.")
            return

        # Publish packages with hardlinks to built RPMs
        log.info(
            f"{self.component}:{self.dist}:{spec}: Publishing RPMs to '{repository_publish}'."
        )

        # Source artifacts
        prep_artifacts_dir = self.get_dist_component_artifacts_dir(stage="prep")
        # Build artifacts
        build_artifacts_dir = self.get_dist_component_artifacts_dir(stage="build")
        # Publish repository
        artifacts_dir = self.get_repository_publish_dir() / self.dist.type

        packages_list = [
            build_artifacts_dir / "rpm" / rpm for rpm in build_info["rpms"]
        ]
        packages_list += [prep_artifacts_dir / build_info["srpm"]]

        # We check that signature exists (--check-only option)
        log.info(f"{self.component}:{self.dist}:{spec}: Verifying signatures.")
        try:
            for rpm in packages_list:
                cmd = [
                    f"{self.plugins_dir}/sign_rpm/scripts/sign-rpm "
                    f"--sign-key {sign_key} --db-path {db_path} --rpm {rpm} --check-only"
                ]
                self.executor.run(cmd)
        except ExecutorError as e:
            msg = f"{self.component}:{self.dist}:{spec}: Failed to check signatures."
            raise PublishError(msg) from e

        target_dir = (
            artifacts_dir
            / f"{self.qubes_release}/{repository_publish}/{self.dist.package_set}/{self.dist.name}"
        )
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
        self.createrepo(spec=spec, target_dir=target_dir)

        # Sign metadata
        self.sign_metadata(spec=spec, sign_key=sign_key, target_dir=target_dir)

    def unpublish(self, spec, sign_key, repository_publish):
        # spec file basename will be used as prefix for some artifacts
        spec_bn = os.path.basename(spec).replace(".spec", "")
        # Read information from build stage
        build_info = self.get_artifacts_info(stage="build", basename=spec_bn)

        if not build_info.get("rpms", []) and not build_info.get("srpm", None):
            log.info(f"{self.component}:{self.dist}:{spec}: Nothing to unpublish.")
            return

        log.info(
            f"{self.component}:{self.dist}:{spec}: Unpublishing RPMs from '{repository_publish}'."
        )

        # Source artifacts
        prep_artifacts_dir = self.get_dist_component_artifacts_dir(stage="prep")
        # Build artifacts
        build_artifacts_dir = self.get_dist_component_artifacts_dir(stage="build")

        packages_list = [
            build_artifacts_dir / "rpm" / rpm for rpm in build_info["rpms"]
        ]
        packages_list += [prep_artifacts_dir / build_info["srpm"]]

        # If exists, remove hardlinks to built RPMs
        artifacts_dir = self.get_repository_publish_dir() / self.dist.type
        target_dir = (
            artifacts_dir
            / f"{self.qubes_release}/{repository_publish}/{self.dist.package_set}/{self.dist.name}"
        )
        try:
            for rpm in packages_list:
                target_path = target_dir / "rpm" / rpm.name
                target_path.unlink(missing_ok=True)
        except (ValueError, PermissionError, NotImplementedError) as e:
            msg = f"{self.component}:{self.dist}:{spec}: Failed to unpublish packages."
            raise PublishError(msg) from e

        # Createrepo unpublished RPMs
        self.createrepo(spec=spec, target_dir=target_dir)

        # Sign metadata
        self.sign_metadata(spec=spec, sign_key=sign_key, target_dir=target_dir)

    def run(
        self,
        stage: str,
        repository_publish: str = None,
        ignore_min_age: bool = False,
        unpublish: bool = False,
        **kwargs,
    ):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        # Check if we have RPM related content defined
        if not self.parameters.get("spec", []):
            log.info(f"{self.component}:{self.dist}: Nothing to be done.")
            return

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

        # FIXME: Refactor the code handling both standard and template components.
        #  It applies for other plugins.

        repository_publish = repository_publish or self.repository_publish.get(
            "components", "current-testing"
        )

        # Publish stage for standard (not template) components
        if stage == "publish" and not unpublish:
            # Sign artifacts
            sign_artifacts_dir = self.get_dist_component_artifacts_dir(stage="sign")

            # repository-publish directory
            artifacts_dir = self.get_repository_publish_dir() / self.dist.type

            # Ensure dbpath from sign stage (still) exists
            db_path = sign_artifacts_dir / "rpmdb"
            if not db_path.exists():
                msg = f"{self.component}: {self.dist}: Failed to find RPM DB path."
                raise PublishError(msg)

            # Create publish repository skeleton
            comps = (
                self.plugins_dir
                / f"publish_rpm/comps/comps-{self.dist.package_set}.xml"
            )
            create_skeleton_cmd = [
                f"{self.plugins_dir}/publish_rpm/scripts/create-skeleton",
                self.qubes_release,
                self.dist.package_set,
                self.dist.name,
                str(artifacts_dir.absolute()),
                str(comps.absolute()),
            ]
            cmd = [" ".join(create_skeleton_cmd)]
            try:
                self.executor.run(cmd)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to create repository skeleton."
                raise PublishError(msg) from e

            # Check if publish repository is valid
            self.validate_repository_publish(repository_publish)

            # Check if we already published packages into the provided repository
            if all(
                self.is_published(
                    basename=spec.with_suffix("").name, repository=repository_publish
                )
                for spec in self.parameters["spec"]
            ):
                log.info(
                    f"{self.component}:{self.dist}: Already published to '{repository_publish}'."
                )
                return

            # Check if we can publish into current
            if repository_publish == "current" and not all(
                self.can_be_published_in_stable(
                    basename=spec.with_suffix("").name, ignore_min_age=ignore_min_age
                )
                for spec in self.parameters["spec"]
            ):
                failure_msg = (
                    f"{self.component}:{self.dist}: "
                    f"Refusing to publish to 'current' as packages are not "
                    f"uploaded to 'current-testing' or 'security-testing' "
                    f"for at least {MIN_AGE_DAYS} days."
                )
                raise PublishError(failure_msg)

            for spec in self.parameters["spec"]:
                spec_bn = spec.with_suffix("").name
                build_info = self.get_artifacts_info(stage="build", basename=spec_bn)
                publish_info = self.get_artifacts_info(stage=stage, basename=spec_bn)

                # If previous publication to a repo has been done and does not correspond to current
                # build artifacts, we delete previous publications. It happens if we modify local
                # sources and then publish into repository with the same version and release.
                info = build_info
                if publish_info:
                    if build_info["source-hash"] != publish_info["source-hash"]:
                        for repository in publish_info.get("repository-publish", []):
                            self.unpublish(
                                spec=spec,
                                sign_key=sign_key,
                                repository_publish=repository,
                            )
                    else:
                        info = publish_info

                self.publish(
                    spec=spec,
                    sign_key=sign_key,
                    db_path=db_path,
                    repository_publish=repository_publish,
                )

                # Save package information we published for committing into current
                info.setdefault("repository-publish", []).append(
                    {
                        "name": repository_publish,
                        "timestamp": datetime.utcnow().strftime("%Y%m%d%H%MZ"),
                    }
                )
                self.save_artifacts_info(stage="publish", basename=spec_bn, info=info)

        if stage == "publish" and unpublish:
            if not all(
                self.is_published(
                    basename=spec.with_suffix("").name, repository=repository_publish
                )
                for spec in self.parameters["spec"]
            ):
                log.info(
                    f"{self.component}:{self.dist}: Not published to '{repository_publish}'."
                )
                return

            for spec in self.parameters["spec"]:
                spec_bn = spec.with_suffix("").name
                publish_info = self.get_artifacts_info(stage=stage, basename=spec_bn)

                self.unpublish(
                    spec=spec,
                    sign_key=sign_key,
                    repository_publish=repository_publish,
                )

                # Save package information we published for committing into current. If the packages
                # are not published into another repository, we delete the publish stage information.
                publish_info["repository-publish"] = [
                    r
                    for r in publish_info.get("repository-publish", [])
                    if r["name"] != repository_publish
                ]
                if publish_info.get("repository-publish", []):
                    self.save_artifacts_info(
                        stage="publish", basename=spec_bn, info=publish_info
                    )
                else:
                    log.info(
                        f"{self.component}:{self.dist}:{spec_bn}: Not published anywhere else, deleting publish info."
                    )
                    self.delete_artifacts_info(stage="publish", basename=spec_bn)
