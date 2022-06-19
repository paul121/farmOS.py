import os
import time

import pytest
from httpx_auth import InvalidGrantRequest

from farmOS import FarmClient
from farmOS.auth import FarmOAuth2ResourceOwnerPasswordCredentials
from tests.conftest import farmOS_testing_server

# Variables for testing.
FARMOS_HOSTNAME = os.getenv("FARMOS_HOSTNAME")
FARMOS_OAUTH_USERNAME = os.getenv("FARMOS_OAUTH_USERNAME")
FARMOS_OAUTH_PASSWORD = os.getenv("FARMOS_OAUTH_PASSWORD")


@farmOS_testing_server
def test_invalid_login():
    with pytest.raises(InvalidGrantRequest):
        auth = FarmOAuth2ResourceOwnerPasswordCredentials(
            FARMOS_HOSTNAME + '/oauth/token',
            "username",
            "password",
            client_id="farm",
            scope="farm_manager"
        )
        farm = FarmClient(
            hostname=FARMOS_HOSTNAME,
            auth=auth,
        )
        farm.info()


@farmOS_testing_server
def test_invalid_client_id():
    with pytest.raises(InvalidGrantRequest):
        auth = FarmOAuth2ResourceOwnerPasswordCredentials(
            FARMOS_HOSTNAME + '/oauth/token',
            FARMOS_OAUTH_USERNAME,
            FARMOS_OAUTH_PASSWORD,
            client_id="bad_client",
            scope="farm_manager"
        )
        farm = FarmClient(
            hostname=FARMOS_HOSTNAME,
            auth=auth,
        )
        farm.info()

@farmOS_testing_server
@pytest.mark.skip(
    reason="simple_oauth seems to accept any secret if none is configured on the client."
)
def test_invalid_client_secret():
    with pytest.raises(InvalidGrantRequest):
        auth = FarmOAuth2ResourceOwnerPasswordCredentials(
            FARMOS_HOSTNAME + '/oauth/token',
            FARMOS_OAUTH_USERNAME,
            FARMOS_OAUTH_PASSWORD,
            client_id="farm",
            client_secret="bad_pass",
            scope="farm_manager"
        )
        farm = FarmClient(
            hostname=FARMOS_HOSTNAME,
            auth=auth,
        )
        farm.info()

@farmOS_testing_server
def test_invalid_scope():
    with pytest.raises(InvalidGrantRequest):
        auth = FarmOAuth2ResourceOwnerPasswordCredentials(
            FARMOS_HOSTNAME + '/oauth/token',
            FARMOS_OAUTH_USERNAME,
            FARMOS_OAUTH_PASSWORD,
            client_id="farm",
            scope="bad_scope",
        )
        farm = FarmClient(
            hostname=FARMOS_HOSTNAME,
            auth=auth,
        )
        farm.info()


@farmOS_testing_server
@pytest.mark.skip(reason="Not implemented yet.")
def test_valid_login(test_farm):
    token = test_farm.authorize(
        username=FARMOS_OAUTH_USERNAME, password=FARMOS_OAUTH_PASSWORD
    )

    assert "access_token" in token
    assert "refresh_token" in token
    assert "expires_at" in token
    assert "expires_in" in token

    # Sleep until the token expires.
    time.sleep(token["expires_in"] + 1)

    # Make a request that will trigger a refresh.
    # Ensure the request is still authenticated.
    info = test_farm.info()
    assert "meta" in info
    assert "links" in info["meta"]
    assert "me" in info["meta"]["links"]
