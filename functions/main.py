# functions/main.py
#
# Cloud Functions (2nd gen, Python) backing the Gallery web app.
#
# Cost design (important):
#   * There is NO always-on infrastructure. Every function scales to zero.
#   * Visual search does NOT use a Vertex AI Vector Search endpoint. Each photo's
#     image embedding is stored on its Firestore document, and
#     `findphotobymatch` compares the query embedding against them in memory.
#   * Every function has a `max_instances` cap so a traffic spike or abuse
#     cannot scale out into a large bill.
#
# Authorization:
#   * Read-only endpoints (getphotos, getphotodetails, findphotobymatch) are
#     public so that anyone standing in front of the wall can use the app.
#   * Write endpoints require a Firebase Auth user with the custom claim
#     `editor: true`. Grant it with `scripts/set_editor.py`.
#   * Firestore security rules deny all direct client access; these functions
#     (Admin SDK) are the only data path.

import base64
import binascii
import os
import re
import urllib.parse

from firebase_admin import firestore, initialize_app, storage
from firebase_functions import https_fn, options
from firebase_functions.https_fn import CallableRequest

# --- Configuration ---
REGION = "us-central1"
EMBEDDING_MODEL = "multimodalembedding@001"
SIMILARITY_THRESHOLD = 0.6  # Only return a match if it's strong enough.

# Hard caps on scale-out. These cost nothing when idle; they only bound the
# worst case. Raise them only if real users start seeing "resource exhausted".
MAX_INSTANCES_PUBLIC = 3
MAX_INSTANCES_EDITOR = 2

# Input limits.
MAX_NAME_LEN = 200
MAX_DATE_LEN = 100
MAX_DESCRIPTION_LEN = 20_000  # Room for long family stories.
MAX_RELATED_PHOTOS = 50
MAX_RELATED_TEXT_LEN = 300
# The browser downsizes scans to ~1024px JPEG (~100-300 KB). This leaves
# generous headroom while rejecting abusive payloads early.
MAX_SCAN_BASE64_LEN = 7_000_000
DOC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# --- End Configuration ---

initialize_app()

# Shared option sets. Lightweight Firestore-only functions get less memory
# (and therefore less billed GB-seconds) than the ones that call Vertex AI.
_LIGHT_PUBLIC = dict(
    region=REGION,
    memory=options.MemoryOption.MB_512,
    max_instances=MAX_INSTANCES_PUBLIC,
)
_LIGHT_EDITOR = dict(
    region=REGION,
    memory=options.MemoryOption.MB_512,
    max_instances=MAX_INSTANCES_EDITOR,
)
_VERTEX_PUBLIC = dict(
    region=REGION,
    memory=options.MemoryOption.GB_1,
    timeout_sec=120,
    max_instances=MAX_INSTANCES_PUBLIC,
)
_VERTEX_EDITOR = dict(
    region=REGION,
    memory=options.MemoryOption.GB_1,
    timeout_sec=120,
    max_instances=MAX_INSTANCES_EDITOR,
)

_embedding_model = None


def _get_embedding_model():
    """Lazily imports and caches the Vertex AI embedding model.

    The Vertex AI SDK is heavy to import. Importing it lazily keeps cold starts
    fast (and memory low) for functions that never need it.
    """
    global _embedding_model
    if _embedding_model is None:
        import vertexai
        from vertexai.vision_models import MultiModalEmbeddingModel

        vertexai.init(location=REGION)
        _embedding_model = MultiModalEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    return _embedding_model


def _embed_image(*, gcs_uri: str | None = None, image_bytes: bytes | None = None) -> list[float] | None:
    """Returns the image embedding for a GCS object or raw image bytes."""
    from vertexai.vision_models import Image as VertexImage

    model = _get_embedding_model()
    if gcs_uri:
        image = VertexImage.load_from_file(gcs_uri)
    else:
        image = VertexImage(image_bytes=image_bytes)
    embeddings = model.get_embeddings(image=image)
    return list(embeddings.image_embedding) if embeddings.image_embedding else None


