from ...alpha_types import ExternalFeedConfig, ProviderRuntimeConfig
from .common import JSONFeedClient


class InjuryNewsFeedClient(JSONFeedClient):
    def __init__(self, config: ExternalFeedConfig, runtime: ProviderRuntimeConfig):
        super().__init__("injury_news", config, runtime)
