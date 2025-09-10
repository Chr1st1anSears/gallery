# functions/main.py

import urllib.parse
import re
import base64
from firebase_admin import initialize_app, firestore, storage
from firebase_functions import https_fn, options
# We only need to import CallableRequest directly now
from firebase_functions.https_fn import CallableRequest
from vertexai.vision_models import Image as VertexImage, MultiModalEmbeddingModel
from google.cloud import aiplatform

# --- Configuration ---
PROJECT_ID = "gallery-469818"
REGION = "us-central1"
INDEX_ID = "2593143198528307200" 
ENDPOINT_ID = "7942821421518946304"
# ---------------------

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
    """Saves photo metadata to Firestore AND indexes it in Vector Search."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.UNAUTHENTICATED, message="Authentication required.")
    
    try:
        data = req.data
        image_url = data.get('imageUrl')
        if not image_url:
            raise ValueError("imageUrl is missing from the request.")

        gcs_uri = get_gcs_uri_from_url(image_url)
        if gcs_uri:
            print(f"Indexing new photo: {gcs_uri}")
            model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
            image = VertexImage.load_from_file(gcs_uri)
            embeddings = model.get_embeddings(image=image)
            
            my_index = aiplatform.MatchingEngineIndex(index_name=INDEX_ID)
            
            my_index.upsert_datapoints(datapoints=[{
                "datapoint_id": gcs_uri,
                "feature_vector": embeddings.image_embedding,
            }])
            print(f"Successfully indexed '{gcs_uri}'.")
        else:
            print(f"Warning: Could not parse GCS URI from URL: {image_url}")

        photo_doc = {
            'imageUrl': image_url,
            'name': data.get('name'),
            'date': data.get('date'),
            'people': data.get('people'),
            'description': data.get('description'),
            'uploaderUid': req.auth.uid
        }
        db = firestore.client()
        db.collection("photos").add(photo_doc)
        
        return {"status": "success", "message": "Photo saved and indexed."}
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
        if doc.exists:
            return doc.to_dict()
        else:
            raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.NOT_FOUND, message="Photo not found.")
    except Exception as e:
        print(f"Error fetching photo details: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred.")

@https_fn.on_call(memory=options.MemoryOption.GB_1)
def editphoto(req: CallableRequest) -> any:
    """Updates a photo document in Firestore."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.UNAUTHENTICATED, message="Authentication required.")
    
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
    """Deletes a photo from Firestore, Storage, AND the Vector Search index."""
    if req.auth is None:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.UNAUTHENTICATED, message="Authentication required.")

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
            gcs_uri = get_gcs_uri_from_url(image_url)

            if gcs_uri:
                print(f"Removing '{gcs_uri}' from Vector Search index...")
                my_index = aiplatform.MatchingEngineIndex(index_name=INDEX_ID)
                my_index.remove_datapoints(datapoint_ids=[gcs_uri])
                print("Successfully removed from index.")
            else:
                print(f"Warning: Could not parse GCS URI from URL to de-index: {image_url}")

            file_path_match = re.search(r"/o/(.*?)\?alt=media", image_url)
            if file_path_match:
                bucket = storage.bucket()
                decoded_file_path = urllib.parse.unquote(file_path_match.group(1))
                blob = bucket.blob(decoded_file_path)
                if blob.exists():
                    blob.delete()
                    print(f"Deleted file from Storage: {decoded_file_path}")

        doc_ref.delete()
        
        return {"status": "success", "message": "Photo deleted and de-indexed."}
    except Exception as e:
        print(f"Error in deletephoto function: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred.")


@https_fn.on_call(memory=options.MemoryOption.GB_1)
def findphotobymatch(req: CallableRequest) -> any:
    """
    Receives an image, finds the closest match in the Vector Search index,
    and returns the corresponding Firestore document ID.
    """
    if not req.data or not req.data.get("image"):
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT, message="Image data is required.")
        
    try:
        image_string = req.data["image"]
        image_bytes = base64.b64decode(image_string)
        
        model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
        image = VertexImage(image_bytes=image_bytes)
        
        embeddings = model.get_embeddings(image=image)
        query_embedding = embeddings.image_embedding

        index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=ENDPOINT_ID)
        
        neighbors = index_endpoint.find_neighbors(
            deployed_index_id="v3_deployment_1757447059850", # This should be the deployed index ID
            queries=[query_embedding],
            num_neighbors=1
        )
        
        if not neighbors or not neighbors[0]:
            return {"photoId": None}

        best_match = neighbors[0][0]
        matched_gcs_uri = best_match.id
        
        db = firestore.client()
        docs = db.collection("photos").stream()
        for doc in docs:
            photo_data = doc.to_dict()
            image_url = photo_data.get("imageUrl", "")
            doc_gcs_uri = get_gcs_uri_from_url(image_url)
            if doc_gcs_uri == matched_gcs_uri:
                return {"photoId": doc.id}
        
        return {"photoId": None}
    except Exception as e:
        print(f"Error in findphotobymatch: {e}")
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INTERNAL, message="An error occurred during the visual search.")