from ...alpha_types import ExternalFeedConfig, ProviderRuntimeConfig
from .common import JSONFeedClient


class NextGenStatsFeedClient(JSONFeedClient):
    def __init__(self, config: ExternalFeedConfig, runtime: ProviderRuntimeConfig):
        super().__init__("nextgenstats", config, runtime)
