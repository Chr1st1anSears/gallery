# main.py
from flask import current_app, Flask, redirect, render_template
from flask import request, url_for, session
import logging
from google.cloud import logging as cloud_logging
import json
import os
from urllib.parse import urlparse

import gallerydb
import storage
import secret_getter
import oauth
import translate
import profiledb

def upload_image_file(img):
    """
    Upload the user-uploaded file to Cloud Storage and retrieve its
    publicly accessible URL.
    """
    if not img:
        return None

    public_url = storage.upload_file(
        img.read(),
        img.filename,
        img.content_type
    )

    current_app.logger.info(
        'Uploaded file %s as %s.', img.filename, public_url)

    return public_url

app = Flask(__name__)
app.config.update(
    SECRET_KEY=secret_getter.get_secret('flask-secret-key'),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    ALLOWED_EXTENSIONS=set(['png', 'jpg', 'jpeg', 'gif']),
    CLIENT_SECRETS=json.loads(secret_getter.get_secret('gallery-client-secrets')), # RECOMMENDATION: Rename secret
    SCOPES=[
        'openid',
        'https://www.googleapis.com/auth/contacts.readonly',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
    ],
    EXTERNAL_HOST_URL=os.getenv('EXTERNAL_HOST_URL'),
)

app.debug = True
app.testing = False

# configure logging
if not app.testing:
    logging.basicConfig(level=logging.INFO)

    # attach a Cloud Logging handler to the root logger
    client = cloud_logging.Client()
    client.setup_logging()

def log_request(req):
    """
    Log request
    """
    current_app.logger.info('REQ: {0} {1}'.format(req.method, req.url))

# build a mapping of language codes to display names
display_languages = {}
for l in translate.get_languages():
    display_languages[l.language_code] = l.display_name


def logout_session():
    """
    Clears known session items.
    """
    session.pop('credentials', None)
    session.pop('user', None)
    session.pop('state', None)
    session.pop('error_message', None)
    session.pop('login_return', None)
    return


def external_url(url):
    """
    Cloud Shell routes https://8080-***/ to localhost over http
    This function replaces the localhost host with the configured scheme + hostname
    """
    external_host_url = current_app.config['EXTERNAL_HOST_URL']
    if external_host_url is None:
        # force https
        if url.startswith('http://'):
            url = f"https://{url[7:]}"
        return url

    # replace the scheme and hostname with the external host URL
    parsed_url = urlparse(url)
    replace_string = f"{parsed_url.scheme}://{parsed_url.netloc}"
    new_url = f"{external_host_url}{url[len(replace_string):]}"
    return new_url


@app.route('/error')
def error():
    """
    Display an error.
    """

    log_request(request)

    if "error_message" not in session:
        return redirect(url_for('.list'))

    # render error
    return render_template('error.html', error_message=session.pop('error_message', None))


@app.route("/login")
def login():
    """
    Login if not already logged in.
    """
    log_request(request)

    if not "credentials" in session:
        # need to log in

        current_app.logger.info('logging in')

        # get authorization URL
        authorization_url, state = oauth.authorize(
            callback_uri=external_url(url_for('oauth2callback', _external=True)),
            client_config=current_app.config['CLIENT_SECRETS'],
            scopes=current_app.config['SCOPES'])

        current_app.logger.info(f"authorization_url={authorization_url}")

        # save state for verification on callback
        session['state'] = state

        return redirect(authorization_url)

    # already logged in
    return redirect(session.pop('login_return', url_for('.list')))


@app.route("/oauth2callback")
def oauth2callback():
    """
    Callback destination during OAuth process.
    """
    log_request(request)

    # check for error, probably access denied by user
    error = request.args.get('error', None)
    if error:
        session['error_message'] = f"{error}"
        return redirect(url_for('.error'))

    # handle the OAuth2 callback
    credentials, user_info = oauth.handle_callback(
        callback_uri=external_url(url_for('oauth2callback', _external=True)),
        client_config=current_app.config['CLIENT_SECRETS'],
        scopes=current_app.config['SCOPES'],
        request_url=external_url(request.url),
        stored_state=session.pop('state', None),
        received_state=request.args.get('state', ''))

    session['credentials'] = credentials
    session['user'] = user_info
    current_app.logger.info(f"user_info={user_info}")

    return redirect(session.pop('login_return', url_for('.list')))


