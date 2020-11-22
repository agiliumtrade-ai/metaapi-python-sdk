from ..clients.httpClient import HttpClient
from ..clients.metaApi.metaApiWebsocket_client import MetaApiWebsocketClient
from ..metaApi.provisioningProfileApi import ProvisioningProfileApi
from ..clients.metaApi.provisioningProfile_client import ProvisioningProfileClient
from ..metaApi.metatraderAccountApi import MetatraderAccountApi
from ..clients.metaApi.metatraderAccount_client import MetatraderAccountClient
from ..clients.metaApi.packetLogger import PacketLoggerOpts
from ..clients.errorHandler import ValidationException
from ..metaApi.connectionRegistry import ConnectionRegistry
from .metatraderDemoAccountApi import MetatraderDemoAccountApi
from ..clients.metaApi.metatraderDemoAccount_client import MetatraderDemoAccountClient
import re
from typing import TypedDict, Optional


class MetaApiOpts(TypedDict):
    """MetaApi options"""
    application: Optional[str]
    """Application id."""
    domain: Optional[str]
    """Domain to connect to, default is agiliumtrade.agiliumtrade.ai."""
    requestTimeout: Optional[float]
    """Timeout for socket requests in seconds."""
    connectTimeout: Optional[float]
    """Timeout for connecting to server in seconds."""
    packetOrderingTimeout: Optional[float]
    """Packet ordering timeout in seconds."""
    packetLogger: Optional[PacketLoggerOpts]
    """Packet logger options."""


class MetaApi:
    """MetaApi MetaTrader API SDK"""

    def __init__(self, token: str, opts: MetaApiOpts = None):
        """Inits MetaApi class instance.

        Args:
            token: Authorization token.
            opts: Application options.
        """
        opts: MetaApiOpts = opts or {}
        application = opts['application'] if 'application' in opts else 'MetaApi'
        domain = opts['domain'] if 'domain' in opts else 'agiliumtrade.agiliumtrade.ai'
        request_timeout = opts['requestTimeout'] if 'requestTimeout' in opts else 60
        connect_timeout = opts['connectTimeout'] if 'connectTimeout' in opts else 60
        packet_ordering_timeout = opts['packetOrderingTimeout'] if 'packetOrderingTimeout' in opts else 60
        packet_logger = opts['packetLogger'] if 'packetLogger' in opts else {}
        if not re.search(r"[a-zA-Z0-9_]+", application):
            raise ValidationException('Application name must be non-empty string consisting ' +
                                      'from letters, digits and _ only')
        http_client = HttpClient(request_timeout)
        self._metaApiWebsocketClient = MetaApiWebsocketClient(
            token, {'application': application, 'domain': domain, 'requestTimeout': request_timeout,
                    'connectTimeout': connect_timeout, 'packetLogger': packet_logger,
                    'packetOrderingTimeout': packet_ordering_timeout})
        self._provisioningProfileApi = ProvisioningProfileApi(ProvisioningProfileClient(http_client, token, domain))
        self._connectionRegistry = ConnectionRegistry(self._metaApiWebsocketClient, application)
        self._metatraderAccountApi = MetatraderAccountApi(MetatraderAccountClient(http_client, token, domain),
                                                          self._metaApiWebsocketClient, self._connectionRegistry)
        self._metatraderDemoAccountApi = MetatraderDemoAccountApi(MetatraderDemoAccountClient(http_client, token,
                                                                                              domain))

    @property
    def provisioning_profile_api(self) -> ProvisioningProfileApi:
        """Returns provisioning profile API.

        Returns:
            Provisioning profile API.
        """
        return self._provisioningProfileApi

    @property
    def metatrader_account_api(self) -> MetatraderAccountApi:
        """Returns MetaTrader account API.

        Returns:
            MetaTrader account API.
        """
        return self._metatraderAccountApi

    @property
    def metatrader_demo_account_api(self) -> MetatraderDemoAccountApi:
        """Returns MetaTrader demo account API.

        Returns:
            MetaTrader demo account API.
        """
        return self._metatraderDemoAccountApi

    def close(self):
        """Closes all clients and connections"""
        self._metaApiWebsocketClient.close()