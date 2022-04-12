import os.path
import re
import shutil
import subprocess
import tempfile
import dnf
import yaml
import dateutil.parser
from dateutil.parser import parse as parsedate
from datetime import datetime, timedelta
from qubesbuilder.common import PROJECT_PATH

DEFAULT_BUILDER_CONF = PROJECT_PATH / "tests/builder-ci.yml"
ARTIFACTS_DIR = PROJECT_PATH / "artifacts"
HASH_RE = re.compile("[a-f0-9]{40}")


def qb_call(builder_conf, *args, **kwargs):
    subprocess.check_call(
        [PROJECT_PATH / "qb", "--verbose", "--builder-conf", builder_conf, *args],
        **kwargs,
    )


def qb_call_output(builder_conf, *args, **kwargs):
    return subprocess.check_output(
        [PROJECT_PATH / "qb", "--verbose", "--builder-conf", builder_conf, *args],
        **kwargs,
    )


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
# Fetch
#


def test_fetch():
    qb_call(DEFAULT_BUILDER_CONF, "package", "fetch")

    assert (ARTIFACTS_DIR / "distfiles/qasync-0.9.4.tar.gz").exists()
    assert (ARTIFACTS_DIR / "distfiles/xfwm4-4.14.2.tar.bz2").exists()

    for component in [
        "core-qrexec",
        "core-vchan-xen",
        "desktop-linux-xfce4-xfwm4",
        "python-qasync",
    ]:
        assert (ARTIFACTS_DIR / "sources" / component / ".qubesbuilder").exists()


def test_fetch_skip():
    result = qb_call_output(
        DEFAULT_BUILDER_CONF, "package", "fetch", stderr=subprocess.STDOUT
    ).decode()
    for sentence in [
        "python-qasync: source already fetched. Skipping.",
        "core-vchan-xen: source already fetched. Skipping.",
        "core-qrexec: source already fetched. Skipping.",
        "desktop-linux-xfce4-xfwm4: source already fetched. Skipping.",
        "python-qasync: file qasync-0.9.4.tar.gz already downloaded. Skipping.",
        "desktop-linux-xfce4-xfwm4: file xfwm4-4.14.2.tar.bz2 already downloaded. Skipping.",
    ]:
        assert sentence in result


#
# Pipeline for core-qrexec and host-fc32
#


