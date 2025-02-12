from typing import List, Any

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.template import QubesTemplate


class Stage:
    def __init__(
        self,
        name: str,
        config: "Config",
        components: List[QubesComponent],
        distributions: List[QubesDistribution],
        templates: List[QubesTemplate],
    ) -> None:
        self.name = name
        self.config = config

        self.plugins = PluginManager(config.get_plugins_dirs()).get_instances(
            stage=self,
            components=components,
            distributions=distributions,
            templates=templates,
            config=config,
        )

    def run(self, **kwargs: Any) -> None:
        for plugin in self.plugins:
            plugin.run(stage=self.name, **kwargs)
