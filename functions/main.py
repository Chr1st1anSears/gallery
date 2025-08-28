# Welcome to Cloud Functions for Firebase for Python!
# To learn more about Cloud Functions, check out the documentation:
# https://firebase.google.com/docs/functions/python

from firebase_admin import initialize_app, firestore
from firebase_functions import https_fn, options

# This is a new import for our new function
from firebase_functions.params import StringParam

# Initialize the Firebase Admin SDK
initialize_app()

# Set the region for all functions in this file
options.set_global_options(region="us-central1")


@https_fn.on_call()
def getphotos(req: https_fn.Request) -> https_fn.Response:
    """Fetches all photo documents from Firestore."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.Code.UNAUTHENTICATED, message="Authentication required.")
    
    try:
        db = firestore.client()
        docs = db.collection("photos").order_by("description").stream()
        photos = []
        for doc in docs:
            photo_data = doc.to_dict()
            photo_data['id'] = doc.id
            photos.append(photo_data)
        
        print(f"Returning {len(photos)} photos.")
        return photos
    except Exception as e:
        print(f"Error fetching photos: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred while fetching photos.")


# --- NEW FUNCTION ---
@https_fn.on_call()
def addphoto(req: https_fn.Request) -> https_fn.Response:
    """
    Receives photo metadata from the client and saves it to a new
    document in the 'photos' collection in Firestore.
    """
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.Code.UNAUTHENTICATED, message="Authentication required.")
    
    try:
        # Get data sent from the front-end
        data = req.data
        print(f"Received photo data: {data}")
        
        # Prepare the data for Firestore
        photo_doc = {
            'imageUrl': data.get('imageUrl'),
            'description': data.get('description'),
            'peopleInPhoto': data.get('peopleInPhoto'),
            'dateTaken': data.get('dateTaken'),
            'uploaderUid': req.auth.uid # Add the uploader's ID for security/auditing
        }
        
        db = firestore.client()
        # Add a new document to the 'photos' collection
        db.collection("photos").add(photo_doc)
        
        return {"status": "success", "message": "Photo details saved."}

    except Exception as e:
        print(f"Error saving photo details: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred while saving photo details.")