import importlib
import pathlib
import shutil
import subprocess
import tempfile
from argparse import Namespace

import pytest

from qubesbuilder.common import PROJECT_PATH

module = importlib.import_module(
    "qubesbuilder.plugins.fetch.scripts.get-and-verify-source"
)
main = getattr(module, "main")


@pytest.fixture
def temp_directory():
    # Create a temporary directory
    temp_dir = pathlib.Path(tempfile.mkdtemp())
    yield temp_dir
    # Remove the temporary directory after the test
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def create_dummy_args(
    component_repository="https://github.com/qubesos/qubes-core-vchan-xen",
    component_directory=None,
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


def test_get_and_verify_source_repository(temp_directory):
    args = create_dummy_args(component_directory=temp_directory)
    main(args)
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


def test_get_and_verify_source_repository_invalid_branch(temp_directory):
    args = create_dummy_args(
        component_directory=temp_directory, git_branch="nonexistent"
    )
    with pytest.raises(subprocess.CalledProcessError) as e:
        main(args)
    assert (
        b"fatal: Remote branch nonexistent not found in upstream origin\n"
        == e.value.stderr
    )


def test_get_and_verify_source_non_qubesos_repository(temp_directory):
    args = create_dummy_args(
        component_directory=temp_directory,
        component_repository="https://github.com/fepitre/qubes-core-qrexec",
        git_branch="builderv2",
    )
    with pytest.raises(ValueError) as e:
        main(args)
    (msg,) = e.value.args
    assert msg == "---> Invalid commit 961bf3c7bd8cc5dc5335ee91afefbf7feb92c982"


def test_get_and_verify_source_non_qubesos_repository_with_maintainer_and_no_tags(
    temp_directory,
):
    args = create_dummy_args(
        component_directory=temp_directory,
        component_repository="https://github.com/fepitre/qubes-core-qrexec",
        git_branch="builderv2",
        less_secure_signed_commits_sufficient=True,
        maintainers=["9FA64B92F95E706BF28E2CA6484010B5CDC576E2"],
    )
    main(args)
    assert (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            cwd=str(temp_directory),
            text=True,
        ).stdout.strip()
        == "builderv2"
    )
