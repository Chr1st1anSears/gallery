from __future__ import absolute_import

import datetime
import os

from flask import current_app
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

from google.cloud import storage


def _check_extension(filename, allowed_extensions):
    """
    Validates that the filename's extension is allowed.
    """
    _, ext = os.path.splitext(filename)
    if (ext.replace('.', '') not in allowed_extensions):
        raise BadRequest(
            '{0} has an invalid name or extension'.format(filename))


def _safe_filename(filename):
    """
    Generates a safe filename that is unlikely to collide with existing
    objects in Cloud Storage.

    filename.ext is transformed into filename-YYYY-MM-DD-HHMMSS.ext
    """
    filename = secure_filename(filename)
    date = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
    basename, extension = filename.rsplit('.', 1)
    return "{0}-{1}.{2}".format(basename, date, extension)


def upload_file(file_stream, filename, content_type):
    """
    Uploads a file to a given Cloud Storage bucket and returns the public url
    to the new object.
    """
    _check_extension(filename, current_app.config['ALLOWED_EXTENSIONS'])
    filename = _safe_filename(filename)

    # build the name of the bucket
    bucket_name = os.getenv('GOOGLE_CLOUD_PROJECT') + '-photos'

    client = storage.Client()

    # create a bucket object
    bucket = client.bucket(bucket_name)

    # create an object in the bucket for the specified path
    blob = bucket.blob(filename)

    # upload the contents of the string into the object
    blob.upload_from_string(
        file_stream,
        content_type=content_type)

    # get the public URL for the object, which is used for storing a reference
    # to the image in the database and displaying the image in the app
    url = blob.public_url

    return url


def upload_image(img):
    """
    Upload the user-uploaded file to Cloud Storage and retrieve its
    publicly accessible URL.
    """
    if not img:
        return None

    public_url = upload_file(
        img.read(),
        img.filename,
        img.content_type
    )

    return public_url

