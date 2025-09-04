import firebase_admin
from firebase_admin import credentials, firestore
import vertexai
from vertexai.vision_models import Image, MultiModalEmbeddingModel
import re
import urllib.parse

# --- Configuration ---
firebase_admin.initialize_app()
PROJECT_ID = "gallery-469818"
REGION = "us-central1"
vertexai.init(project=PROJECT_ID, location=REGION)
# ---------------------

def get_gcs_uri_from_url(image_url: str) -> str | None:
    """
    Extracts the bucket and object path from various GCS URL formats
    and returns a clean gs:// URI.
    """
    if not image_url:
        return None
    
    # This regular expression is designed to find the bucket name and the object path
    # in all common GCS URL formats (production, emulator, gsutil, etc.)
    match = re.search(r"/(b|bucket)/([^/]+)/(o|object)/([^?]+)", image_url)
    if match:
        bucket_name = match.group(2)
        # URL Decode the object path to handle special characters like '%2F' for slashes
        object_path = urllib.parse.unquote(match.group(4))
        return f"gs://{bucket_name}/{object_path}"
    
    return None # Return None if no valid format is found

def generate_embeddings():
    """
    Fetches photos from Firestore and generates embeddings for each.
    """
    db = firestore.client()
    docs = db.collection("photos").stream()

    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")

    print("Generating embeddings for photos in Firestore...")
    for doc in docs:
        photo = doc.to_dict()
        photo_id = doc.id
        image_url = photo.get("imageUrl")
        photo_name = photo.get("name", "Untitled")

        # Use our new, robust function to get the GCS URI
        gcs_uri = get_gcs_uri_from_url(image_url)

        if not gcs_uri:
            print(f"\nSkipping '{photo_name}' ({photo_id}) - could not parse a valid GCS URI from URL: {image_url}")
            continue
        
        try:
            print(f"\nProcessing '{photo_name}' from {gcs_uri}...")
            image = Image.load_from_file(gcs_uri)
            embeddings = model.get_embeddings(
                image=image,
                contextual_text=f"{photo_name}, {photo.get('description', '')}",
            )
            image_embedding = embeddings.image_embedding
            print(f"  - Successfully generated embedding with {len(image_embedding)} dimensions.")
            
            # TODO: In the next step, we'll save this embedding to the Vector Search index.

        except Exception as e:
            print(f"  - ERROR: Could not process image '{photo_name}'. Reason: {e}")

if __name__ == "__main__":
    generate_embeddings()