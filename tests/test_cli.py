import itertools
import os.path
import pathlib
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta

import dnf
import pytest
import yaml
from dateutil.parser import parse as parsedate

from qubesbuilder.common import PROJECT_PATH

DEFAULT_BUILDER_CONF = PROJECT_PATH / "tests/builder-ci.yml"
HASH_RE = re.compile("[a-f0-9]{40}")


@pytest.fixture(scope="session")
def artifacts_dir(tmpdir_factory):
    if os.environ.get("ARTIFACTS_DIR"):
        artifacts_dir = pathlib.Path(os.environ.get("ARTIFACTS_DIR"))
    else:
        tmpdir = tmpdir_factory.mktemp("github-")
        artifacts_dir = tmpdir / "artifacts"
    if not artifacts_dir.exists():
        artifacts_dir.mkdir()
    yield artifacts_dir


def qb_call(builder_conf, artifacts_dir, *args, **kwargs):
    cmd = [
        str(PROJECT_PATH / "qb"),
        "--verbose",
        "--builder-conf",
        str(builder_conf),
        "--option",
        f"artifacts-dir={artifacts_dir}",
        *args,
    ]
    subprocess.check_call(cmd, **kwargs)


def qb_call_output(builder_conf, artifacts_dir, *args, **kwargs):
    cmd = [
        str(PROJECT_PATH / "qb"),
        "--verbose",
        "--builder-conf",
        str(builder_conf),
        "--option",
        f"artifacts-dir={artifacts_dir}",
        *args,
    ]
    return subprocess.check_output(cmd, **kwargs)


def deb_packages_list(repository_dir, suite, **kwargs):
    return (
        subprocess.check_output(
            ["reprepro", "-b", repository_dir, "list", suite],
            **kwargs,
        )
        .decode()
        .splitlines()
    )


def rpm_packages_list(repository_dir):
    with tempfile.TemporaryDirectory() as tmpdir:
        base = dnf.Base()
        base.conf.installroot = tmpdir
        base.conf.cachedir = tmpdir + "/cache"
        base.repos.add_new_repo(
            repoid="local", conf=base.conf, baseurl=[repository_dir]
        )
        base.fill_sack()
        q = base.sack.query()
        return [str(p) + ".rpm" for p in q.available()]


#
# config
#


def test_config(artifacts_dir):
    with tempfile.TemporaryDirectory() as tmpdir:
        include_path = os.path.join(tmpdir, "include1.yml")
        with open(include_path, "w") as f:
            f.write("+components:\n")
            f.write("- component2\n")
            f.write("- component3\n")
            f.write("distributions:\n")
            f.write("- vm-fc36\n")
            f.write("- vm-fc37\n")
        include_path = os.path.join(tmpdir, "include-nested.yml")
        with open(include_path, "w") as f:
            f.write("+components:\n")
            f.write("- component4\n")
            f.write("- component5\n")
            f.write("debug: true\n")
        include_path = os.path.join(tmpdir, "include2.yml")
        with open(include_path, "w") as f:
            f.write("include:\n")
            f.write("- include-nested.yml\n")
            f.write("+components:\n")
            f.write("- component6\n")
            f.write("- component7\n")
            f.write("distributions:\n")
            f.write("- vm-fc36\n")
            f.write("- vm-fc37\n")
        config_path = os.path.join(tmpdir, "builder.yml")
        with open(config_path, "w") as f:
            f.write("include:\n")
            f.write("- include1.yml\n")
            f.write("- include2.yml\n")
            f.write("components:\n")
            f.write("- component1\n")
            f.write("- component2\n")
            f.write("distributions:\n")
            f.write("- vm-fc33\n")
            f.write("- vm-fc34\n")

        output = qb_call_output(config_path, artifacts_dir, "config", "get-components")
        assert (
            output == b"component1\ncomponent2\ncomponent3\ncomponent4\n"
            b"component5\ncomponent6\ncomponent7\n"
        )

        output = qb_call_output(
            config_path, artifacts_dir, "config", "get-distributions"
        )
        assert output == b"vm-fc33\nvm-fc34\n"

        output = qb_call_output(
            config_path, artifacts_dir, "config", "get-var", "debug"
        )
        assert output == b"true\n"


