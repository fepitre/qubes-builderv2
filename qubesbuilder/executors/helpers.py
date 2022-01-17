from qubesbuilder.executors import ExecutorException
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.executors.local import LocalExecutor


def getExecutor(executor_type, executor_options):
    executor = None
    if executor_type in ("podman", "docker"):
        executor = ContainerExecutor(executor_type, executor_options.get("image", None))
    elif executor_type == "local":
        executor = LocalExecutor()
    if not executor:
        raise ExecutorException("Cannot determine which executor to use.")
    return executor
