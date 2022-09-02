import sys
from pathlib import Path

from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.executors.qubes import QubesExecutor
from qubesbuilder.plugins import PluginError


def get_executor(executor_type, executor_options):
    if executor_type in ("podman", "docker"):
        executor = ContainerExecutor(executor_type, **executor_options)
    elif executor_type == "local":
        executor = LocalExecutor(**executor_options)  # type: ignore
    elif executor_type == "qubes":
        executor = QubesExecutor(**executor_options)  # type: ignore
    else:
        raise ExecutorError("Cannot determine which executor to use.")
    return executor


def _load_modules(path):
    loaded_modules = []
    modules = Path(path).iterdir()
    module_pattern = "qubesbuilder.plugins.%s"

    for directory in modules:
        if not (directory / "__init__.py").exists():
            continue
        mod_name = directory.name
        if mod_name == "plugins":
            continue
        try:
            module = sys.modules.get(module_pattern % mod_name)
            if not module:
                __import__(module_pattern % mod_name)
                module = sys.modules[module_pattern % mod_name]
            loaded_modules.append(module)
        except ImportError as e:
            raise PluginError(str(e)) from e

    return loaded_modules


def _get_plugins(attr, **kwargs):
    if not kwargs.get("plugins_dir", None):
        raise PluginError("Please provide plugins directory.")
    modules = _load_modules(kwargs.get("plugins_dir"))
    plugins = []
    for m in modules:
        if not hasattr(m, attr):
            continue
        for p in getattr(m, attr):
            plugins.append(p)

    instances = []
    for p in plugins:
        instances += p.from_args(
            **kwargs,
        )

    return sorted(instances, key=lambda x: x.priority)


def get_plugins(**kwargs):
    return _get_plugins("PLUGINS", **kwargs)


def get_template_plugins(**kwargs):
    return _get_plugins("TEMPLATE_PLUGINS", **kwargs)
