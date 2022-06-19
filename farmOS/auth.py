import httpx
from httpx_auth import OAuth2ResourceOwnerPasswordCredentials


# Extend class to remove basic auth.
class FarmOAuth2ResourceOwnerPasswordCredentials(OAuth2ResourceOwnerPasswordCredentials):
    def _configure_client(self, client: httpx.Client):
        client.timeout = self.timeout