#
# Init cache
#


def test_component_init_cache(artifacts_dir):
    qb_call(DEFAULT_BUILDER_CONF, artifacts_dir, "package", "init-cache")

    assert (artifacts_dir / "cache/chroot/fc32/mock/fedora-32-x86_64").exists()
    assert (artifacts_dir / "cache/chroot/bullseye/pbuilder/base.tgz").exists()
    assert (artifacts_dir / "cache/chroot/fc36/mock/fedora-36-x86_64").exists()


#
# Fetch
#


def test_component_fetch(artifacts_dir):
    qb_call(DEFAULT_BUILDER_CONF, artifacts_dir, "package", "fetch")

    assert (artifacts_dir / "distfiles/python-qasync/qasync-0.23.0.tar.gz").exists()
    assert (
        artifacts_dir / "distfiles/desktop-linux-xfce4-xfwm4/xfwm4-4.14.2.tar.bz2"
    ).exists()

    for component in [
        "core-qrexec",
        "core-vchan-xen",
        "desktop-linux-xfce4-xfwm4",
        "python-qasync",
    ]:
        assert (artifacts_dir / "sources" / component / ".qubesbuilder").exists()


def test_component_fetch_updating(artifacts_dir):
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "package",
        "fetch",
        stderr=subprocess.STDOUT,
    ).decode()
    for sentence in [
        "python-qasync: source already fetched. Updating.",
        "core-vchan-xen: source already fetched. Updating.",
        "core-qrexec: source already fetched. Updating.",
        "desktop-linux-xfce4-xfwm4: source already fetched. Updating.",
        "python-qasync: file qasync-0.23.0.tar.gz already downloaded. Skipping.",
        "desktop-linux-xfce4-xfwm4: file xfwm4-4.14.2.tar.bz2 already downloaded. Skipping.",
    ]:
        assert sentence in result


def test_component_fetch_increment(artifacts_dir):
    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "--option",
        "increment-devel-versions=true",
        "package",
        "fetch",
    )

    for component in [
        "core-qrexec",
        "core-vchan-xen",
        "desktop-linux-xfce4-xfwm4",
        "python-qasync",
    ]:
        assert (
            artifacts_dir / "components" / component / "noversion" / "devel"
        ).exists()

        (artifacts_dir / "sources" / component / "hello").write_text(
            "world", encoding="utf8"
        )

    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "--option",
        "increment-devel-versions=true",
        "package",
        "fetch",
    )

    for component in [
        "core-qrexec",
        "core-vchan-xen",
        "desktop-linux-xfce4-xfwm4",
        "python-qasync",
    ]:
        assert (
            artifacts_dir / "components" / component / "noversion" / "devel"
        ).read_text(encoding="utf-8") == "2"


#
# Pipeline for core-qrexec and host-fc32
#


