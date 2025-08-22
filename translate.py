import os
from google.cloud import translate

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
PARENT = f"projects/{PROJECT_ID}"

supported_languages = None

def get_languages():
    """
    Gets the list of supported languages.
    """

    # use the global variable
    global supported_languages

    # retrieve supported languages if not previously retrieved
    if not supported_languages:
        client = translate.TranslationServiceClient()

        response = client.get_supported_languages(
            parent=PARENT,
            display_language_code='en',
        )

        supported_languages = response.languages

    return supported_languages


def detect_language(text):
    """
    Detect the language of the supplied text.
    Returns the most likely language.
    """

    client = translate.TranslationServiceClient()

    response = client.detect_language(
        parent=PARENT,
        content=text,
    )

    return response.languages[0]


def translate_text(text, target_language_code):
    """
    Translate the text to the target language.
    """

    client = translate.TranslationServiceClient()

    response = client.translate_text(
        parent=PARENT,
        contents=[text],
        target_language_code=target_language_code,
    )

    return response.translations[0]

