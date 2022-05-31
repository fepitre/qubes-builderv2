from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.executors.qubes import QubesExecutor


def getExecutor(executor_type, executor_options):
    if executor_type in ("podman", "docker"):
        executor = ContainerExecutor(executor_type, **executor_options)
    elif executor_type == "local":
        executor = LocalExecutor(**executor_options)  # type: ignore
    elif executor_type == "qubes":
        executor = QubesExecutor(**executor_options)  # type: ignore
    else:
        raise ExecutorError("Cannot determine which executor to use.")
    return executor
