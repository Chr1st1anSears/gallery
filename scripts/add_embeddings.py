"""Backfill image embeddings for photos that don't have one yet.

Each photo document in Firestore stores its own image embedding, which the
`findphotobymatch` Cloud Function compares against at scan time. New photos
added through the app get an embedding automatically; run this script after
importing photos some other way, or to repair documents missing an embedding.

Usage (uses Application Default Credentials; run
`gcloud auth application-default login` first):

    python scripts/add_embeddings.py --project YOUR_PROJECT_ID
    python scripts/add_embeddings.py --project YOUR_PROJECT_ID --force   # recompute all

Cost: one Vertex AI multimodal embedding request per photo processed
(fractions of a cent each). No always-on resources are created.
"""

import argparse
import re
import urllib.parse

import firebase_admin
import vertexai
from firebase_admin import firestore
from vertexai.vision_models import Image, MultiModalEmbeddingModel

REGION = "us-central1"
EMBEDDING_MODEL = "multimodalembedding@001"


def get_gcs_uri_from_url(image_url: str) -> str | None:
    """Converts a Firebase Storage download URL into a gs:// URI."""
    if not image_url:
        return None
    match = re.search(r"/(b|bucket)/([^/]+)/(o|object)/([^?]+)", image_url)
    if match:
        bucket_name = match.group(2)
        object_path = urllib.parse.unquote(match.group(4))
        return f"gs://{bucket_name}/{object_path}"
    return None


def add_embeddings_to_firestore(force: bool) -> None:
    db = firestore.client()
    photos_ref = db.collection("photos")
    model = MultiModalEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    print("Generating and saving embeddings for photos in Firestore...")

    for doc in photos_ref.stream():
        photo_data = doc.to_dict()
        photo_id = doc.id

        if photo_data.get("embedding") and not force:
            print(f"Skipping {photo_id}, embedding already exists.")
            continue

        gcs_uri = get_gcs_uri_from_url(photo_data.get("imageUrl"))
        if not gcs_uri:
            print(f"Skipping {photo_id}, could not parse a GCS URI from its imageUrl.")
            continue

        try:
            print(f"Processing {photo_id} ({gcs_uri})...")
            embeddings = model.get_embeddings(image=Image.load_from_file(gcs_uri))
            photos_ref.document(photo_id).update({"embedding": list(embeddings.image_embedding)})
            print(f"  - Saved embedding for {photo_id}.")
        except Exception as e:
            print(f"  - ERROR processing {photo_id}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill photo embeddings in Firestore.")
    parser.add_argument("--project", required=True, help="Firebase / GCP project ID.")
    parser.add_argument("--force", action="store_true", help="Recompute embeddings even if present.")
    args = parser.parse_args()

    firebase_admin.initialize_app(options={"projectId": args.project})
    vertexai.init(project=args.project, location=REGION)
    add_embeddings_to_firestore(args.force)