def test_prep_host_fc32():
    qb_call(
        DEFAULT_BUILDER_CONF, "-c", "core-qrexec", "-d", "host-fc32", "package", "prep"
    )

    with open(
        ARTIFACTS_DIR
        / "components/core-qrexec/4.1.16-1/host-fc32/prep/qubes-qrexec.prep.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debugsource-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-4.1.16-1.fc32.src.rpm"

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm

    with open(
        ARTIFACTS_DIR
        / "components/core-qrexec/4.1.16-1/host-fc32/prep/qubes-qrexec-dom0.prep.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm"

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm


def test_build_host_fc32():
    qb_call(
        DEFAULT_BUILDER_CONF, "-c", "core-qrexec", "-d", "host-fc32", "package", "build"
    )

    with open(
        ARTIFACTS_DIR
        / "components/core-qrexec/4.1.16-1/host-fc32/build/qubes-qrexec.build.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-4.1.16-1.fc32.src.rpm"

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm

    with open(
        ARTIFACTS_DIR
        / "components/core-qrexec/4.1.16-1/host-fc32/build/qubes-qrexec-dom0.build.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    rpms = {
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
    }
    srpm = "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm"

    assert set(info.get("rpms", [])) == rpms
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("srpm", None) == srpm


def test_sign_host_fc32():
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
            "-c",
            "core-qrexec",
            "-d",
            "host-fc32",
            "package",
            "sign",
            env=env,
        )

    assert (
        ARTIFACTS_DIR
        / "components/core-qrexec/4.1.16-1/host-fc32/sign/632F8C69E01B25C9E0C3ADF2F360C0D259FB650C.asc"
    ).exists()

    dbpath = ARTIFACTS_DIR / "components/core-qrexec/4.1.16-1/host-fc32/sign/rpmdb"
    assert dbpath.exists()

    rpms = [
        "qubes-core-qrexec-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
    ]
    for rpm in rpms:
        rpm_path = (
            ARTIFACTS_DIR
            / f"components/core-qrexec/4.1.16-1/host-fc32/{f'prep/{rpm}' if rpm.endswith('.src.rpm') else f'build/rpm/{rpm}'}"
        )
        assert rpm_path.exists()
        result = subprocess.run(
            f"rpm --dbpath {dbpath} -K {rpm_path}",
            check=True,
            capture_output=True,
            shell=True,
        )
        assert "digests signatures OK" in result.stdout.decode()


def test_publish_host_fc32():
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
            "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
        }
        srpm = "qubes-core-qrexec-4.1.16-1.fc32.src.rpm"

        rpms_dom0 = {
            "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
        }
        srpm_dom0 = "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm"

        with open(
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        with open(
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec-dom0.publish.yml"
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
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        with open(
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec-dom0.publish.yml"
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

        # publish into current
        fake_time = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d%H%MZ")
        publish_file = (
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec.publish.yml"
        )
        publish_dom0_file = (
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec-dom0.publish.yml"
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

    rpms = [
        "qubes-core-qrexec-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
    ]

    # Check that packages are in the published repository
    for repository in ["unstable", "current-testing", "current"]:
        repository_dir = (
            f"file://{ARTIFACTS_DIR}/repository-publish/rpm/r4.2/{repository}/host/fc32"
        )
        packages = rpm_packages_list(repository_dir)
        assert set(rpms) == set(packages)


# Check that we properly ignore already done stages.


def test_prep_host_fc32_skip():
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
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


def test_build_host_fc32_skip():
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
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


def test_sign_host_fc32_skip():
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        result = qb_call_output(
            DEFAULT_BUILDER_CONF,
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
        "qubes-core-qrexec-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
    ]
    for rpm in rpms:
        assert f"{rpm} has already a valid signature. Skipping." in result


# Check that we unpublish properly from current-testing


def test_unpublish_host_fc32():
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
            "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
        }
        srpm = "qubes-core-qrexec-4.1.16-1.fc32.src.rpm"

        rpms_dom0 = {
            "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
            "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
        }
        srpm_dom0 = "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm"

        with open(
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        with open(
            ARTIFACTS_DIR
            / "components/core-qrexec/4.1.16-1/host-fc32/publish/qubes-qrexec-dom0.publish.yml"
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
        "qubes-core-qrexec-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-debugsource-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-libs-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-devel-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.src.rpm",
        "qubes-core-qrexec-dom0-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debuginfo-4.1.16-1.fc32.x86_64.rpm",
        "qubes-core-qrexec-dom0-debugsource-4.1.16-1.fc32.x86_64.rpm",
    ]
    for repository in ["unstable", "current-testing", "current"]:
        repository_dir = (
            f"file://{ARTIFACTS_DIR}/repository-publish/rpm/r4.2/{repository}/host/fc32"
        )
        packages = rpm_packages_list(repository_dir)
        if repository == "current":
            assert packages == []
        else:
            assert set(rpms) == set(packages)


#
# Pipeline for python-qasync and vm-bullseye
#


def test_prep_vm_bullseye():
    qb_call(
        DEFAULT_BUILDER_CONF,
        "-c",
        "python-qasync",
        "-d",
        "vm-bullseye",
        "package",
        "prep",
    )

    with open(
        ARTIFACTS_DIR
        / "components/python-qasync/0.9.4-2/vm-bullseye/prep/debian.prep.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    packages = [
        "python3-qasync_0.9.4-2+deb11u1_all.deb",
        "python3-qasync-dbgsym_0.9.4-2+deb11u1_all.deb",
    ]
    debian = "python-qasync_0.9.4-2+deb11u1.debian.tar.xz"
    dsc = "python-qasync_0.9.4-2+deb11u1.dsc"
    orig = "python-qasync_0.9.4.orig.tar.gz"
    package_release_name = "python-qasync_0.9.4"
    package_release_name_full = "python-qasync_0.9.4-2+deb11u1"

    assert info.get("packages", []) == packages
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("debian", None) == debian
    assert info.get("dsc", None) == dsc
    assert info.get("orig", None) == orig
    assert info.get("package-release-name", None) == package_release_name
    assert info.get("package-release-name-full", None) == package_release_name_full


def test_build_vm_bullseye():
    qb_call(
        DEFAULT_BUILDER_CONF,
        "-c",
        "python-qasync",
        "-d",
        "vm-bullseye",
        "package",
        "build",
    )

    with open(
        ARTIFACTS_DIR
        / "components/python-qasync/0.9.4-2/vm-bullseye/build/debian.build.yml"
    ) as f:
        info = yaml.safe_load(f.read())

    packages = ["python3-qasync_0.9.4-2+deb11u1_all.deb"]
    debian = "python-qasync_0.9.4-2+deb11u1.debian.tar.xz"
    dsc = "python-qasync_0.9.4-2+deb11u1.dsc"
    orig = "python-qasync_0.9.4.orig.tar.gz"
    package_release_name = "python-qasync_0.9.4"
    package_release_name_full = "python-qasync_0.9.4-2+deb11u1"

    assert info.get("packages", []) == packages
    assert HASH_RE.match(info.get("source-hash", None))
    assert info.get("debian", None) == debian
    assert info.get("dsc", None) == dsc
    assert info.get("orig", None) == orig
    assert info.get("package-release-name", None) == package_release_name
    assert info.get("package-release-name-full", None) == package_release_name_full


def test_sign_vm_bullseye():
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        qb_call(
            DEFAULT_BUILDER_CONF,
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "package",
            "sign",
            env=env,
        )

    assert (
        ARTIFACTS_DIR
        / "components/python-qasync/0.9.4-2/vm-bullseye/sign/632F8C69E01B25C9E0C3ADF2F360C0D259FB650C.asc"
    ).exists()

    keyring_dir = (
        ARTIFACTS_DIR / "components/python-qasync/0.9.4-2/vm-bullseye/sign/keyring"
    )
    assert keyring_dir.exists()

    files = [
        "python-qasync_0.9.4-2+deb11u1.dsc",
        "python-qasync_0.9.4-2+deb11u1_amd64.changes",
        "python-qasync_0.9.4-2+deb11u1_amd64.buildinfo",
    ]
    for f in files:
        file_path = (
            ARTIFACTS_DIR / f"components/python-qasync/0.9.4-2/vm-bullseye/build/{f}"
        )
        assert file_path.exists()
        result = subprocess.run(
            f"gpg2 --homedir {keyring_dir} --verify {file_path}",
            shell=True,
        )
        assert result.returncode == 0


def test_publish_vm_bullseye():
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
            ARTIFACTS_DIR
            / "components/python-qasync/0.9.4-2/vm-bullseye/publish/debian.publish.yml"
        ) as f:
            info = yaml.safe_load(f.read())

        packages = ["python3-qasync_0.9.4-2+deb11u1_all.deb"]
        debian = "python-qasync_0.9.4-2+deb11u1.debian.tar.xz"
        dsc = "python-qasync_0.9.4-2+deb11u1.dsc"
        orig = "python-qasync_0.9.4.orig.tar.gz"
        package_release_name = "python-qasync_0.9.4"
        package_release_name_full = "python-qasync_0.9.4-2+deb11u1"

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
            ARTIFACTS_DIR
            / "components/python-qasync/0.9.4-2/vm-bullseye/publish/debian.publish.yml"
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
        fake_time = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d%H%MZ")
        publish_file = (
            ARTIFACTS_DIR
            / "components/python-qasync/0.9.4-2/vm-bullseye/publish/debian.publish.yml"
        )

        for r in info["repository-publish"]:
            if r["name"] == "current-testing":
                r["timestamp"] = fake_time
                break

        with open(publish_file, "w") as f:
            f.write(yaml.safe_dump(info))

        qb_call(
            DEFAULT_BUILDER_CONF,
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
    repository_dir = ARTIFACTS_DIR / "repository-publish/deb/r4.2/vm"
    for codename in ["bullseye-unstable", "bullseye-testing", "bullseye"]:
        packages = deb_packages_list(repository_dir, codename)
        expected_packages = [
            f"{codename}|main|amd64: python3-qasync 0.9.4-2+deb11u1",
            f"{codename}|main|source: python-qasync 0.9.4-2+deb11u1",
        ]
        assert set(packages) == set(expected_packages)


# Check that we properly ignore already done stages.


def test_prep_vm_bullseye_skip():
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
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


def test_build_vm_bullseye_skip():
    result = qb_call_output(
        DEFAULT_BUILDER_CONF,
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


def test_sign_vm_bullseye_skip():
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        result = qb_call_output(
            DEFAULT_BUILDER_CONF,
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


def test_unpublish_vm_bullseye():
    # FIXME: we rely on previous test_publish_vm_bullseye being ran before
    repository_dir = ARTIFACTS_DIR / "repository-publish/deb/r4.2/vm"
    for codename in ["bullseye-unstable", "bullseye-testing", "bullseye"]:
        packages = deb_packages_list(repository_dir, codename)
        expected_packages = [
            f"{codename}|main|amd64: python3-qasync 0.9.4-2+deb11u1",
            f"{codename}|main|source: python-qasync 0.9.4-2+deb11u1",
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
            "-c",
            "python-qasync",
            "-d",
            "vm-bullseye",
            "repository",
            "unpublish",
            "current",
            env=env,
        )

        packages = ["python3-qasync_0.9.4-2+deb11u1_all.deb"]
        debian = "python-qasync_0.9.4-2+deb11u1.debian.tar.xz"
        dsc = "python-qasync_0.9.4-2+deb11u1.dsc"
        orig = "python-qasync_0.9.4.orig.tar.gz"
        package_release_name = "python-qasync_0.9.4"
        package_release_name_full = "python-qasync_0.9.4-2+deb11u1"

        with open(
            ARTIFACTS_DIR
            / "components/python-qasync/0.9.4-2/vm-bullseye/publish/debian.publish.yml"
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
    repository_dir = ARTIFACTS_DIR / "repository-publish/deb/r4.2/vm"
    for codename in ["bullseye-unstable", "bullseye-testing", "bullseye"]:
        packages = deb_packages_list(repository_dir, codename)
        if codename == "bullseye":
            expected_packages = []
        else:
            expected_packages = [
                f"{codename}|main|amd64: python3-qasync 0.9.4-2+deb11u1",
                f"{codename}|main|source: python-qasync 0.9.4-2+deb11u1",
            ]
        assert set(packages) == set(expected_packages)


#
# Pipeline for Fedora 35 XFCE template
#


def test_prep_template_fedora_35_xfce():
    qb_call(
        DEFAULT_BUILDER_CONF,
        "-e",
        "qubes",
        "--executor-option",
        "dispvm=qubes-builder-dvm",
        "-t",
        "fedora-35-xfce",
        "template",
        "prep",
    )

    assert (ARTIFACTS_DIR / "templates/prepared_images/fedora-35-xfce.img").exists()
    assert (ARTIFACTS_DIR / "templates/build_timestamp_fedora-35-xfce").exists()


def test_build_template_fedora_35_xfce():
    qb_call(
        DEFAULT_BUILDER_CONF,
        "-e",
        "qubes",
        "--executor-option",
        "dispvm=qubes-builder-dvm",
        "-t",
        "fedora-35-xfce",
        "template",
        "build",
    )
    assert (ARTIFACTS_DIR / "templates/prepared_images/fedora-35-xfce.img").exists()
    assert (
        ARTIFACTS_DIR / "templates/qubeized_images/fedora-35-xfce/root.img"
    ).exists()
    assert (ARTIFACTS_DIR / "templates/build_timestamp_fedora-35-xfce").exists()

    with open(ARTIFACTS_DIR / "templates/build_timestamp_fedora-35-xfce") as f:
        data = f.read().splitlines()
    template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%MZ")
    rpm_path = (
        ARTIFACTS_DIR
        / f"templates/rpm/qubes-template-fedora-35-xfce-4.1.0-{template_timestamp}.noarch.rpm"
    )
    assert rpm_path.exists()


def test_sign_template_fedora_35_xfce():
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
            "-t",
            "fedora-35-xfce",
            "template",
            "sign",
            env=env,
        )

    assert (
        ARTIFACTS_DIR / "templates/632F8C69E01B25C9E0C3ADF2F360C0D259FB650C.asc"
    ).exists()

    dbpath = ARTIFACTS_DIR / "templates/rpmdb"
    assert dbpath.exists()

    with open(ARTIFACTS_DIR / "templates/build_timestamp_fedora-35-xfce") as f:
        data = f.read().splitlines()
    template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%MZ")
    rpm_path = (
        ARTIFACTS_DIR
        / f"templates/rpm/qubes-template-fedora-35-xfce-4.1.0-{template_timestamp}.noarch.rpm"
    )
    assert rpm_path.exists()
    result = subprocess.run(
        f"rpm --dbpath {dbpath} -K {rpm_path}",
        check=True,
        capture_output=True,
        shell=True,
    )
    assert "digests signatures OK" in result.stdout.decode()


def test_publish_template_fedora_35_xfce():
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
            "-t",
            "fedora-35-xfce",
            "repository",
            "publish",
            "templates-itl-testing",
            env=env,
        )

        with open(ARTIFACTS_DIR / "templates/fedora-35-xfce.publish.yml") as f:
            info = yaml.safe_load(f.read())

        with open(ARTIFACTS_DIR / "templates/build_timestamp_fedora-35-xfce") as f:
            data = f.read().splitlines()
        template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%MZ")

        assert info.get("timestamp", []) == template_timestamp
        assert ["templates-itl-testing"] == [
            r["name"] for r in info.get("repository-publish", [])
        ]

        # publish into templates-itl
        fake_time = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d%H%MZ")
        publish_file = ARTIFACTS_DIR / "templates/fedora-35-xfce.publish.yml"

        for r in info["repository-publish"]:
            if r["name"] == "templates-itl-testing":
                r["timestamp"] = fake_time
                break

        with open(publish_file, "w") as f:
            f.write(yaml.safe_dump(info))

        qb_call(
            DEFAULT_BUILDER_CONF,
            "-t",
            "fedora-35-xfce",
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
        rpm = f"qubes-template-fedora-35-xfce-4.1.0-{template_timestamp}.noarch.rpm"
        repository_dir = (
            f"file://{ARTIFACTS_DIR}/repository-publish/rpm/r4.2/{repository}"
        )
        packages = rpm_packages_list(repository_dir)
        assert {rpm} == set(packages)


def test_unpublish_template_fedora_35_xfce():
    env = os.environ.copy()
    with tempfile.TemporaryDirectory() as tmpdir:
        gnupghome = f"{tmpdir}/.gnupg"
        shutil.copytree(PROJECT_PATH / "tests/gnupg", gnupghome)
        os.chmod(gnupghome, 0o700)

        env["GNUPGHOME"] = gnupghome
        env["HOME"] = tmpdir

        with open(ARTIFACTS_DIR / "templates/build_timestamp_fedora-35-xfce") as f:
            data = f.read().splitlines()
        template_timestamp = parsedate(data[0]).strftime("%Y%m%d%H%MZ")

        # unpublish from templates-itl
        qb_call(
            DEFAULT_BUILDER_CONF,
            "-t",
            "fedora-35-xfce",
            "repository",
            "unpublish",
            "templates-itl",
            env=env,
        )

        publish_file = ARTIFACTS_DIR / "templates/fedora-35-xfce.publish.yml"
        with open(publish_file) as f:
            info = yaml.safe_load(f.read())

        assert info.get("timestamp", []) == template_timestamp
        assert set([r["name"] for r in info.get("repository-publish", [])]) == {
            "templates-itl-testing"
        }

    # Check that packages are in the published repository
    for repository in ["templates-itl-testing", "templates-itl"]:
        rpm = f"qubes-template-fedora-35-xfce-4.1.0-{template_timestamp}.noarch.rpm"
        repository_dir = (
            f"file://{ARTIFACTS_DIR}/repository-publish/rpm/r4.2/{repository}"
        )
        packages = rpm_packages_list(repository_dir)
        if repository == "templates-itl":
            assert packages == []
        else:
            assert {rpm} == set(packages)