# All functions share this module, but only these two need Vertex AI. Cloud Run
# sets K_SERVICE to the function's service name, so we preload the SDK and
# model at container startup *only* in those containers. Startup gets Cloud
# Run's CPU boost and doesn't count against the request timeout, so the first
# scan stays fast, while the Firestore-only functions skip the heavy import.
_VERTEX_SERVICES = {"findphotobymatch", "addphoto"}
if os.environ.get("K_SERVICE") in _VERTEX_SERVICES:
    try:
        _get_embedding_model()
    except Exception as e:  # Fall back to loading lazily on first request.
        print(f"Warning: could not preload embedding model: {e}")


# --- Helpers ---

def _error(code: https_fn.FunctionsErrorCode, message: str) -> https_fn.HttpsError:
    return https_fn.HttpsError(code=code, message=message)


def _require_editor(req: CallableRequest) -> None:
    """Raises unless the caller is signed in and has the `editor` custom claim."""
    if req.auth is None:
        raise _error(https_fn.FunctionsErrorCode.UNAUTHENTICATED, "Authentication required.")
    if req.auth.token.get("editor") is not True:
        raise _error(
            https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            "You do not have permission to perform this action.",
        )


def _clean_str(value, field: str, max_len: int, *, required: bool = False) -> str:
    """Validates an optional/required string field and returns it stripped."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, f"'{field}' must be a string.")
    value = value.strip()
    if required and not value:
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, f"'{field}' is required.")
    if len(value) > max_len:
        raise _error(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            f"'{field}' must be at most {max_len} characters.",
        )
    return value


def _clean_doc_id(value, field: str = "photoId") -> str:
    if not isinstance(value, str) or not DOC_ID_PATTERN.match(value):
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, f"'{field}' is invalid.")
    return value


def _clean_related_photos(value, *, self_id: str | None = None) -> list[dict]:
    """Validates the relatedPhotos list: [{id: str, text: str}, ...]."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_RELATED_PHOTOS:
        raise _error(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            f"'relatedPhotos' must be a list of at most {MAX_RELATED_PHOTOS} items.",
        )
    cleaned, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Invalid related photo entry.")
        related_id = _clean_doc_id(item.get("id"), "relatedPhotos.id")
        if related_id == self_id or related_id in seen:
            continue  # Drop self-links and duplicates.
        seen.add(related_id)
        cleaned.append({
            "id": related_id,
            "text": _clean_str(item.get("text"), "relatedPhotos.text", MAX_RELATED_TEXT_LEN),
        })
    return cleaned


def get_gcs_uri_from_url(image_url: str) -> str | None:
    """Parses a Firebase Storage download URL to get its gs:// URI."""
    if not image_url:
        return None
    match = re.search(r"/b/([^/]+)/o/([^?]+)", image_url)
    if match:
        bucket_name = match.group(1)
        object_path = urllib.parse.unquote(match.group(2))
        return f"gs://{bucket_name}/{object_path}"
    return None


def _validate_upload_url(image_url, uid: str) -> tuple[str, str]:
    """Ensures imageUrl points at this project's bucket, inside the caller's folder.

    Returns (image_url, object_path). This stops callers from attaching
    arbitrary external URLs or other users' files to a photo document.
    """
    if not isinstance(image_url, str) or len(image_url) > 2048:
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "'imageUrl' is invalid.")
    parsed = urllib.parse.urlparse(image_url)
    gcs_uri = get_gcs_uri_from_url(image_url)
    if parsed.scheme != "https" or parsed.hostname != "firebasestorage.googleapis.com" or not gcs_uri:
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "'imageUrl' must be a Firebase Storage URL.")
    expected_bucket = storage.bucket().name
    bucket_name, _, object_path = gcs_uri[len("gs://"):].partition("/")
    if bucket_name != expected_bucket or not object_path.startswith(f"{uid}/") or ".." in object_path:
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "'imageUrl' must be your own upload.")
    return image_url, object_path


# --- Public, read-only endpoints ---

@https_fn.on_call(**_LIGHT_PUBLIC)
def getphotos(req: CallableRequest) -> list:
    """Returns a lightweight list of all photos (no embeddings or descriptions)."""
    try:
        db = firestore.client()
        docs = (
            db.collection("photos")
            .order_by("date")
            .select(["name", "date", "imageUrl"])
            .stream()
        )
        photos = []
        for doc in docs:
            d = doc.to_dict()
            photos.append({"id": doc.id, "name": d.get("name"), "date": d.get("date"), "imageUrl": d.get("imageUrl")})
        return photos
    except Exception as e:
        print(f"Error fetching photos: {e}")
        raise _error(https_fn.FunctionsErrorCode.INTERNAL, "An error occurred.")


