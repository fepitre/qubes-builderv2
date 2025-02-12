from typing import List, Any

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.template import QubesTemplate


class Job:
    def __init__(self, config):
        self.config = config

    def run(self):
        pass