def test_component_prep_host_fc32(artifacts_dir):
    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "core-qrexec",
        "-d",
        "host-fc32",
        "package",
        "prep",
    )

    with open(
        artifacts_dir
        / "components/core-qrexec/4.1.18-1/host-fc32/prep/rpm_spec_qubes-qrexec.spec.prep.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debugsource-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-4.1.18-1.fc32.src.rpm"

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm

    with open(
        artifacts_dir
        / "components/core-qrexec/4.1.18-1/host-fc32/prep/rpm_spec_qubes-qrexec-dom0.spec.prep.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm"

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm


def test_component_build_host_fc32(artifacts_dir):
    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "core-qrexec",
        "-d",
        "host-fc32",
        "package",
        "build",
    )

    with open(
        artifacts_dir
        / "components/core-qrexec/4.1.18-1/host-fc32/build/rpm_spec_qubes-qrexec.spec.build.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-4.1.18-1.fc32.src.rpm"

    for rpm in rpms.union({srpm}):
        assert (
            artifacts_dir / "repository/host-fc32/core-qrexec_4.1.18" / rpm
        ).exists()

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm

    with open(
        artifacts_dir
        / "components/core-qrexec/4.1.18-1/host-fc32/build/rpm_spec_qubes-qrexec-dom0.spec.build.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm"

    for rpm in rpms.union({srpm}):
        assert (
            artifacts_dir / "repository/host-fc32/core-qrexec_4.1.18" / rpm
        ).exists()

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm

    # buildinfo
    assert (
        artifacts_dir
        / "components/core-qrexec/4.1.18-1/host-fc32/build/rpm/qubes-core-qrexec-4.1.18-1.fc32.x86_64.buildinfo"
    ).exists()


def test_component_sign_host_fc32(artifacts_dir):
    env = os.environ.copy()

    buildinfo = (
        artifacts_dir
        / "components/core-qrexec/4.1.18-1/host-fc32/build/rpm/qubes-core-qrexec-4.1.18-1.fc32.x86_64.buildinfo"
    )
    buildinfo_number_lines = len(buildinfo.read_text(encoding="utf8").splitlines())

    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        # Better copy testing keyring into a separate directory to prevent locks inside
        # local sources (when executed locally).
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)
        # Enforce keyring location
        env["GNUPGHOME"] = gnupghome
        # We prevent rpm to find ~/.rpmmacros
        env["HOME"] = tmpdir

        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "package",
            "sign",
            env=env,
        )

    dbpath = artifacts_dir / "rpmdb/632F8C69E01B25C9E0C3ADF2F360C0D259FB650C"
    assert dbpath.exists()

    rpms = [
        "qubes-core-qrexec-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
    ]
    for rpm in rpms:
        rpm_path = (
            artifacts_dir
            / f"components/core-qrexec/4.1.18-1/host-fc32/{f'prep/{rpm}' if rpm.endswith('.src.rpm') else f'build/rpm/{rpm}'}"
        )
        assert rpm_path.exists()
        result = subprocess.run(
            f"rpm --dbpath {dbpath} -K {rpm_path}",
            check=True,
            capture_output=True,
            shell=True,
        )
        assert "digests signatures OK" in result.stdout.decode()

    # Ensure that original content is at least here with the 3 headers PGP BEGIN/END and at least
    # one line inside the signature
    signed_buildinfo_number_lines = len(
        buildinfo.read_text(encoding="utf8").splitlines()
    )
    assert signed_buildinfo_number_lines > buildinfo_number_lines + 4


def test_component_publish_host_fc32(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        # publish into unstable
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "repository",
            "publish",
            "unstable",
            env=env,
        )

        rpms = {
            "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
        }
        srpm = "qubes-core-qrexec-4.1.18-1.fc32.src.rpm"

        rpms_dom0 = {
            "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
        }
        srpm_dom0 = "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm"

        with open(
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec.spec.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        with open(
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec-dom0.spec.publish.yml"
        ) as f:
            info_dom0 = yaml.safe_load(f.read())

        assert set(info.get("rpms", [])) == rpms
        assert info.get("srpm", None) == srpm
        assert HASH_RE.match(info.get("source-hash", None))
        assert ["unstable"] == [r["name"] for r in info.get("repository-publish", [])]

        assert set(info_dom0.get("rpms", [])) == rpms_dom0
        assert info_dom0.get("srpm", None) == srpm_dom0
        assert HASH_RE.match(info_dom0.get("source-hash", None))
        assert ["unstable"] == [r["name"] for r in info.get("repository-publish", [])]

        # publish into current-testing
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "repository",
            "publish",
            "current-testing",
            env=env,
        )
        with open(
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec.spec.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        with open(
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec-dom0.spec.publish.yml"
        ) as f:
            info_dom0 = yaml.safe_load(f.read())

        assert set(info.get("rpms", [])) == rpms
        assert info.get("srpm", None) == srpm
        assert HASH_RE.match(info.get("source-hash", None))
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
        }

        assert set(info_dom0.get("rpms", [])) == rpms_dom0
        assert info_dom0.get("srpm", None) == srpm_dom0
        assert HASH_RE.match(info_dom0.get("source-hash", None))
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
        }

        # buildinfo
        assert (
            artifacts_dir / "repository-publish/rpm/r4.2/current-testing/host/fc32"
        ).exists()

        # publish into current
        fake_time = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d%H%M")
        publish_file = (
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec.spec.publish.yml"
        )
        publish_dom0_file = (
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec-dom0.spec.publish.yml"
        )

        for r in info["repository-publish"]:
            if r["name"] == "current-testing":
                r["timestamp"] = fake_time
                break

        for r in info_dom0["repository-publish"]:
            if r["name"] == "current-testing":
                r["timestamp"] = fake_time
                break

        with open(publish_file, "w") as f:
            f.write(yaml.safe_dump(info))

        with open(publish_dom0_file, "w") as f:
            f.write(yaml.safe_dump(info_dom0))

        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "repository",
            "publish",
            "current",
            env=env,
        )
        with open(publish_file) as f:
            info = yaml.safe_load(f.read())

        with open(publish_dom0_file) as f:
            info_dom0 = yaml.safe_load(f.read())

        assert set(info.get("rpms", [])) == rpms
        assert info.get("srpm", None) == srpm
        assert HASH_RE.match(info.get("source-hash", None))
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
            "current",
        }

        assert set(info_dom0.get("rpms", [])) == rpms_dom0
        assert info_dom0.get("srpm", None) == srpm_dom0
        assert HASH_RE.match(info_dom0.get("source-hash", None))
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
            "current",
        }

        # buildinfo
        assert (
            artifacts_dir / "repository-publish/rpm/r4.2/current/host/fc32"
        ).exists()

    rpms = [
        "qubes-core-qrexec-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
    ]

    # Check that packages are in the published repository
    for repository in ["unstable", "current-testing", "current"]:
        repository_dir = (
            f"file://{artifacts_dir}/repository-publish/rpm/r4.2/{repository}/host/fc32"
        )
        packages = rpm_packages_list(repository_dir)
        assert set(rpms) == set(packages)


