import urllib.parse
import re
import base64
from firebase_admin import initialize_app, firestore, storage
from firebase_functions import https_fn, options
from vertexai.vision_models import Image as VertexImage, MultiModalEmbeddingModel
from google.cloud import aiplatform

# Initialize the Firebase Admin SDK ONCE at the top.
initialize_app()

# Set the region for all functions in this file
options.set_global_options(region="us-central1")


@https_fn.on_call()
def getphotos(req: https_fn.Request) -> https_fn.Response:
    """Fetches all photo documents from Firestore."""
    try:
        db = firestore.client()
        docs = db.collection("photos").order_by("date").stream()
        photos = []
        for doc in docs:
            photo_data = doc.to_dict()
            photo_data['id'] = doc.id
            photos.append(photo_data)
        print(f"Returning {len(photos)} photos.")
        return photos
    except Exception as e:
        print(f"Error fetching photos: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred.")

@https_fn.on_call()
def addphoto(req: https_fn.Request) -> https_fn.Response:
    """Saves photo metadata to a new document in Firestore."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.Code.UNAUTHENTICATED, message="Authentication required.")
    
    try:
        data = req.data
        print(f"Received photo data: {data}")
        photo_doc = {
            'imageUrl': data.get('imageUrl'),
            'name': data.get('name'),
            'date': data.get('date'),
            'people': data.get('people'),
            'description': data.get('description'),
            'uploaderUid': req.auth.uid
        }
        db = firestore.client()
        db.collection("photos").add(photo_doc)
        return {"status": "success", "message": "Photo details saved."}
    except Exception as e:
        print(f"Error saving photo details: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred.")

@https_fn.on_call()
def getphotodetails(req: https_fn.Request) -> https_fn.Response:
    """Fetches a single photo document from Firestore by its ID."""
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
        
        if doc.get('uploaderUid') != req.auth.uid:
            raise https_fn.HttpsError(code=https_fn.Code.PERMISSION_DENIED, message="You do not have permission to edit this photo.")

        doc_ref.update(updated_data)
        return {"status": "success", "message": "Photo updated."}
    except Exception as e:
        print(f"Error updating photo: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred.")

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
        
        if doc.get('uploaderUid') != req.auth.uid:
            raise https_fn.HttpsError(code=https_fn.Code.PERMISSION_DENIED, message="You do not have permission to delete this photo.")
        
        image_url = doc.get('imageUrl')
        if image_url:
            bucket = storage.bucket()
            file_path = image_url.split(f"/b/{bucket.name}/o/")[1].split("?")[0]
            decoded_file_path = urllib.parse.unquote(file_path)
            
            blob = bucket.blob(decoded_file_path)
            if blob.exists():
                blob.delete()
                print(f"Deleted file from Storage: {decoded_file_path}")

        doc_ref.delete()
        print(f"Deleted document from Firestore: {photo_id}")
        
        return {"status": "success", "message": "Photo deleted."}
    except Exception as e:
        print(f"Error deleting photo: {e}")
        raise https_fn.HttpsError(code=https_fn.Code.INTERNAL, message="An error occurred.")

# A helper function to parse URLs, used in findphotobymatch
def get_gcs_uri_from_url(image_url: str) -> str | None:
    if not image_url: return None
    match = re.search(r"/(b|bucket)/([^/]+)/(o|object)/([^?]+)", image_url)
    if match:
        bucket_name = match.group(2)
        object_path = urllib.parse.unquote(match.group(4))
        return f"gs://{bucket_name}/{object_path}"
    return None

@https_fn.on_call()
def findphotobymatch(req: https_fn.Request) -> https_fn.Response:
    """
    Receives an image, finds the closest match in the Vector Search index,
    and returns the corresponding Firestore document ID.
    """
    ENDPOINT_ID = "7942821421518946304"
    # THE FIX: Use the DEPLOYED Index name, not the numeric Index resource ID.
    DEPLOYED_INDEX_ID = "v2_1757010436651" 

    if not req.data or not req.data.get("image"):
        raise https_fn.HttpsError(code=https_fn.HttpsError.Code.INVALID_ARGUMENT, message="Image data is required.")
        
    try:
        image_string = req.data["image"]
        image_bytes = base64.b64decode(image_string)
        
        model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
        image = VertexImage(image_bytes=image_bytes)
        
        embeddings = model.get_embeddings(image=image)
        query_embedding = embeddings.image_embedding

        index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=ENDPOINT_ID)
        
        neighbors = index_endpoint.find_neighbors(
            deployed_index_id=DEPLOYED_INDEX_ID,
            queries=[query_embedding],
            num_neighbors=1
        )
        
        if not neighbors or not neighbors[0]:
            print("No neighbors found in Vector Search.")
            return {"photoId": None}

        best_match = neighbors[0][0]
        matched_gcs_uri = best_match.id
        
        db = firestore.client()
        photos_ref = db.collection("photos")
        
        # --- DEBUGGING: Print the value from Vector Search ---
        print(f"--- DEBUG: Matched GCS URI from Vector Search: '{matched_gcs_uri}'")

        docs = photos_ref.stream()
        for doc in docs:
            photo_data = doc.to_dict()
            image_url = photo_data.get("imageUrl", "")
            doc_gcs_uri = get_gcs_uri_from_url(image_url)
            
            # --- DEBUGGING: Print the value we are comparing against ---
            print(f"--- DEBUG: Comparing against Firestore Doc ID {doc.id} with parsed URI: '{doc_gcs_uri}'")

            if doc_gcs_uri == matched_gcs_uri:
                print(f"Found matching Firestore document: {doc.id}")
                return {"photoId": doc.id}
        
        print("Vector Search match found, but no corresponding document in Firestore.")
        return {"photoId": None}

    except Exception as e:
        print(f"Error in findphotobymatch: {e}")
        raise https_fn.HttpsError(code=https_fn.HttpsError.Code.INTERNAL, message="An error occurred during the visual search.")
