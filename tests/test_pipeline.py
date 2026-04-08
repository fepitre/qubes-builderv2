# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2026 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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

# Tests for pipeline structure and fetch-triggering behavior (issue #10522).
# upload/sign/publish must not trigger fetch even without local sources.
# fetch only runs when explicitly requested or needed by prep/build.

import subprocess

import pytest
import yaml

from qubesbuilder.common import PROJECT_PATH
from tests.conftest import artifacts_dir_single  # noqa: F401

DEFAULT_BUILDER_CONF = PROJECT_PATH / "tests/builder-ci.yml"

# upload/publish are dist-level (always instantiated); sign/prep are
# component+dist-level (filtered by has_component_packages when sources absent).
COMPONENT = "core-qrexec"
DISTRIBUTION = "host-fc37"


def qb_call(*args, artifacts_dir, check=True, capture_output=False):
    cmd = [
        "python3",
        str(PROJECT_PATH / "qb"),
        "--builder-conf",
        str(DEFAULT_BUILDER_CONF),
        "--option",
        f"artifacts-dir={artifacts_dir}",
        *args,
    ]
    if capture_output:
        try:
            return subprocess.check_output(
                cmd, stderr=subprocess.DEVNULL
            ).decode()
        except subprocess.CalledProcessError as e:
            pytest.fail(
                f"Command failed:\n{' '.join(e.cmd)}\nReturn code: {e.returncode}"
            )
    else:
        try:
            return subprocess.run(cmd, check=check).returncode
        except subprocess.CalledProcessError as e:
            pytest.fail(
                f"Command failed:\n{' '.join(e.cmd)}\nReturn code: {e.returncode}"
            )


def _pipeline_stages(artifacts_dir, *stages):
    """
    Return the set of stage names present in the pipeline YAML output.
    """
    raw = qb_call(
        "-c",
        COMPONENT,
        "-d",
        DISTRIBUTION,
        "package",
        "pipeline",
        "--format",
        "yaml",
        *stages,
        artifacts_dir=artifacts_dir,
        capture_output=True,
    )
    jobs = yaml.safe_load(raw) or []
    return {j["stage"] for j in jobs}


# Pipeline structure tests


def test_pipeline_upload_excludes_fetch(artifacts_dir_single):
    stages = _pipeline_stages(artifacts_dir_single, "upload")
    assert (
        "fetch" not in stages
    ), f"unexpected fetch in upload pipeline: {stages}"
    assert "upload" in stages
    assert "publish" in stages


def test_pipeline_publish_excludes_fetch(artifacts_dir_single):
    stages = _pipeline_stages(artifacts_dir_single, "publish")
    assert (
        "fetch" not in stages
    ), f"unexpected fetch in publish pipeline: {stages}"
    assert "publish" in stages


def test_pipeline_sign_excludes_fetch(artifacts_dir_single):
    stages = _pipeline_stages(artifacts_dir_single, "sign")
    assert "fetch" not in stages, f"unexpected fetch in sign pipeline: {stages}"


def test_pipeline_init_cache_excludes_fetch(artifacts_dir_single):
    raw = qb_call(
        "-d",
        DISTRIBUTION,
        "package",
        "pipeline",
        "--format",
        "yaml",
        "init-cache",
        artifacts_dir=artifacts_dir_single,
        capture_output=True,
    )
    jobs = yaml.safe_load(raw) or []
    stages = {j["stage"] for j in jobs}
    assert (
        "fetch" not in stages
    ), f"unexpected fetch in init-cache pipeline: {stages}"
    assert "init-cache" in stages


def test_pipeline_fetch_prep_includes_fetch(artifacts_dir_single):
    stages = _pipeline_stages(artifacts_dir_single, "fetch", "prep")
    assert (
        "fetch" in stages
    ), f"fetch missing from fetch+prep pipeline: {stages}"


def test_pipeline_upload_ordering(artifacts_dir_single):
    raw = qb_call(
        "-c",
        COMPONENT,
        "-d",
        DISTRIBUTION,
        "package",
        "pipeline",
        "--format",
        "yaml",
        "upload",
        artifacts_dir=artifacts_dir_single,
        capture_output=True,
    )
    jobs = yaml.safe_load(raw) or []
    stage_order = [j["stage"] for j in jobs]
    assert stage_order.index("publish") < stage_order.index("upload")


# Behavior tests: stages that don't need sources must not trigger fetch


def test_upload_without_sources_succeeds(artifacts_dir_single):
    qb_call(
        "-c",
        COMPONENT,
        "-d",
        DISTRIBUTION,
        "package",
        "upload",
        artifacts_dir=artifacts_dir_single,
    )


def test_sign_without_sources_succeeds(artifacts_dir_single):
    qb_call(
        "-c",
        COMPONENT,
        "-d",
        DISTRIBUTION,
        "package",
        "sign",
        artifacts_dir=artifacts_dir_single,
    )


def test_publish_without_sources_succeeds(artifacts_dir_single):
    qb_call(
        "-c",
        COMPONENT,
        "-d",
        DISTRIBUTION,
        "package",
        "publish",
        artifacts_dir=artifacts_dir_single,
    )
