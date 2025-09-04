import argparse
from google.cloud import storage
import vertexai
from vertexai.vision_models import Image, MultiModalEmbeddingModel

# --- Configuration ---
# Initialize Vertex AI. This script assumes it's running in an
# authenticated environment like Cloud Shell.
PROJECT_ID = "gallery-469818"
REGION = "us-central1"
vertexai.init(project=PROJECT_ID, location=REGION)
# ---------------------

def index_bucket(bucket_name: str, prefix: str | None = None):
    """
    Lists all images in a GCS bucket/prefix and generates embeddings.
    
    Args:
        bucket_name: The name of the Cloud Storage bucket.
        prefix: Optional. The folder/prefix to process within the bucket.
    """
    storage_client = storage.Client()
    
    print(f"Listing files in bucket '{bucket_name}' with prefix '{prefix or 'None'}'...")
    
    # List all the blobs (files) in the bucket/prefix.
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    
    # Load the pre-trained multimodal embedding model
    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")

    count = 0
    for blob in blobs:
        # Skip directories (which end in '/') and non-image files
        if blob.name.endswith('/') or not blob.content_type.startswith('image/'):
            continue
            
        gcs_uri = f"gs://{bucket_name}/{blob.name}"
        
        try:
            print(f"\nProcessing '{blob.name}'...")
            image = Image.load_from_file(gcs_uri)

            # Generate the embedding. Since we don't have text from Firestore,
            # we rely purely on the image content.
            embeddings = model.get_embeddings(image=image)
            image_embedding = embeddings.image_embedding
            
            print(f"  - Successfully generated embedding with {len(image_embedding)} dimensions.")
            count += 1
            
            # TODO: In the next step, we would save this embedding and the blob.name
            # to the Vector Search index.

        except Exception as e:
            print(f"  - ERROR: Could not process image '{blob.name}'. Reason: {e}")

    print(f"\nFinished processing. Generated embeddings for {count} images.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate embeddings for all images in a GCS bucket."
    )
    parser.add_argument(
        "bucket_name",
        help="The name of the Cloud Storage bucket to process.",
    )
    parser.add_argument(
        "--prefix",
        help="Optional. The folder/prefix within the bucket to process.",
        default=None,
    )
    args = parser.parse_args()
    
    index_bucket(args.bucket_name, args.prefix)