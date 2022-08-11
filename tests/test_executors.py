import os.path
import tempfile
from pathlib import Path, PurePath

import pytest

from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.executors.qubes import QubesExecutor


def test_container_simple():
    executor = ContainerExecutor("docker", "fedora:latest", user="root", group="root")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a local file with some content
        hello = Path(temp_dir) / "hello.md"
        with open(hello, "w") as f:
            f.write("Hello!\n")

        # Copy-in the previously created local file
        copy_in = [(hello, PurePath("/tmp"))]

        # Copy-out the modified file
        copy_out = [(PurePath("/tmp/hello.md"), Path(temp_dir))]
        # Command that appends a line to the file
        cmd = ["echo It works! >> /tmp/hello.md"]

        # Execute the command
        executor.run(cmd, copy_in, copy_out)

        # Read modified file that has been copied out from the container
        with open(hello) as f:
            data = f.read()

        # Check expected content
        assert data == "Hello!\nIt works!\n"


def test_container_not_running():
    with pytest.raises(ExecutorError) as e:
        ContainerExecutor("docker", "fedora:latest", base_url="tcp://127.0.0.1:1234")
    msg = "Cannot connect to container client."
    assert str(e.value) == msg


def test_container_unknown_image():
    with pytest.raises(ExecutorError) as e:
        ContainerExecutor("docker", "fedora-unknown:latest")
    msg = "Cannot find fedora-unknown:latest."
    assert str(e.value) == msg


def test_local_simple():
    executor = LocalExecutor()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a local file with some content
        hello = Path(temp_dir) / "hello.md"
        with open(hello, "w") as f:
            f.write("Hello!\n")

        # Copy-in the previously created local file
        copy_in = [(hello, Path("/tmp"))]

        # Copy-out the modified file
        copy_out = [(Path("/tmp/hello.md"), Path(temp_dir))]
        # Command that appends a line to the file
        cmd = ["echo It works! >> /tmp/hello.md"]

        # Execute the command
        executor.run(cmd, copy_in, copy_out)

        # Read modified file that has been copied out from the container
        with open(hello) as f:
            data = f.read()

        # Check expected content
        assert data == "Hello!\nIt works!\n"


@pytest.mark.skipif(
    not os.path.exists("/var/run/qubes/this-is-appvm"),
    reason="Qubes Admin VM is required!",
)
def test_qubes_simple():
    executor = QubesExecutor("qubes-builder-dvm")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a local file with some content
        hello = Path(temp_dir) / "hello.md"
        with open(hello, "w") as f:
            f.write("Hello!\n")

        # Copy-in the previously created local file
        copy_in = [(hello, PurePath("/tmp"))]

        # Copy-out the modified file
        copy_out = [(PurePath("/tmp/hello.md"), Path(temp_dir))]
        # Command that appends a line to the file
        cmd = ["echo It works! >> /tmp/hello.md"]

        # Execute the command
        executor.run(cmd, copy_in, copy_out)

        # Read modified file that has been copied out from the container
        with open(hello) as f:
            data = f.read()

        # Check expected content
        assert data == "Hello!\nIt works!\n"


@pytest.mark.skipif(
    not os.path.exists("/var/run/qubes/this-is-appvm"),
    reason="Qubes Admin VM is required!",
)
def test_qubes_environment():
    executor = QubesExecutor("qubes-builder-dvm")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a local file with some content
        hello = Path(temp_dir) / "hello.md"
        with open(hello, "w") as f:
            f.write("Hello!\n")

        # Copy-in the previously created local file
        copy_in = [(hello, PurePath("/tmp"))]

        # Copy-out the modified file
        copy_out = [(PurePath("/tmp/hello.md"), Path(temp_dir))]
        # Command that appends a line to the file
        cmd = [
            "echo ${MY_ANSWER} >> /tmp/hello.md",
            "echo ${MY_QUESTION} >> /tmp/hello.md",
        ]

        # Execute the command
        executor.run(
            cmd,
            copy_in,
            copy_out,
            environment={"MY_ANSWER": "Hi there!", "MY_QUESTION": "How are you?"},
        )

        # Read modified file that has been copied out from the container
        with open(hello) as f:
            data = f.read()

        # Check expected content
        assert data == "Hello!\nHi there!\nHow are you?\n"
