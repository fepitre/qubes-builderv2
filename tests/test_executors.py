import tempfile
from pathlib import Path, PurePath

import pytest

from qubesbuilder.executors import ExecutorException
from qubesbuilder.executors.container import ContainerExecutor


def test_container_simple():
    executor = ContainerExecutor("docker", "fedora:latest")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a local file with some content
        hello = Path(temp_dir) / "hello.md"
        with open(hello, "w") as f:
            f.write("Hello!\n")

        # Copy-in the previously created local file
        copy_in = [
            (hello, PurePath("/tmp/hello.md"))
        ]

        # Copy-out the modified file
        copy_out = [
            (PurePath("/tmp/hello.md"), hello)
        ]
        # Command that appends a line to the file
        cmd = ["/bin/bash", "-c", "echo It works! >> /tmp/hello.md"]

        # Execute the command
        executor.run(cmd, copy_in, copy_out)

        # Read modified file that has been copied out from the container
        with open(hello) as f:
            data = f.read()

        # Check expected content
        assert data == "Hello!\nIt works!\n"


def test_container_not_running():
    with pytest.raises(ExecutorException) as e:
        ContainerExecutor("docker", "fedora:latest", base_url="tcp://127.0.0.1:1234")
    msg = "Cannot connect to container client."
    assert str(e.value) == msg


def test_container_unknown_image():
    with pytest.raises(ExecutorException) as e:
        ContainerExecutor("docker", "fedora-unknown:latest")
    msg = "Cannot find fedora-unknown:latest."
    assert str(e.value) == msg