def test_component_upload_host_fc32(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)
        builder_conf = tmpdir + "/builder.yml"
        with open(builder_conf, "w") as builder_f:
            builder_f.write(DEFAULT_BUILDER_CONF.read_text())
            builder_f.write(
                f"""
repository-upload-remote-host:
 rpm: {tmpdir}/repo/rpm/r4.2
 deb: {tmpdir}/repo/deb/r4.2
"""
            )

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        # upload into unstable, only host-fc32
        qb_call(
            builder_conf,
            artifacts_dir,
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "repository",
            "upload",
            "unstable",
            env=env,
        )

        rpms = {
            "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
        }
        srpm = "qubes-core-qrexec-4.1.18-1.fc32.src.rpm"

        rpms_dom0 = {
            "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
        }
        srpm_dom0 = "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm"

        for rpm in itertools.chain([srpm_dom0], rpms_dom0, rpms, [srpm]):
            assert (
                pathlib.Path(tmpdir) / f"repo/rpm/r4.2/unstable/host/fc32/rpm/{rpm}"
            ).exists()

        # vm-fc36 shouldn't exist, as nothing was published into it
        assert not (pathlib.Path(tmpdir) / f"repo/rpm/r4.2/unstable/vm/fc36").exists()

        # and vm-bullseye same
        assert not (
            pathlib.Path(tmpdir) / f"repo/deb/r4.2/vm/dists/bullseye-unstable"
        ).exists()


# Check that we properly ignore already done stages.


def test_component_prep_host_fc32_skip(artifacts_dir):
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "core-qrexec",
        "-d",
        "host-fc32",
        "package",
        "prep",
        stderr=subprocess.STDOUT,
    ).decode()
    print(result)
    assert (
        "core-qrexec:host-fedora-32.x86_64: Source hash is the same than already prepared source. Skipping."
        in result
    )


def test_component_build_host_fc32_skip(artifacts_dir):
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "core-qrexec",
        "-d",
        "host-fc32",
        "package",
        "build",
        stderr=subprocess.STDOUT,
    ).decode()
    print(result)
    assert (
        "core-qrexec:host-fedora-32.x86_64: Source hash is the same than already built source. Skipping."
        in result
    )


