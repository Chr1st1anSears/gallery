
# functions/main.py

import urllib.parse
import re
import base64
import numpy as np
from firebase_admin import initialize_app, firestore, storage
from firebase_functions import https_fn, options
# We only need to import CallableRequest directly now
from firebase_functions.https_fn import CallableRequest
from vertexai.vision_models import Image as VertexImage, MultiModalEmbeddingModel
from google.cloud import aiplatform

# --- Configuration ---
PROJECT_ID = "gallery-469818"
REGION = "us-central1"
# --- End Configuration ---

# --- Allow list ---
AUTHORIZED_USERS = [
    "crsears1995@gmail.com",
    "crsears@google.com",
    "vorobyshek077@gmail.com",
    "vorobeva@bc.edu",
]
# ------------------

initialize_app()
aiplatform.init(project=PROJECT_ID, location=REGION)


# A helper function to parse URLs, used across multiple functions
def get_gcs_uri_from_url(image_url: str) -> str | None:
    """Parses a Firebase Storage URL to get its GCS URI."""
    if not image_url: return None
    match = re.search(r"/b/([^/]+)/o/([^?]+)", image_url)
    if match:
        bucket_name = match.group(1)
        object_path = urllib.parse.unquote(match.group(2))
        return f"gs://{bucket_name}/{object_path}"
    return None


@https_fn.on_call(memory=options.MemoryOption.GB_1)
def getphotos(req: CallableRequest) -> any:
    """Fetches all photo documents from Firestore."""
    try:
        db = firestore.client()
        docs = db.collection("photos").order_by("date").stream()
        photos = []
        for doc in docs:
            photo_data = doc.to_dict()
            photo_data['id'] = doc.id
            photos.append(photo_data)
        return photos
    except Exception as e:
        print(f"Error fetching photos: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred.")

@https_fn.on_call(memory=options.MemoryOption.GB_1)
def addphoto(req: CallableRequest) -> any:
    """Saves photo metadata to Firestore and generates its embedding."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.UNAUTHENTICATED, message="Authentication required.")
    
    user_email = req.auth.token.get("email")
    if user_email not in AUTHORIZED_USERS:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.PERMISSION_DENIED, message="You do not have permission to perform this action.")

    try:
        data = req.data
        image_url = data.get('imageUrl')
        if not image_url:
            raise ValueError("imageUrl is missing from the request.")

        # 1. Save the initial document to get an ID
        db = firestore.client()
        photo_doc_data = {
            'imageUrl': image_url,
            'name': data.get('name'),
            'date': data.get('date'),
            'relatedPhotos': data.get('relatedPhotos', []),
            'description': data.get('description'),
            'uploaderUid': req.auth.uid
        }
        doc_ref = db.collection("photos").add(photo_doc_data)[1] # add() returns a tuple
        print(f"Created new photo document with ID: {doc_ref.id}")

        # 2. Generate the embedding
        gcs_uri = get_gcs_uri_from_url(image_url)
        if gcs_uri:
            print(f"Generating embedding for new photo: {gcs_uri}")
            model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
            image = VertexImage.load_from_file(gcs_uri)
            embeddings = model.get_embeddings(image=image)
            
            # 3. Update the document with the embedding
            if embeddings.image_embedding:
                doc_ref.update({"embedding": embeddings.image_embedding})
                print(f"Successfully added embedding to document {doc_ref.id}.")
            else:
                print(f"Warning: Could not generate embedding for {gcs_uri}.")
        else:
            print(f"Warning: Could not parse GCS URI from URL: {image_url}")
        
        return {"status": "success", "message": "Photo saved and embedding generated."}
    except Exception as e:
        print(f"Error in addphoto function: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred while adding the photo.")

@https_fn.on_call(memory=options.MemoryOption.GB_1)
def getphotodetails(req: CallableRequest) -> any:
    """Fetches a single photo document from Firestore by its ID."""
    photo_id = req.data.get("photoId")
    if not photo_id:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT, message="photoId is required.")
        
    try:
        db = firestore.client()
        doc = db.collection("photos").document(photo_id).get()
        if not doc.exists:
            raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.NOT_FOUND, message="Photo not found.")
        
        photo_data = doc.to_dict()

        # --- CHANGE: This is the new logic to enrich the related photos data ---
        # It fetches the names of the related photos for the frontend to display.
        if "relatedPhotos" in photo_data and isinstance(photo_data["relatedPhotos"], list) and photo_data["relatedPhotos"]:
            # 1. Create a list of document references for all related photos.
            related_doc_refs = [
                db.collection("photos").document(related["id"])
                for related in photo_data["relatedPhotos"] if "id" in related
            ]
            
            # 2. Fetch all related documents in a single, efficient batch call.
            related_docs = db.get_all(related_doc_refs)
            
            # 3. Create a simple dictionary to easily look up a doc's data by its ID.
            related_docs_map = {doc.id: doc.to_dict() for doc in related_docs if doc.exists}

            # 4. Build a new, "enriched" list of related photos.
            enriched_related_photos = []
            for related in photo_data["relatedPhotos"]:
                related_id = related.get("id")
                if related_id in related_docs_map:
                    enriched_related_photos.append({
                        "id": related_id,
                        "text": related.get("text", ""),
                        "name": related_docs_map[related_id].get("name", "Unknown Photo")
                    })
            
            # 5. Replace the original list with the new one containing the names.
            photo_data["relatedPhotos"] = enriched_related_photos

        return photo_data

    except Exception as e:
        print(f"Error fetching photo details: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred.")

@https_fn.on_call(memory=options.MemoryOption.GB_1)
def editphoto(req: CallableRequest) -> any:
    """Updates a photo document in Firestore."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.UNAUTHENTICATED, message="Authentication required.")
    
    user_email = req.auth.token.get("email")
    if user_email not in AUTHORIZED_USERS:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.PERMISSION_DENIED, message="You do not have permission to perform this action.")

    data = req.data
    photo_id = data.get("photoId")
    updated_data = data.get("updatedData")

    if not photo_id or not updated_data:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT, message="photoId and updatedData are required.")

    try:
        db = firestore.client()
        doc_ref = db.collection("photos").document(photo_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.NOT_FOUND, message="Photo not found.")

        doc_ref.update(updated_data)
        return {"status": "success", "message": "Photo updated."}
    except Exception as e:
        print(f"Error updating photo: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred.")

