from google.cloud import firestore


default_profile = { "preferredLanguage": "en" }


def __document_to_dict(doc):
    if not doc.exists:
        return None
    doc_dict = doc.to_dict()
    doc_dict['id'] = doc.id
    return doc_dict


def read(email):
    """
    Return a profile by email.
    """

    db = firestore.Client()

    # retrieve a profile from the database by ID
    profile_ref = db.collection("profiles").document(email)

    profile_dict = __document_to_dict(profile_ref.get())

    # return empty dictionary if no profile
    if profile_dict is None:
        profile_dict = default_profile.copy()

    return profile_dict


def read_entry(email, key, default_value=''):
    """
    Return a profile entry by email and key.
    """

    profile_dict = read(email)
    return profile_dict.get(key, default_value)


def update(data, email):
    """
    Update a profile, and return the updated profile's details.
    """

    db = firestore.Client()

    # update profile in database
    profile_ref = db.collection("profiles").document(email)
    profile_ref.set(data)

    return __document_to_dict(profile_ref.get())