def test_component_sign_host_fc32_skip(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        result = qb_call_output(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "package",
            "sign",
            stderr=subprocess.STDOUT,
            env=env,
        ).decode()

    rpms = [
        "qubes-core-qrexec-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
    ]
    for rpm in rpms:
        assert f"{rpm} has already a valid signature. Skipping." in result


# Check that we unpublish properly from current-testing


def test_component_unpublish_host_fc32(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        # publish into unstable
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "repository",
            "unpublish",
            "current",
            env=env,
        )

        rpms = {
            "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
        }
        srpm = "qubes-core-qrexec-4.1.18-1.fc32.src.rpm"

        rpms_dom0 = {
            "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
        }
        srpm_dom0 = "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm"

        with open(
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec.spec.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        with open(
            artifacts_dir
            / "components/core-qrexec/4.1.18-1/host-fc32/publish/rpm_spec_qubes-qrexec-dom0.spec.publish.yml"
        ) as f:
            info_dom0 = yaml.safe_load(f.read())

        assert set(info.get("rpms", [])) == rpms
        assert info.get("srpm", None) == srpm
        assert HASH_RE.match(info.get("source-hash", None))
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
        }

        assert set(info_dom0.get("rpms", [])) == rpms_dom0
        assert info_dom0.get("srpm", None) == srpm_dom0
        assert HASH_RE.match(info_dom0.get("source-hash", None))
        assert set([r["name"] for r in info_dom0.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
        }

    # Check that packages are in the published repository
    rpms = [
        "qubes-core-qrexec-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.18-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.18-1.fc32.x86_64.rpm",
    ]
    for repository in ["unstable", "current-testing", "current"]:
        repository_dir = (
            f"file://{artifacts_dir}/repository-publish/rpm/r4.2/{repository}/host/fc32"
        )
        packages = rpm_packages_list(repository_dir)
        if repository == "current":
            assert packages == []
        else:
            assert set(rpms) == set(packages)


#
# Pipeline for python-qasync and vm-bullseye
#


def test_component_prep_vm_bullseye(artifacts_dir):
    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "python-qasync",
        "-d",
        "vm-bullseye",
        "package",
        "prep",
    )

    with open(
        artifacts_dir
        / "components/python-qasync/0.23.0-1/vm-bullseye/prep/debian-pkg_debian.prep.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    packages = [
        "python3-qasync_0.23.0-1+deb11u1_all.deb",
        "python3-qasync-dbgsym_0.23.0-1+deb11u1_all.deb",
    ]
    debian = "python-qasync_0.23.0-1+deb11u1.debian.tar.xz"
    dsc = "python-qasync_0.23.0-1+deb11u1.dsc"
    orig = "python-qasync_0.23.0.orig.tar.gz"
    package_release_name = "python-qasync_0.23.0"
    package_release_name_full = "python-qasync_0.23.0-1+deb11u1"

    assert info.get("packages", []) == packages
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("debian", None) == debian
    assert info.get("dsc", None) == dsc
    assert info.get("orig", None) == orig
    assert info.get("package-release-name", None) == package_release_name
    assert info.get("package-release-name-full", None) == package_release_name_full


def test_component_build_vm_bullseye(artifacts_dir):
    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "python-qasync",
        "-d",
        "vm-bullseye",
        "package",
        "build",
    )

    with open(
        artifacts_dir
        / "components/python-qasync/0.23.0-1/vm-bullseye/build/debian-pkg_debian.build.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    packages = ["python3-qasync_0.23.0-1+deb11u1_all.deb"]
    debian = "python-qasync_0.23.0-1+deb11u1.debian.tar.xz"
    dsc = "python-qasync_0.23.0-1+deb11u1.dsc"
    orig = "python-qasync_0.23.0.orig.tar.gz"
    package_release_name = "python-qasync_0.23.0"
    package_release_name_full = "python-qasync_0.23.0-1+deb11u1"

    assert info.get("packages", []) == packages
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("debian", None) == debian
    assert info.get("dsc", None) == dsc
    assert info.get("orig", None) == orig
    assert info.get("package-release-name", None) == package_release_name
    assert info.get("package-release-name-full", None) == package_release_name_full


def test_component_sign_vm_bullseye(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "package",
            "sign",
            env=env,
        )

    keyring_dir = (
        artifacts_dir / "components/python-qasync/0.23.0-1/vm-bullseye/sign/keyring"
    )
    assert keyring_dir.exists()

    files = [
        "python-qasync_0.23.0-1+deb11u1.dsc",
        "python-qasync_0.23.0-1+deb11u1_amd64.changes",
        "python-qasync_0.23.0-1+deb11u1_amd64.buildinfo",
    ]
    for f in files:
        file_path = (
            artifacts_dir / f"components/python-qasync/0.23.0-1/vm-bullseye/build/{f}"
        )
        assert file_path.exists()
        result = subprocess.run(
            f"gpg2 --homedir {keyring_dir} --verify {file_path}",
            shell=True,
        )
        assert result.returncode == 0


def test_component_publish_vm_bullseye(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        # publish into unstable
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "repository",
            "publish",
            "unstable",
            env=env,
        )

        with open(
            artifacts_dir
            / "components/python-qasync/0.23.0-1/vm-bullseye/publish/debian-pkg_debian.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        packages = ["python3-qasync_0.23.0-1+deb11u1_all.deb"]
        debian = "python-qasync_0.23.0-1+deb11u1.debian.tar.xz"
        dsc = "python-qasync_0.23.0-1+deb11u1.dsc"
        orig = "python-qasync_0.23.0.orig.tar.gz"
        package_release_name = "python-qasync_0.23.0"
        package_release_name_full = "python-qasync_0.23.0-1+deb11u1"

        assert info.get("packages", []) == packages
        assert HASH_RE.match(info.get("source-hash", None))
        assert info.get("debian", None) == debian
        assert info.get("dsc", None) == dsc
        assert info.get("orig", None) == orig
        assert info.get("package-release-name", None) == package_release_name
        assert info.get("package-release-name-full", None) == package_release_name_full
        assert ["unstable"] == [r["name"] for r in info.get("repository-publish", [])]

        # publish into current-testing
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "repository",
            "publish",
            "current-testing",
            env=env,
        )
        with open(
            artifacts_dir
            / "components/python-qasync/0.23.0-1/vm-bullseye/publish/debian-pkg_debian.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        assert info.get("packages", []) == packages
        assert HASH_RE.match(info.get("source-hash", None))
        assert info.get("debian", None) == debian
        assert info.get("dsc", None) == dsc
        assert info.get("orig", None) == orig
        assert info.get("package-release-name", None) == package_release_name
        assert info.get("package-release-name-full", None) == package_release_name_full
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
        }

        # publish into current
        fake_time = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d%H%M")
        publish_file = (
            artifacts_dir
            / "components/python-qasync/0.23.0-1/vm-bullseye/publish/debian-pkg_debian.publish.yml"
        )

        for r in info["repository-publish"]:
            if r["name"] == "current-testing":
                r["timestamp"] = fake_time
                break

        with open(publish_file, "w") as f:
            f.write(yaml.safe_dump(info))

        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "repository",
            "publish",
            "current",
            env=env,
        )
        with open(publish_file) as f:
            info = yaml.safe_load(f.read())

        assert info.get("packages", []) == packages
        assert HASH_RE.match(info.get("source-hash", None))
        assert info.get("debian", None) == debian
        assert info.get("dsc", None) == dsc
        assert info.get("orig", None) == orig
        assert info.get("package-release-name", None) == package_release_name
        assert info.get("package-release-name-full", None) == package_release_name_full
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
            "current",
        }

    # Check that packages are in the published repositories
    repository_dir = artifacts_dir / "repository-publish/deb/r4.2/vm"
    for codename in ["bullseye-unstable", "bullseye-testing", "bullseye"]:
        packages = deb_packages_list(repository_dir, codename)
        expected_packages = [
            f"{codename}|main|amd64: python3-qasync 0.23.0-1+deb11u1",
            f"{codename}|main|source: python-qasync 0.23.0-1+deb11u1",
        ]
        assert set(packages) == set(expected_packages)


