# Welcome to Cloud Functions for Firebase for Python!
# To learn more about Cloud Functions, check out the documentation:
# https://firebase.google.com/docs/functions/python

from firebase_admin import initialize_app, firestore
from firebase_functions import https_fn, options

# This is a new import for our new function
from firebase_functions.params import StringParam
from firebase_admin import initialize_app, firestore, storage
# Initialize the Firebase Admin SDK
initialize_app()

# Set the region for all functions in this file
options.set_global_options(region="us-central1")


@https_fn.on_call()
def getphotos(req: https_fn.Request) -> https_fn.Response:
    """Fetches all photo documents from Firestore."""
    
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
    
# ... (imports and initialize_app() are at the top)

@https_fn.on_call()
def getphotodetails(req: https_fn.Request) -> https_fn.Response:
    """Fetches a single photo document from Firestore by its ID."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.Code.UNAUTHENTICATED, message="Authentication required.")
    
    photo_id = req.data.get("photoId")
    if not photo_id:
        raise https_fn.HttpsError(code=https_fn.Code.INVALID_ARGUMENT, message="photoId is required.")
        
    try:
        db = firestore.client()
        doc = db.collection("photos").document(photo_id).get()
        if doc.exists:
            return doc.to_dict()
        else:
            raise https_fn.HttpsError(code=https_fn.Code.NOT_FOUND, message="Photo not found.")
    except Exception as e:
        print(f"Error fetching photo details: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred.")


@https_fn.on_call()
def editphoto(req: https_fn.Request) -> https_fn.Response:
    """Updates a photo document in Firestore."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.Code.UNAUTHENTICATED, message="Authentication required.")
    
    data = req.data
    photo_id = data.get("photoId")
    updated_data = data.get("updatedData")

    if not photo_id or not updated_data:
        raise https_fn.HttpsError(code=https_fn.Code.INVALID_ARGUMENT, message="photoId and updatedData are required.")

    try:
        db = firestore.client()
        doc_ref = db.collection("photos").document(photo_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise https_fn.HttpsError(code=https_fn.Code.NOT_FOUND, message="Photo not found.")
        
        # Security Check: Ensure the user editing the photo is the one who uploaded it.
        if doc.get('uploaderUid') != req.auth.uid:
            raise https_fn.HttpsError(code=https_fn.Code.PERMISSION_DENIED, message="You do not have permission to edit this photo.")

        doc_ref.update(updated_data)
        return {"status": "success", "message": "Photo updated."}
    except Exception as e:
        print(f"Error updating photo: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred.")
    
# --- NEW FUNCTION ---
@https_fn.on_call()
def deletephoto(req: https_fn.Request) -> https_fn.Response:
    """Deletes a photo's Firestore document and its file in Cloud Storage."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.Code.UNAUTHENTICATED, message="Authentication required.")

    photo_id = req.data.get("photoId")
    if not photo_id:
        raise https_fn.HttpsError(code=https_fn.Code.INVALID_ARGUMENT, message="photoId is required.")
        
    try:
        db = firestore.client()
        doc_ref = db.collection("photos").document(photo_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise https_fn.HttpsError(code=https_fn.Code.NOT_FOUND, message="Photo not found.")
        
        # Security Check: Ensure the user deleting the photo is the one who uploaded it.
        if doc.get('uploaderUid') != req.auth.uid:
            raise https_fn.HttpsError(code=https_fn.Code.PERMISSION_DENIED, message="You do not have permission to delete this photo.")
        
        # Part 1: Delete the file from Cloud Storage
        image_url = doc.get('imageUrl')
        if image_url:
            # Get the default bucket
            bucket = storage.bucket()
            # Parse the file path from the full URL
            file_path = image_url.split(f"/b/{bucket.name}/o/")[1].split("?")[0]
            # URL Decode the file path
            import urllib.parse
            decoded_file_path = urllib.parse.unquote(file_path)
            
            blob = bucket.blob(decoded_file_path)
            if blob.exists():
                blob.delete()
                print(f"Deleted file from Storage: {decoded_file_path}")

        # Part 2: Delete the document from Firestore
        doc_ref.delete()
        print(f"Deleted document from Firestore: {photo_id}")
        
        return {"status": "success", "message": "Photo deleted."}

    except Exception as e:
        print(f"Error deleting photo: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred while deleting the photo.")