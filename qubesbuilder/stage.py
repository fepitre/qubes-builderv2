from typing import List, Any


class Stage:
    def __init__(
        self,
        name: str,
        config: "Config",
        plugins: List["Plugin"] = None,
    ) -> None:
        self.name = name
        self.config = config
        self.plugins = plugins or []

    def run(self, **kwargs: Any) -> None:
        for plugin in self.plugins:
            plugin.run(stage=self.name, **kwargs)
