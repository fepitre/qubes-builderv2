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

import os.path
import shutil
from pathlib import Path
from typing import List

import yaml

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import BUILDER_DIR, BUILD_DIR, PLUGINS_DIR, REPOSITORY_DIR
from qubesbuilder.plugins.build import BuildPlugin, BuildError

log = get_logger("build_rpm")


def provision_local_repository(
    spec: str,
    repository_dir: Path,
    component: QubesComponent,
    dist: QubesDistribution,
    source_info: dict,
    packages_list: List,
    prep_artifacts_dir: Path,
    build_artifacts_dir: Path,
):
    """
    Provision local builder repository.
    """
    log.info(
        f"{component}:{dist}:{spec}: Provisioning local repository '{repository_dir}'."
    )

    # Create target directory that will have hardlinks to SRPM and built RPMs
    target_dir = repository_dir / f"{component.name}-{component.version}"
    if target_dir.exists():
        shutil.rmtree(target_dir.as_posix())
    target_dir.mkdir(parents=True)

    try:
        # srpm
        srpm_path = prep_artifacts_dir / source_info["srpm"]
        target_path = target_dir / source_info["srpm"]
        # target_path.hardlink_to(srpm_path)
        os.link(srpm_path, target_path)

        # rpms
        for rpm in packages_list:
            rpm_path = build_artifacts_dir / "rpm" / rpm
            target_path = target_dir / rpm
            # target_path.hardlink_to(rpm_path)
            os.link(rpm_path, target_path)
    except (ValueError, PermissionError, NotImplementedError) as e:
        msg = f"{component}:{dist}:{spec}: Failed to provision local repository."
        raise BuildError(msg) from e


class RPMBuildPlugin(BuildPlugin):
    """
    Manage RPM distribution build.
    """

    plugin_dependencies = ["source_rpm", "build"]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool = False,
        debug: bool = False,
        use_qubes_repo: dict = None,
    ):
        super().__init__(
            component=component,
            dist=dist,
            executor=executor,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
            use_qubes_repo=use_qubes_repo,
        )

        # Add some environment variables needed to render mock root configuration
        # FIXME: host is aliased as "dom0" for legacy
        self.environment.update(
            {
                "DIST": self.dist.name,
                "PACKAGE_SET": self.dist.package_set.replace("host", "dom0"),
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

        if stage == "build":
            # Update parameters
            self.update_parameters()

            # Check if we have RPM related content defined
            if not self.parameters.get("spec", []):
                log.info(f"{self.component}:{self.dist}: Nothing to be done.")
                return

            distfiles_dir = self.get_distfiles_dir()
            artifacts_dir = self.get_component_dir(stage)
            rpms_dir = artifacts_dir / "rpm"

            # Clean previous build artifacts
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir.as_posix())
            rpms_dir.mkdir(parents=True)

            # Source artifacts
            prep_artifacts_dir = self.get_component_dir(stage="prep")

            # Local build repository
            repository_dir = self.get_repository_dir() / self.dist.distribution
            repository_dir.mkdir(parents=True, exist_ok=True)

            # Remove previous versions in order to keep latest one only
            for build in repository_dir.glob(f"{self.component.name}-*"):
                shutil.rmtree(build.as_posix())

            for spec in self.parameters["spec"]:
                # spec file basename will be used as prefix for some artifacts
                spec_bn = os.path.basename(spec).replace(".spec", "")

                # Read information from source stage
                try:
                    with open(prep_artifacts_dir / f"{spec_bn}_source_info.yml") as f:
                        source_info = yaml.safe_load(f.read())
                except (FileNotFoundError, PermissionError) as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to read source info."
                    raise BuildError(msg) from e

                #
                # Build from SRPM
                #

                # Copy-in distfiles, content and source RPM
                copy_in = [
                    (distfiles_dir, BUILDER_DIR),
                    (self.plugins_dir / "build_rpm", PLUGINS_DIR),
                    (repository_dir, REPOSITORY_DIR),
                    (prep_artifacts_dir / source_info["srpm"], BUILD_DIR),
                ] + [
                    (self.plugins_dir / plugin, PLUGINS_DIR)
                    for plugin in self.plugin_dependencies
                ]

                copy_out = [
                    (BUILD_DIR / "rpm" / rpm, rpms_dir) for rpm in source_info["rpms"]
                ]

                # Createrepo of local builder repository and ensure 'mock' group can access
                # build directory
                cmd = [
                    f"cd {REPOSITORY_DIR}",
                    "createrepo_c .",
                    f"sudo chown -R user:mock {BUILD_DIR}",
                ]

                # Run 'mock' to build source RPM
                # On Fedora /usr/bin/mock is a (consolehelper) wrapper,
                # which among other things, strips environment variables"
                mock_conf = f"{self.dist.fullname}-{self.dist.version}-{self.dist.architecture}.cfg"
                mock_cmd = [
                    f"sudo --preserve-env=DIST,PACKAGE_SET,USE_QUBES_REPO_VERSION",
                    f"/usr/libexec/mock/mock",
                    f"--rebuild {BUILD_DIR / source_info['srpm']}",
                    f"--root /builder/plugins/source_rpm/mock/{mock_conf}",
                    f"--resultdir={BUILD_DIR}",
                ]
                if self.verbose:
                    mock_cmd.append("--verbose")
                if self.use_qubes_repo and self.use_qubes_repo.get("version"):
                    mock_cmd.append("--enablerepo=qubes-current")
                if self.use_qubes_repo and self.use_qubes_repo.get("testing"):
                    mock_cmd.append("--enablerepo=qubes-current-testing")
                cmd += [" ".join(mock_cmd)]

                # Move RPMs into a separate dir and generate packages list
                cmd += [
                    f"{PLUGINS_DIR}/build_rpm/scripts/filter-packages-by-dist-arch "
                    f"{BUILD_DIR} {BUILD_DIR}/rpm {self.dist.tag} {self.dist.architecture}"
                ]
                try:
                    self.executor.run(
                        cmd,
                        copy_in,
                        copy_out,
                        environment=self.environment,
                        no_fail_copy_out=True,
                    )
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to build RPMs: {str(e)}."
                    raise BuildError(msg) from e

                # Get packages list that have been actually built from predicted ones
                packages_list = []
                for rpm in source_info["rpms"]:
                    if os.path.exists(rpms_dir / rpm):
                        packages_list.append(rpm)

                # Provision builder local repository
                provision_local_repository(
                    spec=spec,
                    component=self.component,
                    dist=self.dist,
                    repository_dir=repository_dir,
                    source_info=source_info,
                    packages_list=packages_list,
                    prep_artifacts_dir=prep_artifacts_dir,
                    build_artifacts_dir=artifacts_dir,
                )

                # Save package information we parsed for next stages
                try:
                    with open(artifacts_dir / f"{spec_bn}_build_info.yml", "w") as f:
                        info = {"srpm": source_info["srpm"], "rpms": packages_list}
                        f.write(yaml.safe_dump(info))
                except (PermissionError, yaml.YAMLError) as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to write build info."
                    raise BuildError(msg) from e