@https_fn.on_call(**_LIGHT_PUBLIC)
def getphotodetails(req: CallableRequest) -> dict:
    """Fetches a single photo, enriching relatedPhotos with their names."""
    photo_id = _clean_doc_id((req.data or {}).get("photoId"))

    try:
        db = firestore.client()
        doc = db.collection("photos").document(photo_id).get()
        if not doc.exists:
            raise _error(https_fn.FunctionsErrorCode.NOT_FOUND, "Photo not found.")

        data = doc.to_dict()
        photo = {
            "id": doc.id,
            "name": data.get("name"),
            "date": data.get("date"),
            "description": data.get("description"),
            "imageUrl": data.get("imageUrl"),
            "relatedPhotos": [],
        }

        related = data.get("relatedPhotos")
        if isinstance(related, list) and related:
            refs = [
                db.collection("photos").document(r["id"])
                for r in related
                if isinstance(r, dict) and isinstance(r.get("id"), str) and DOC_ID_PATTERN.match(r["id"])
            ]
            # One batched read for all related docs; only fetch the name field.
            names = {d.id: d.to_dict().get("name") for d in db.get_all(refs, field_paths=["name"]) if d.exists}
            photo["relatedPhotos"] = [
                {"id": r["id"], "text": r.get("text", ""), "name": names[r["id"]] or "Unknown Photo"}
                for r in related
                if isinstance(r, dict) and r.get("id") in names
            ]
        return photo

    except https_fn.HttpsError:
        raise
    except Exception as e:
        print(f"Error fetching photo details: {e}")
        raise _error(https_fn.FunctionsErrorCode.INTERNAL, "An error occurred.")


@https_fn.on_call(**_VERTEX_PUBLIC)
def findphotobymatch(req: CallableRequest) -> dict:
    """Finds the stored photo most similar to the supplied image.

    Performs an in-memory similarity search over the embeddings stored on each
    Firestore document. No Vector Search endpoint is used (see top of file).

    Pass {"warmup": true} to load the model without doing a search; the
    homepage does this so the first real scan is faster.
    """
    data = req.data or {}

    if data.get("warmup") is True:
        _get_embedding_model()
        return {"warm": True}

    image_string = data.get("image")
    if not isinstance(image_string, str) or not image_string:
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Image data is required.")
    if len(image_string) > MAX_SCAN_BASE64_LEN:
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Image is too large.")
    try:
        image_bytes = base64.b64decode(image_string, validate=True)
    except (binascii.Error, ValueError):
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Image data is not valid base64.")

    try:
        import numpy as np

        query_embedding = _embed_image(image_bytes=image_bytes)
        if not query_embedding:
            return {"photoId": None}
        query = np.asarray(query_embedding, dtype=np.float32)

        db = firestore.client()
        best_match_id, highest_similarity = None, -1.0
        # Only pull the embedding field; we just need IDs and vectors here.
        for doc in db.collection("photos").select(["embedding"]).stream():
            doc_embedding = doc.to_dict().get("embedding")
            if not doc_embedding:
                continue
            similarity = float(np.dot(query, np.asarray(doc_embedding, dtype=np.float32)))
            if similarity > highest_similarity:
                highest_similarity, best_match_id = similarity, doc.id

        if highest_similarity >= SIMILARITY_THRESHOLD:
            return {"photoId": best_match_id}
        print(f"No sufficiently similar match found. Highest similarity: {highest_similarity}")
        return {"photoId": None}

    except Exception as e:
        print(f"Error in findphotobymatch: {e}")
        raise _error(https_fn.FunctionsErrorCode.INTERNAL, "An error occurred during the visual search.")


# --- Editor-only endpoints ---