# Check that we properly ignore already done stages.


def test_component_prep_vm_bullseye_skip(artifacts_dir):
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "python-qasync",
        "-d",
        "vm-bullseye",
        "package",
        "prep",
        stderr=subprocess.STDOUT,
    ).decode()
    print(result)
    assert (
        "python-qasync:vm-debian-11.amd64: Source hash is the same than already prepared source. Skipping."
        in result
    )


def test_component_build_vm_bullseye_skip(artifacts_dir):
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "-c",
        "python-qasync",
        "-d",
        "vm-bullseye",
        "package",
        "build",
        stderr=subprocess.STDOUT,
    ).decode()
    print(result)
    assert (
        "python-qasync:vm-debian-11.amd64: Source hash is the same than already built source. Skipping."
        in result
    )


def test_component_sign_vm_bullseye_skip(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        result = qb_call_output(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "package",
            "sign",
            stderr=subprocess.STDOUT,
            env=env,
        ).decode()

    assert f"Leaving current signature unchanged." in result


# Check that we unpublish properly from current-testing


def test_component_unpublish_vm_bullseye(artifacts_dir):
    # FIXME: we rely on previous test_publish_vm_bullseye being ran before
    repository_dir = artifacts_dir / "repository-publish/deb/r4.2/vm"
    for codename in ["bullseye-unstable", "bullseye-testing", "bullseye"]:
        packages = deb_packages_list(repository_dir, codename)
        expected_packages = [
            f"{codename}|main|amd64: python3-qasync 0.23.0-1+deb11u1",
            f"{codename}|main|source: python-qasync 0.23.0-1+deb11u1",
        ]
        assert set(packages) == set(expected_packages)

    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        # publish into unstable
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "repository",
            "unpublish",
            "current",
            env=env,
        )

        packages = ["python3-qasync_0.23.0-1+deb11u1_all.deb"]
        debian = "python-qasync_0.23.0-1+deb11u1.debian.tar.xz"
        dsc = "python-qasync_0.23.0-1+deb11u1.dsc"
        orig = "python-qasync_0.23.0.orig.tar.gz"
        package_release_name = "python-qasync_0.23.0"
        package_release_name_full = "python-qasync_0.23.0-1+deb11u1"

        with open(
            artifacts_dir
            / "components/python-qasync/0.23.0-1/vm-bullseye/publish/debian-pkg_debian.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        assert info.get("packages", []) == packages
        assert HASH_RE.match(info.get("source-hash", None))
        assert info.get("debian", None) == debian
        assert info.get("dsc", None) == dsc
        assert info.get("orig", None) == orig
        assert info.get("package-release-name", None) == package_release_name
        assert info.get("package-release-name-full", None) == package_release_name_full
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "unstable",
            "current-testing",
        }

    # Check that packages are in the published repositories
    repository_dir = artifacts_dir / "repository-publish/deb/r4.2/vm"
    for codename in ["bullseye-unstable", "bullseye-testing", "bullseye"]:
        packages = deb_packages_list(repository_dir, codename)
        if codename == "bullseye":
            expected_packages = []
        else:
            expected_packages = [
                f"{codename}|main|amd64: python3-qasync 0.23.0-1+deb11u1",
                f"{codename}|main|source: python-qasync 0.23.0-1+deb11u1",
            ]
        assert set(packages) == set(expected_packages)


