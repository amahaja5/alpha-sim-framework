from ...alpha_types import ExternalFeedConfig, ProviderRuntimeConfig
from .common import JSONFeedClient


class OddsFeedClient(JSONFeedClient):
    def __init__(self, config: ExternalFeedConfig, runtime: ProviderRuntimeConfig):
        super().__init__("odds", config, runtime)