@https_fn.on_call(**_VERTEX_EDITOR)
def addphoto(req: CallableRequest) -> dict:
    """Saves photo metadata to Firestore and stores its image embedding."""
    _require_editor(req)
    data = req.data or {}

    image_url, _ = _validate_upload_url(data.get("imageUrl"), req.auth.uid)
    photo_doc = {
        "imageUrl": image_url,
        "name": _clean_str(data.get("name"), "name", MAX_NAME_LEN, required=True),
        "date": _clean_str(data.get("date"), "date", MAX_DATE_LEN),
        "description": _clean_str(data.get("description"), "description", MAX_DESCRIPTION_LEN),
        "relatedPhotos": _clean_related_photos(data.get("relatedPhotos")),
        "uploaderUid": req.auth.uid,
    }

    try:
        db = firestore.client()
        _, doc_ref = db.collection("photos").add(photo_doc)
        print(f"Created new photo document with ID: {doc_ref.id}")

        gcs_uri = get_gcs_uri_from_url(image_url)
        embedding = _embed_image(gcs_uri=gcs_uri)
        if embedding:
            doc_ref.update({"embedding": embedding})
            print(f"Stored embedding on document {doc_ref.id}.")
        else:
            print(f"Warning: could not generate embedding for {gcs_uri}.")

        return {"status": "success", "photoId": doc_ref.id}
    except Exception as e:
        print(f"Error in addphoto function: {e}")
        raise _error(https_fn.FunctionsErrorCode.INTERNAL, "An error occurred while adding the photo.")


@https_fn.on_call(**_LIGHT_EDITOR)
def editphoto(req: CallableRequest) -> dict:
    """Updates the editable fields of a photo document."""
    _require_editor(req)
    data = req.data or {}
    photo_id = _clean_doc_id(data.get("photoId"))
    updated = data.get("updatedData")
    if not isinstance(updated, dict):
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "'updatedData' is required.")

    # Only these fields may be changed. imageUrl, embedding and uploaderUid are
    # managed by the server and can never be overwritten by a client.
    changes = {}
    if "name" in updated:
        changes["name"] = _clean_str(updated["name"], "name", MAX_NAME_LEN, required=True)
    if "date" in updated:
        changes["date"] = _clean_str(updated["date"], "date", MAX_DATE_LEN)
    if "description" in updated:
        changes["description"] = _clean_str(updated["description"], "description", MAX_DESCRIPTION_LEN)
    if "relatedPhotos" in updated:
        changes["relatedPhotos"] = _clean_related_photos(updated["relatedPhotos"], self_id=photo_id)
    if not changes:
        raise _error(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "No editable fields supplied.")

    try:
        doc_ref = firestore.client().collection("photos").document(photo_id)
        if not doc_ref.get(field_paths=["name"]).exists:
            raise _error(https_fn.FunctionsErrorCode.NOT_FOUND, "Photo not found.")
        doc_ref.update(changes)
        return {"status": "success"}
    except https_fn.HttpsError:
        raise
    except Exception as e:
        print(f"Error updating photo: {e}")
        raise _error(https_fn.FunctionsErrorCode.INTERNAL, "An error occurred.")


@https_fn.on_call(**_LIGHT_EDITOR)
def deletephoto(req: CallableRequest) -> dict:
    """Deletes a photo document and its image from Cloud Storage."""
    _require_editor(req)
    photo_id = _clean_doc_id((req.data or {}).get("photoId"))

    try:
        doc_ref = firestore.client().collection("photos").document(photo_id)
        doc = doc_ref.get(field_paths=["imageUrl"])
        if not doc.exists:
            raise _error(https_fn.FunctionsErrorCode.NOT_FOUND, "Photo not found.")

        gcs_uri = get_gcs_uri_from_url(doc.to_dict().get("imageUrl", ""))
        if gcs_uri:
            bucket = storage.bucket()
            bucket_name, _, object_path = gcs_uri[len("gs://"):].partition("/")
            # Only ever delete objects from this project's own bucket.
            if bucket_name == bucket.name and object_path:
                blob = bucket.blob(object_path)
                if blob.exists():
                    blob.delete()
                    print(f"Deleted file from Storage: {object_path}")

        doc_ref.delete()
        return {"status": "success"}
    except https_fn.HttpsError:
        raise
    except Exception as e:
        print(f"Error in deletephoto function: {e}")
        raise _error(https_fn.FunctionsErrorCode.INTERNAL, "An error occurred.")
