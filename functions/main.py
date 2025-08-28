# Welcome to Cloud Functions for Firebase for Python!
# To learn more about Cloud Functions, check out the documentation:
# https://firebase.google.com/docs/functions/python

from firebase_admin import initialize_app, firestore
from firebase_functions import https_fn

# Initialize the Firebase Admin SDK
initialize_app()

@https_fn.on_call()
def getphotos(req: https_fn.Request) -> https_fn.Response:
    """
    A callable function that fetches all photo documents from Firestore.
    """
    # Verify that the user is authenticated.
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.Code.UNAUTHENTICATED,
            message="Authentication required."
        )

    try:
        db = firestore.client()
        
        # Retrieve all documents from the "photos" collection
        docs = db.collection("photos").order_by("description").stream()

        # Prepare the list of photos to return
        photos = []
        for doc in docs:
            photo_data = doc.to_dict()
            photo_data['id'] = doc.id
            photos.append(photo_data)
        
        print(f"Returning {len(photos)} photos.")
        return photos

    except Exception as e:
        print(f"Error fetching photos: {e}")
        raise https_fn.HttpsError(
            code=https_fn.Code.INTERNAL,
            message="An error occurred while fetching photos."
        )