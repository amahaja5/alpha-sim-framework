from ...alpha_types import ExternalFeedConfig, ProviderRuntimeConfig
from .common import JSONFeedClient


class WeatherFeedClient(JSONFeedClient):
    def __init__(self, config: ExternalFeedConfig, runtime: ProviderRuntimeConfig):
        super().__init__("weather", config, runtime)
