import importlib.util
from pathlib import Path
from typing import List, Dict

from qubesbuilder.exc import EntityError, PluginManagerError


class PluginEntity:
    def __init__(self, path: Path):
        self.directory = path.parent
        if path.name == "__init__.py":
            self.name = self.directory.name
        else:
            self.name = path.name.replace(".py", "")
        if self.name.startswith("qubes-"):
            self.name = self.name[6:]
        self.name = self.name.replace("-", "_")
        self.fullname = f"qubesbuilder.plugins.{self.name}"
        try:
            spec = importlib.util.spec_from_file_location(self.fullname, path)
            if not spec:
                raise EntityError("Cannot get module spec.")
            self.module = importlib.util.module_from_spec(spec)
            if not spec.loader:
                raise EntityError("Cannot get module from spec.")
            spec.loader.exec_module(self.module)
        except ImportError as e:
            raise EntityError(str(e)) from e


class PluginManager:
    def __init__(self, directories: List[Path]):
        self._directories = directories
        self._entities: Dict[str, PluginEntity] = {}

    def _get_plugin_entities(self):
        entities = {}
        for directory in self._directories:
            modules = Path(directory).iterdir()
            for module in modules:
                if module.is_dir():
                    module_path = module / "__init__.py"
                    if not module_path.exists():
                        continue
                    entity = PluginEntity(module_path)
                elif module.name.endswith(".py"):
                    entity = PluginEntity(module)
                else:
                    continue
                # Ensure module name are uniq
                if entity.name in entities:
                    raise PluginManagerError(
                        f"Conflicting module name detected: '{entity.name}'."
                    )
                entities[entity.name] = entity

        return entities

    def _get_instances_with_attr(self, module_attr, **kwargs):
        # Ensure plugin class name are uniq
        plugin_names = []
        for entity in self.entities.values():
            if not hasattr(entity.module, module_attr):
                continue
            plugin_names += [c.__name__ for c in getattr(entity.module, module_attr)]

        if len(set(plugin_names)) != len(plugin_names):
            raise PluginManagerError(f"Conflicting plugin name detected.")

        instances = []
        for entity in self.entities.values():
            if not hasattr(entity.module, module_attr):
                continue
            for plugin in getattr(entity.module, module_attr):
                instances += plugin.from_args(
                    **kwargs,
                )
        return instances

    @property
    def entities(self):
        if not self._entities:
            self._entities = self._get_plugin_entities()
        return self._entities

    def get_component_instances(self, **kwargs):
        return self._get_instances_with_attr("PLUGINS", manager=self, **kwargs)

    def get_template_instances(self, **kwargs):
        return self._get_instances_with_attr("TEMPLATE_PLUGINS", manager=self, **kwargs)
