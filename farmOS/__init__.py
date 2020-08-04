import logging
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from .session import OAuthSession
from .client import LogAPI, AssetAPI, TermAPI, AreaAPI
from .config import ClientConfig

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class farmOS:

    """Create a new farmOS instance.

    Keyword Arguments:
    hostname - the farmOS hostname (without protocol)
    username - the farmOS username
    password - the farmOS user's password

    Attributes:
    session - an APISession object that handles HTTP requests

    """

    def __init__(self,
                 hostname,
                 client_id='farm',
                 client_secret=None,
                 scope='user_access',
                 token=None,
                 config=None,
                 config_file=None,
                 profile_name=None,
                 token_updater=None):

        logger.debug('Creating farmOS client.')

        # Start a list of config files.
        config_file_list = ['farmos_default_config.cfg']

        # Append additional config files.
        self.config_file = None
        if config_file is not None:
            if isinstance(config_file, str):
                logger.debug('Using config file: %s', config_file)
                config_file_list.append(config_file)
                self.config_file = config_file
            else:
                raise Exception("Config file must be a string.")

        # Check for a provided configuration object.
        if isinstance(config, ClientConfig):
            logger.debug('Using provided ClientConfig object.')
            self.config = config
        elif config is not None and not isinstance(config, ClientConfig):
            raise Exception("Config is not a ClientConfig object.")
        # Create a new object if none is provided.
        elif config is None:
            logger.debug('No ClientConfig object provided, using defaults.')
            self.config = ClientConfig(profile_name=profile_name)

        # Read config files.
        self.config.read(config_file_list)
        logger.debug('Loaded config files: %s', config_file_list)

        # Use a profile if provided.
        self.profile = None
        self.profile_name = "DEFAULT"
        if profile_name is not None:
            self.use_profile(profile_name, create_profile=True)
            logger.debug('Using profile name "%s"', profile_name)

        # Load the config boolean for development mode.
        self.development = self.config.getboolean(self.profile_name, "development", fallback=False)
        if self.development:
            logger.warning('Development mode enabled.')

        # Allow authentication over HTTP in development mode
        # or if the oauth_insecure_transport config is enabled.
        oauth_insecure_transport = self.config.getboolean(self.profile_name,
                                                          "oauthlib_insecure_transport",
                                                          fallback=False)
        if oauth_insecure_transport:
            logger.warning('OAuth Insecure Transport enabled in configuration.')

        if self.development or oauth_insecure_transport:
            import os
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            logger.warning('OAuth Insecure Transport is enabled.')

        # Load the token updater function.
        # Default to simple token_saver to save tokens to config.
        self.token_updater = self.save_token
        if token_updater is not None:
            logger.debug('Using provided token_updater utility.')
            self.token_updater = token_updater

        self.session = None

        if hostname is not None:
            valid_schemes = ["http", "https"]
            default_scheme = "http" if self.development else "https"
            parsed_url = urlparse(hostname)

            # Validate the hostname.
            # Add a default scheme if not provided.
            if not parsed_url.scheme:
                parsed_url = parsed_url._replace(scheme=default_scheme)
                logger.debug('No scheme provided. Using %s', default_scheme)

            # Check for a valid scheme.
            if parsed_url.scheme not in valid_schemes:
                raise Exception("Not a valid scheme.")

            # If not netloc was provided, it was probably parsed as the path.
            if not parsed_url.netloc and parsed_url.path:
                parsed_url = parsed_url._replace(netloc=parsed_url.path)
                parsed_url = parsed_url._replace(path='')

            # Check for netloc.
            if not parsed_url.netloc:
                raise Exception("Invalid hostname. Must have netloc.")

            # Don't allow path, params, or query.
            if parsed_url.path or parsed_url.params or parsed_url.query:
                raise Exception("Hostname cannot include path and query parameters.")

            # Build the url again to include changes.
            hostname = urlunparse(parsed_url)
            logger.debug('Complete hostname configured as %s', hostname)

            # Save the hostname in the config.
            self.config[self.profile_name]["hostname"] = hostname

        else:
            raise Exception("No hostname provided and could not be loaded from config.")

        # Check if we have a token
        has_token = False
        if token is not None:
            has_token = True
        elif self.profile and 'access_token' in dict(self.profile):
            has_token = True

        logger.debug('Creating an OAuth Session...')
        token_url = self.config.get(self.profile_name, "oauth_token_url")

        # Load saved Authentication Profile from config.
        if token is None and self.has_profile():
            logger.debug('Loading Authentication Profile from config.')

            # Save OAuth Client ID to config.
            if client_id is not None:
                self.config[self.profile_name]["oauth_client_id"] = client_id
            if client_secret is not None:
                self.config[self.profile_name]["oauth_client_secret"] = client_secret
            if scope is not None:
                self.config[self.profile_name]["oauth_scope"] = scope

            # Initialize an empty token dict.
            token = {}

            if 'access_token' in self.config[profile_name]:
                token['access_token'] = self.config[profile_name]['access_token']

            if 'refresh_token' in self.config[profile_name]:
                token['refresh_token'] = self.config[profile_name]['refresh_token']

            if 'expires_at' in self.config[profile_name]:
                token['expires_at'] = self.config[profile_name]['expires_at']

        # Check the token expiration time.
        if token is not None and 'expires_at' in token:
            # Create datetime objects for comparison.
            now = datetime.now()
            expiration_time = datetime.fromtimestamp(float(token['expires_at']))

            # Calculate seconds until expiration.
            timedelta = expiration_time - now
            expires_in = timedelta.total_seconds()

            # Update the token expires_in value
            token['expires_in'] = expires_in

            # Unset the 'expires_at' key.
            token.pop('expires_at')

        logger.debug('Creating OAuth Session from existing token.')

        # Create an OAuth Session
        self.session = OAuthSession(hostname=hostname,
                                    client_id=client_id,
                                    client_secret=client_secret,
                                    scope=scope,
                                    token=token,
                                    token_url=token_url,
                                    token_updater=self.token_updater)

        self._client_id = client_id
        self._client_secret = client_secret

        if self.session is None:
            raise Exception("Could not create a session object. Supply authentication credentials when "
                            "initializing a farmOS Client.")

        self.log = LogAPI(self.session)
        self.asset = AssetAPI(self.session)
        self.area = AreaAPI(self.session)
        self.term = TermAPI(self.session)

    def authorize(self, username=None, password=None, scope='user_access'):
        """Authorize with the farmOS server. """
        return self.session.authorize(username, password, scope)

    def info(self, path='farm.json'):
        """Retrieve info about the farmOS instance"""
        logger.debug('Retrieving farmOS server info.')
        response = self.session.http_request(path)
        if response.status_code == 200:
            return response.json()

        return []

    def save_token(self, token):
        """Save an OAuth Token to config for later use.

        This method accepts an OAuth token and saves values to the Authentication
        section of the farm.config ClientConfig object. It is primarily used as
        a callback for the requests-oauthlib OAuth2Session automatic token refreshing
        functionality. But this method could be used by others to supply a farmOS client
        with existing OAuth tokens to use (and persist).

        :param token: OAuth token dict.
        :return: None.
        """
        # Only save values if a profile name was defined.
        if self.has_profile():
            profile_name = self.get_profile_name()
            logger.debug('Saving new OAuth token to profile %s', profile_name)

            if 'access_token' in token:
                self.config[self.profile_name]["access_token"] = token['access_token']

            if 'expires_in' in token:
                # token['expires_in'] is an int, the access_token lifetime.
                # Must be saved as a string in the config.
                self.config[self.profile_name]["expires_in"] = str(token['expires_in'])

            if 'token_type' in token:
                self.config[self.profile_name]["token_type"] = token['token_type']

            if 'refresh_token' in token:
                self.config[self.profile_name]["refresh_token"] = token['refresh_token']

            if 'expires_at' in token:
                # token['expires_at'] is a float, the access_token expiration time.
                # requests-oauthlib generates this value as
                #       expires_at = time.time() + expires_in
                # Must be saved as a string in the config.
                self.config[self.profile_name]["expires_at"] = str(token['expires_at'])

        if self.config_file is None:
            logger.debug('No profile configured. New OAuth token will not be saved to config.')
        else:
            self.config.write(path=self.config_file)

    def create_profile(self, profile_name):
        """Creates a Section for profile_name in farm.config."""
        if not self._profile_exists(profile_name):
            self.config.add_section(profile_name)
            return True
        else:
            # TODO: Write test for duplicate profile names.
            raise Exception("Profile '" + profile_name + "' already exists.")

    def has_profile(self, profile_name=None):
        """Returns True or False if the client is configured with a profile.

        Also returns whether a profile_name is found in the config.
        """
        if profile_name is not None:
            return self._profile_exists(profile_name)
        else:
            return self.profile is not None

    def get_profile_name(self):
        """Returns the current profile name."""
        if self.has_profile():
            return self.profile_name
        else:
            raise Exception("No profile being used.")

    def use_profile(self, profile_name, create_profile=False):
        """Set the authentication profile to use from farm.config."""
        profile = self._get_profile_config(profile_name)

        if profile is None:
            if create_profile is True:
                self.create_profile(profile_name)
                profile = self._get_profile_config(profile_name)
            else:
                # TODO: Write test for no profile name.
                raise Exception("Profile '" + profile_name + "' does not exist.")

        self.profile = profile
        self.profile_name = profile_name

    def _get_profile_config(self, profile_name=None):
        """Helper function that returns the current profile config, or the config or profile_name."""
        if self._profile_exists(profile_name):
            return self.config[profile_name]
        else:
            return None

    def _profile_exists(self, profile_name):
        """Helper function to check if a profile for profile_name exists."""
        if isinstance(profile_name, str):
            return self.config.has_section(profile_name)
        else:
            # TODO: Write test for invalid profile_name.
            raise Exception("profile_name not a String.")
