import firebase_admin
from firebase_admin import firestore
import vertexai
from vertexai.vision_models import Image, MultiModalEmbeddingModel
import argparse
import re
import urllib.parse

# --- Configuration ---
firebase_admin.initialize_app()
PROJECT_ID = "gallery-469818" 
REGION = "us-central1"
vertexai.init(project=PROJECT_ID, location=REGION)
# ---------------------

def get_gcs_uri_from_url(image_url: str) -> str | None:
    """A helper function to parse GCS URIs."""
    if not image_url: return None
    match = re.search(r"/(b|bucket)/([^/]+)/(o|object)/([^?]+)", image_url)
    if match:
        bucket_name = match.group(2)
        object_path = urllib.parse.unquote(match.group(4))
        return f"gs://{bucket_name}/{object_path}"
    return None

def add_embeddings_to_firestore():
    """
    Fetches all photos from Firestore, generates embeddings for them,
    and updates each document with its embedding.
    """
    db = firestore.client()
    photos_ref = db.collection("photos")
    docs = photos_ref.stream()

    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
    print("Generating and saving embeddings for all photos in Firestore...")

    for doc in docs:
        photo_data = doc.to_dict()
        photo_id = doc.id
        image_url = photo_data.get("imageUrl")
        
        # Skip if this document already has an embedding
        if "embedding" in photo_data:
            print(f"Skipping {photo_id}, embedding already exists.")
            continue

        gcs_uri = get_gcs_uri_from_url(image_url)
        if not gcs_uri:
            print(f"Skipping {photo_id}, could not parse GCS URI from: {image_url}")
            continue

        try:
            print(f"Processing {photo_id} ({gcs_uri})...")
            image = Image.load_from_file(gcs_uri)
            embeddings = model.get_embeddings(image=image)
            
            # Convert the list of floats to a format Firestore can store
            image_embedding_list = list(embeddings.image_embedding)
            
            # Update the Firestore document with the new embedding field
            photos_ref.document(photo_id).update({
                "embedding": image_embedding_list
            })
            print(f"  - Successfully saved embedding for {photo_id}.")

        except Exception as e:
            print(f"  - ERROR processing {photo_id}. Reason: {e}")

if __name__ == "__main__":
    add_embeddings_to_firestore()