import google.oauth2.credentials
import google_auth_oauthlib.flow
from uuid import uuid4
from googleapiclient.discovery import build
from werkzeug.exceptions import Unauthorized

def _credentials_to_dict(credentials):
    """
    Convert credentials mapping (object) into a dictionary.
    """
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'id_token': credentials.id_token,
    }


def authorize(callback_uri, client_config, scopes):
    """
    Builds the URL that will be used for redirection to Google
    to start the OAuth flow.
    """

    # specify the flow configuration details
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config=client_config,
        scopes=scopes,
    )
    flow.redirect_uri = callback_uri

    # create a random state
    state = str(uuid4())

    # get the authorization URL
    authorization_url, state = flow.authorization_url(
        # offline access allows access token refresh without reprompting the user
        # using online here to force log in
        access_type='online',
        state=state,
        prompt='consent',
        include_granted_scopes='false',
    )

    return authorization_url, state

def handle_callback(callback_uri, client_config, scopes, request_url, stored_state, received_state):
    """
    Fetches credentials using the authorization code in the request URL,
    and retrieves user information for the logged-in user.
    """

    # validate received state
    if received_state != stored_state:
        raise Unauthorized(f'Invalid state parameter: received={received_state} stored={stored_state}')

    # specify the flow configuration details
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config=client_config,
        scopes=scopes
    )
    flow.redirect_uri = callback_uri

    # get a token using the details in the request
    flow.fetch_token(authorization_response=request_url)
    credentials = flow.credentials

    oauth2_client = build('oauth2','v2',credentials=credentials, cache_discovery=False)
    user_info = oauth2_client.userinfo().get().execute()

    return _credentials_to_dict(credentials), user_info