#
# Pipeline for Fedora 36 XFCE template
#


def test_template_prep_fedora_36_xfce(artifacts_dir):
    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "--option",
        "executor:type=qubes",
        "--option",
        "executor:options:dispvm=qubes-builder-dvm",
        "-t",
        "fedora-36-xfce",
        "template",
        "prep",
    )

    assert (artifacts_dir / "templates/build_timestamp_fedora-36-xfce").exists()
    assert (
        artifacts_dir / "templates/qubeized_images/fedora-36-xfce/root.img"
    ).exists()
    assert (artifacts_dir / "templates/fedora-36-xfce/appmenus").exists()
    assert (artifacts_dir / "templates/fedora-36-xfce/template.conf").exists()


def test_template_build_fedora_36_xfce(artifacts_dir):
    qb_call(
        DEFAULT_BUILDER_CONF,
        artifacts_dir,
        "--option",
        "executor:type=qubes",
        "--option",
        "executor:options:dispvm=qubes-builder-dvm",
        "-t",
        "fedora-36-xfce",
        "template",
        "build",
    )

    assert (artifacts_dir / "templates/build_timestamp_fedora-36-xfce").exists()

    with open(artifacts_dir / "templates/build_timestamp_fedora-36-xfce") as f:
        data = f.read().splitlines()
    template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%M")
    rpm_path = (
        artifacts_dir
        / f"templates/rpm/qubes-template-fedora-36-xfce-4.1.0-{template_timestamp}.noarch.rpm"
    )
    assert rpm_path.exists()


