from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.executors.qubes import QubesExecutor


def getExecutor(executor_type, executor_options):
    executor = None
    if executor_type in ("podman", "docker"):
        executor = ContainerExecutor(executor_type, executor_options.get("image", None))
    elif executor_type == "local":
        executor = LocalExecutor()
    elif executor_type == "qubes":
        executor = QubesExecutor(executor_options.get("dispvm", None))
    if not executor:
        raise ExecutorError("Cannot determine which executor to use.")
    return executor