@https_fn.on_call(memory=options.MemoryOption.GB_1)
def deletephoto(req: CallableRequest) -> any:
    """Deletes a photo from Firestore and Storage."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.UNAUTHENTICATED, message="Authentication required.")

    user_email = req.auth.token.get("email")
    if user_email not in AUTHORIZED_USERS:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.PERMISSION_DENIED, message="You do not have permission to perform this action.")

    photo_id = req.data.get("photoId")
    if not photo_id:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT, message="photoId is required.")
        
    try:
        db = firestore.client()
        doc_ref = db.collection("photos").document(photo_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.NOT_FOUND, message="Photo not found.")
        
        doc_data = doc.to_dict()
        image_url = doc_data.get('imageUrl')

        if image_url:
            # Delete from Cloud Storage
            file_path_match = re.search(r"/o/(.*?)\?alt=media", image_url)
            if file_path_match:
                bucket = storage.bucket()
                decoded_file_path = urllib.parse.unquote(file_path_match.group(1))
                blob = bucket.blob(decoded_file_path)
                if blob.exists():
                    blob.delete()
                    print(f"Deleted file from Storage: {decoded_file_path}")

        # Delete from Firestore
        doc_ref.delete()
        
        return {"status": "success", "message": "Photo deleted."}
    except Exception as e:
        print(f"Error in deletephoto function: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred.")


@https_fn.on_call(memory=options.MemoryOption.GB_1)
def findphotobymatch(req: CallableRequest) -> any:
    """
    Receives an image, finds the closest match from the Firestore database
    by performing an in-memory vector similarity search.
    """
    if not req.data or not req.data.get("image"):
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT, message="Image data is required.")
        
    try:
        # 1. Generate embedding for the user's image
        image_string = req.data["image"]
        image_bytes = base64.b64decode(image_string)
        
        model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
        image = VertexImage(image_bytes=image_bytes)
        
        embeddings = model.get_embeddings(image=image)
        query_embedding = embeddings.image_embedding

        # 2. Fetch all photo documents from Firestore
        db = firestore.client()
        docs = db.collection("photos").stream()

        best_match_id = None
        highest_similarity = -1.0  # Cosine similarity ranges from -1 to 1
        SIMILARITY_THRESHOLD = 0.6 # Only return a match if it's strong enough

        # 3. Loop and compare
        for doc in docs:
            photo_data = doc.to_dict()
            
            # Ensure the document has an embedding
            if "embedding" in photo_data and photo_data["embedding"]:
                doc_embedding = photo_data["embedding"]
                
                # Calculate dot product similarity
                similarity = np.dot(query_embedding, doc_embedding)
                
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    best_match_id = doc.id

        # 4. Return the best match if it meets the threshold
        if highest_similarity >= SIMILARITY_THRESHOLD:
            return {"photoId": best_match_id}
        else:
            print(f"No sufficiently similar match found. Highest similarity: {highest_similarity}")
            return {"photoId": None}

    except Exception as e:
        print(f"Error in findphotobymatch: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred during the visual search.")