def test_template_sign_fedora_36_xfce(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        # Better copy testing keyring into a separate directory to prevent locks inside
        # local sources (when executed locally).
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)
        # Enforce keyring location
        env["GNUPGHOME"] = gnupghome
        # We prevent rpm to find ~/.rpmmacros
        env["HOME"] = tmpdir

        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-t",
            "fedora-36-xfce",
            "template",
            "sign",
            env=env,
        )

    dbpath = artifacts_dir / "templates/rpmdb"
    assert dbpath.exists()

    with open(artifacts_dir / "templates/build_timestamp_fedora-36-xfce") as f:
        data = f.read().splitlines()
    template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%M")
    rpm_path = (
        artifacts_dir
        / f"templates/rpm/qubes-template-fedora-36-xfce-4.1.0-{template_timestamp}.noarch.rpm"
    )
    assert rpm_path.exists()
    result = subprocess.run(
        f"rpm --dbpath {dbpath} -K {rpm_path}",
        check=True,
        capture_output=True,
        shell=True,
    )
    assert "digests signatures OK" in result.stdout.decode()


def test_template_publish_fedora_36_xfce(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        # publish into templates-itl-testing
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-t",
            "fedora-36-xfce",
            "repository",
            "publish",
            "templates-itl-testing",
            env=env,
        )

        with open(artifacts_dir / "templates/fedora-36-xfce.publish.yml") as f:
            info = yaml.safe_load(f.read())

        with open(artifacts_dir / "templates/build_timestamp_fedora-36-xfce") as f:
            data = f.read().splitlines()
        template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%M")

        assert info.get("timestamp", []) == template_timestamp
        assert ["templates-itl-testing"] == [
            r["name"] for r in info.get("repository-publish", [])
        ]

        # publish into templates-itl
        fake_time = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d%H%M")
        publish_file = artifacts_dir / "templates/fedora-36-xfce.publish.yml"

        for r in info["repository-publish"]:
            if r["name"] == "templates-itl-testing":
                r["timestamp"] = fake_time
                break

        with open(publish_file, "w") as f:
            f.write(yaml.safe_dump(info))

        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-t",
            "fedora-36-xfce",
            "repository",
            "publish",
            "templates-itl",
            env=env,
        )
        with open(publish_file) as f:
            info = yaml.safe_load(f.read())

        assert info.get("timestamp", []) == template_timestamp
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "templates-itl-testing",
            "templates-itl",
        }

    # Check that packages are in the published repository
    for repository in ["templates-itl-testing", "templates-itl"]:
        rpm = f"qubes-template-fedora-36-xfce-4.1.0-{template_timestamp}.noarch.rpm"
        repository_dir = (
            f"file://{artifacts_dir}/repository-publish/rpm/r4.2/{repository}"
        )
        packages = rpm_packages_list(repository_dir)
        assert {rpm} == set(packages)


def test_template_unpublish_fedora_36_xfce(artifacts_dir):
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        with open(artifacts_dir / "templates/build_timestamp_fedora-36-xfce") as f:
            data = f.read().splitlines()
        template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%M")

        # unpublish from templates-itl
        qb_call(
            DEFAULT_BUILDER_CONF,
            artifacts_dir,
            "-t",
            "fedora-36-xfce",
            "repository",
            "unpublish",
            "templates-itl",
            env=env,
        )

        publish_file = artifacts_dir / "templates/fedora-36-xfce.publish.yml"
        with open(publish_file) as f:
            info = yaml.safe_load(f.read())

        assert info.get("timestamp", []) == template_timestamp
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "templates-itl-testing"
        }

    # Check that packages are in the published repository
    for repository in ["templates-itl-testing", "templates-itl"]:
        rpm = f"qubes-template-fedora-36-xfce-4.1.0-{template_timestamp}.noarch.rpm"
        repository_dir = (
            f"file://{artifacts_dir}/repository-publish/rpm/r4.2/{repository}"
        )
        packages = rpm_packages_list(repository_dir)
        if repository == "templates-itl":
            assert packages == []
        else:
            assert {rpm} == set(packages)
