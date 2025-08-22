import os
from google.cloud import secretmanager

def get_secret(secret_id, version_id='latest'):

    # create the secret manager client
    client = secretmanager.SecretManagerServiceClient()

    # build the resource name of the secret version
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

    # access the secret version
    response = client.access_secret_version(name=name)

    # return the decoded secret
    return response.payload.data.decode('UTF-8')