@app.route("/logout")
def logout():
    """
    Log out and return to root page.
    """
    log_request(request)

    logout_session()
    return redirect(url_for('.list'))


@app.route('/')
def list():
    """
    Display all photos.
    """
    log_request(request)

    # get list of photos
    photos = gallerydb.list()

    # render list of photos
    return render_template('list.html', photos=photos)


@app.route('/photos/<photo_id>')
def view(photo_id):
    """
    View the details of a specified photo.
    """
    log_request(request)

    # retrieve a specific photo
    photo = gallerydb.read(photo_id)
    current_app.logger.info(f"photo={photo}")

    # defaults if logged out
    description_language = None
    translation_language = None
    translated_text = ''
    if photo['description'] and "credentials" in session:
        preferred_language = session.get('preferred_language', 'en')

        # translate description
        translation = translate.translate_text(
            text=photo['description'],
            target_language_code=preferred_language,
        )
        description_language = display_languages[translation.detected_language_code]
        translation_language = display_languages[preferred_language]
        translated_text = translation.translated_text

    # render photo details
    return render_template('view.html', photo=photo,
        translated_text=translated_text,
        description_language=description_language,
        translation_language=translation_language,
    )


@app.route('/photos/add', methods=['GET', 'POST'])
def add():
    """
    If GET, show the form to collect details of a new photo.
    If POST, create the new photo based on the specified form.
    """
    log_request(request)

    # must be logged in
    if "credentials" not in session:
        session['login_return'] = url_for('.add')
        return redirect(url_for('.login'))

    # Save details if form was posted
    if request.method == 'POST':

        # get photo details from form
        data = request.form.to_dict(flat=True)

        image_url = upload_image_file(request.files.get('image'))

        # If an image was uploaded, update the data to point to the image.
        if image_url:
            data['imageUrl'] = image_url

        # add photo
        photo = gallerydb.create(data)

        # render photo details
        return redirect(url_for('.view', photo_id=photo['id']))

    # render form to add photo
    return render_template('form.html', action='Add', photo={})


@app.route('/photos/<photo_id>/edit', methods=['GET', 'POST'])
def edit(photo_id):
    """
    If GET, show the form to collect updated details for a photo.
    If POST, update the photo based on the specified form.
    """
    log_request(request)

    # must be logged in
    if "credentials" not in session:
        session['login_return'] = url_for('.edit', photo_id=photo_id)
        return redirect(url_for('.login'))

    # read existing photo details
    photo = gallerydb.read(photo_id)

    # Save details if form was posted
    if request.method == 'POST':

        # get photo details from form
        data = request.form.to_dict(flat=True)

        image_url = upload_image_file(request.files.get('image'))

        # If an image was uploaded, update the data to point to the image.
        if image_url:
            data['imageUrl'] = image_url

        # update photo
        photo = gallerydb.update(data, photo_id)

        # render photo details
        return redirect(url_for('.view', photo_id=photo['id']))

    # render form to update photo
    return render_template('form.html', action='Edit', photo=photo)


@app.route('/photos/<photo_id>/delete')
def delete(photo_id):
    """
    Delete the specified photo and return to the photo list.
    """
    log_request(request)

    # must be logged in
    if "credentials" not in session:
        session['login_return'] = url_for('.view', photo_id=photo_id)
        return redirect(url_for('.login'))

    # delete photo
    gallerydb.delete(photo_id)

    # render list of remaining photos
    return redirect(url_for('.list'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """
    If GET, show the form to collect updated details for the user profile.
    If POST, update the profile based on the specified form.
    """
    log_request(request)

    # must be logged in
    if "credentials" not in session:
        session['login_return'] = url_for('.profile')
        return redirect(url_for('.login'))

    # read existing profile
    email = session['user']['email']
    profile = profiledb.read(email)

    # Save details if form was posted
    if request.method == 'POST':

        # get photo details from form
        data = request.form.to_dict(flat=True)

        # update profile
        profiledb.update(data, email)
        session['preferred_language'] = data['preferredLanguage']

        # return to root
        return redirect(url_for('.list'))

    # render form to update profile
    return render_template('profile.html', action='Edit',
        profile=profile, languages=translate.get_languages())


# this is only used when running locally
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)