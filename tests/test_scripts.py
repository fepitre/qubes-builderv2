import importlib
import pathlib
import shutil
import subprocess
import tempfile
from argparse import Namespace

import pytest

from qubesbuilder.common import PROJECT_PATH


get_and_verify_source = importlib.import_module(
    "qubesbuilder.plugins.fetch.scripts.get-and-verify-source"
).main


@pytest.fixture
def temp_directory():
    # Create a temporary directory
    temp_dir = pathlib.Path(tempfile.mkdtemp())
    yield temp_dir
    # Remove the temporary directory after the test
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


#
# get_and_verify_source
#


def create_dummy_args(
    component_repository,
    component_directory,
    git_branch="main",
    fetch_only=False,
    fetch_versions_only=False,
    ignore_missing=False,
    clean=False,
    insecure_skip_checking=False,
    less_secure_signed_commits_sufficient=False,
    maintainers=None,
):
    args = Namespace()

    args.component_repository = component_repository
    args.component_directory = str(component_directory)
    args.keys_dir = str(PROJECT_PATH / "qubesbuilder/plugins/fetch/keys")
    args.git_keyring_dir = str(component_directory / ".keyring")

    args.git_branch = git_branch
    args.fetch_only = fetch_only
    args.fetch_versions_only = fetch_versions_only
    args.ignore_missing = ignore_missing
    args.clean = clean
    args.insecure_skip_checking = insecure_skip_checking
    args.less_secure_signed_commits_sufficient = less_secure_signed_commits_sufficient
    args.maintainer = (
        maintainers if maintainers and isinstance(maintainers, list) else []
    )

    return args


def test_repository(temp_directory):
    args = create_dummy_args(
        component_repository="https://github.com/qubesos/qubes-core-vchan-xen",
        component_directory=temp_directory,
    )
    get_and_verify_source(args)
    assert (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            cwd=str(temp_directory),
            text=True,
        ).stdout.strip()
        == "main"
    )
    assert (temp_directory / "version").exists()


def test_repository_invalid_branch(temp_directory):
    args = create_dummy_args(
        component_repository="https://github.com/qubesos/qubes-core-vchan-xen",
        component_directory=temp_directory,
        git_branch="nonexistent",
    )
    with pytest.raises(subprocess.CalledProcessError) as e:
        get_and_verify_source(args)
    assert (
        b"fatal: Remote branch nonexistent not found in upstream origin\n"
        == e.value.stderr
    )


def test_non_qubesos_repository(temp_directory):
    args = create_dummy_args(
        component_directory=temp_directory,
        component_repository="https://github.com/fepitre/qubes-core-qrexec",
        git_branch="builderv2",
    )
    with pytest.raises(ValueError) as e:
        get_and_verify_source(args)
    (msg,) = e.value.args
    assert msg == "---> Invalid commit 961bf3c7bd8cc5dc5335ee91afefbf7feb92c982"


def test_non_qubesos_repository_with_maintainer_and_no_signed_tags(
    temp_directory,
):
    args = create_dummy_args(
        component_directory=temp_directory,
        component_repository="https://github.com/fepitre/qubes-core-qrexec",
        git_branch="builderv2",
        less_secure_signed_commits_sufficient=True,
        maintainers=["9FA64B92F95E706BF28E2CA6484010B5CDC576E2"],
    )
    get_and_verify_source(args)
    assert (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            cwd=str(temp_directory),
            text=True,
        ).stdout.strip()
        == "builderv2"
    )


def test_repository_no_version_tags(temp_directory):
    args = create_dummy_args(
        component_repository="https://github.com/fepitre/qubes-core-qrexec",
        component_directory=temp_directory,
        git_branch="builderv2-tests-1",
        fetch_versions_only=True,
    )
    with pytest.raises(subprocess.CalledProcessError) as e:
        get_and_verify_source(args)
    assert "fatal: No names found, cannot describe anything.\n" == e.value.stderr


def test_existing_repository_no_version_tags(temp_directory):
    component_repository = "https://github.com/fepitre/qubes-core-qrexec"
    git_branch = "builderv2-tests-1"
    subprocess.run(
        ["git", "clone", "-b", git_branch, component_repository, temp_directory],
        check=True,
        capture_output=True,
    )
    args = create_dummy_args(
        component_repository=component_repository,
        component_directory=temp_directory,
        git_branch=git_branch,
        fetch_versions_only=True,
    )
    get_and_verify_source(args)
    assert not (temp_directory / ".git/FETCH_HEAD").exists()


def test_existing_repository_with_version_tags(temp_directory):
    component_repository = "https://github.com/fepitre/qubes-core-qrexec"
    git_branch = "builderv2-tests-2"
    subprocess.run(
        ["git", "clone", "-b", git_branch, component_repository, temp_directory],
        check=True,
        capture_output=True,
    )
    args = create_dummy_args(
        component_repository=component_repository,
        component_directory=temp_directory,
        git_branch=git_branch,
        fetch_versions_only=True,
    )
    get_and_verify_source(args)
    assert (temp_directory / ".git/FETCH_HEAD").exists()


def test_non_qubesos_repository_with_maintainer_and_signed_tag(
    temp_directory,
):
    args = create_dummy_args(
        component_directory=temp_directory,
        component_repository="https://github.com/fepitre/qubes-core-qrexec",
        git_branch="builderv2-tests-3",
        maintainers=["9FA64B92F95E706BF28E2CA6484010B5CDC576E2"],
    )
    get_and_verify_source(args)
    assert (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            cwd=str(temp_directory),
            text=True,
        ).stdout.strip()
        == "builderv2-tests-3"
    )
