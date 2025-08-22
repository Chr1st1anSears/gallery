# gallerydb.py
from google.cloud import firestore

def document_to_dict(doc):
    """
    Convert Firestore document to a Python dictionary.
    """
    if not doc.exists:
        return None
    doc_dict = doc.to_dict()
    doc_dict['id'] = doc.id
    return doc_dict


def read(photo_id):
    """
    Return the details for a single photo.
    """

    db = firestore.Client()

    # retrieve a photo from the database by ID
    photo_ref = db.collection("photos").document(photo_id)
    return document_to_dict(photo_ref.get())


def create(data):
    """
    Create a new photo and return the photo details.
    """

    db = firestore.Client()

    # store photo in database
    photo_ref = db.collection("photos").document()
    photo_ref.set(data)
    return document_to_dict(photo_ref.get())


def update(data, photo_id):
    """
    Update an existing photo, and return the updated photo's details.
    """

    db = firestore.Client()

    # update photo in database
    photo_ref = db.collection("photos").document(photo_id)
    photo_ref.set(data)
    return document_to_dict(photo_ref.get())


def delete(photo_id):
    """
    Delete a photo in the database.
    """

    db = firestore.Client()

    # remove photo from database
    photo_ref = db.collection("photos").document(photo_id)
    photo_ref.delete()

    # no return required


def list():
    """
    Return a list of all photos in the database, ordered by description.
    """

    # empty list of photos
    photos = []

    db = firestore.Client()

    # get an ordered list of documents in the collection
    docs = db.collection("photos").order_by("description").stream()

    # retrieve each item in database and add to the list
    for doc in docs:
        photos.append(document_to_dict(doc))

    # return the list
    return photos