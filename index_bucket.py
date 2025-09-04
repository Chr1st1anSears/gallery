import argparse
import time
from google.cloud import storage
import vertexai
from vertexai.vision_models import Image, MultiModalEmbeddingModel
from google.cloud import aiplatform

# --- Configuration ---
PROJECT_ID = "gallery-469818"
REGION = "us-central1"
# TODO: Update with the new numeric ID of your STREAMING index
INDEX_ID = "5341464871131152384" 
ENDPOINT_ID = "7942821421518946304" # This can stay the same
# ---------------------

vertexai.init(project=PROJECT_ID, location=REGION)

def index_bucket(bucket_name: str, prefix: str | None = None):
    """
    Lists images in a GCS bucket, generates embeddings, and saves them
    to a Vertex AI Vector Search index using streaming updates.
    """
    storage_client = storage.Client()
    print(f"Listing files in bucket '{bucket_name}' with prefix '{prefix or 'None'}'...")
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    
    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")

    my_index = aiplatform.MatchingEngineIndex(index_name=INDEX_ID)

    datapoints_to_upsert = []
    
    for blob in blobs:
        if blob.name.endswith('/') or not blob.content_type.startswith('image/'):
            continue
            
        gcs_uri = f"gs://{bucket_name}/{blob.name}"
        
        try:
            print(f"\nProcessing '{blob.name}'...")
            image = Image.load_from_file(gcs_uri)
            embeddings = model.get_embeddings(image=image)
            
            # THE FIX: Use the correct field names 'datapoint_id' and 'feature_vector'.
            datapoints_to_upsert.append(
                {
                    "datapoint_id": gcs_uri,
                    "feature_vector": embeddings.image_embedding,
                }
            )
            print(f"  - Generated embedding. Batch size is now {len(datapoints_to_upsert)}.")

            if len(datapoints_to_upsert) >= 10:
                print("\nUpserting batch of 10 to the index...")
                my_index.upsert_datapoints(datapoints=datapoints_to_upsert)
                datapoints_to_upsert = []
                print("  - Batch upserted successfully.")
                time.sleep(1)

        except Exception as e:
            print(f"  - ERROR: Could not process image '{blob.name}'. Reason: {e}")

    if datapoints_to_upsert:
        print("\nUpserting final batch to the index...")
        my_index.upsert_datapoints(datapoints=datapoints_to_upsert)
        print("  - Final batch upserted successfully.")

    print(f"\nFinished indexing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate and save embeddings for images in a GCS bucket."
    )
    parser.add_argument("bucket_name", help="The GCS bucket name.")
    parser.add_argument("--prefix", help="Optional folder/prefix.", default=None)
    args = parser.parse_args()
    
    index_bucket(args.bucket_name, args.prefix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate and save embeddings for images in a GCS bucket."
    )
    parser.add_argument("bucket_name", help="The GCS bucket name.")
    parser.add_argument("--prefix", help="Optional folder/prefix.", default=None)
    args = parser.parse_args()
    
    index_bucket(args.bucket_name, args.prefix)