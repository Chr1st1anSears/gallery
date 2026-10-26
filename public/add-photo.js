// add-photo.js — upload a new photo (editors only).
document.addEventListener('DOMContentLoaded', () => {
  const { el, errorMessage } = Gallery;
  const { createRelatedPhotosEditor, fetchPhotoChoices, requireEditor } = GalleryForm;

  const MAX_UPLOAD_BYTES = 15 * 1024 * 1024; // Must match storage.rules.
  const EXTENSIONS = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/heic': 'heic', 'image/gif': 'gif' };

  const form = document.getElementById('add-photo-form');
  const uploadInput = document.getElementById('image-upload');
  const cameraInput = document.getElementById('camera-input');
  const fileNameDisplay = document.getElementById('file-name');
  const submitButton = document.getElementById('submit-button');
  const relatedContainer = document.getElementById('related-photos-container');
  const addRelatedButton = document.getElementById('add-related-photo-button');
  const formStatus = document.getElementById('form-status');

  let currentUser = null;
  let selectedFile = null;
  let related = null;

  const setStatus = (message) => { formStatus.textContent = message || ''; };

  requireEditor().then(async (user) => {
    currentUser = user;
    try {
      related = createRelatedPhotosEditor(relatedContainer, await fetchPhotoChoices());
      related.addRow();
    } catch (error) {
      relatedContainer.replaceChildren(
        el('p', { className: 'text-danger', text: 'Could not load the photo list for related photos.' })
      );
    }
  });

  addRelatedButton.addEventListener('click', () => related && related.addRow());

  const handleFileSelect = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setStatus('Please choose an image file.');
      return;
    }
    if (file.size >= MAX_UPLOAD_BYTES) {
      setStatus('That image is too large (15 MB max).');
      return;
    }
    selectedFile = file;
    setStatus('');
    fileNameDisplay.textContent = 'Selected: ' + file.name;
  };
  uploadInput.addEventListener('change', handleFileSelect);
  cameraInput.addEventListener('change', handleFileSelect);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentUser || !selectedFile) {
      setStatus('Please choose a photo to upload.');
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Uploading...';
    setStatus('');
    try {
      // Random, unguessable object name; the original filename is not used.
      const ext = EXTENSIONS[selectedFile.type] || 'img';
      const path = `${currentUser.uid}/${crypto.randomUUID()}.${ext}`;
      const ref = firebase.storage().ref(path);
      await ref.put(selectedFile, { contentType: selectedFile.type });
      const imageUrl = await ref.getDownloadURL();

      submitButton.textContent = 'Saving...';
      await firebase.functions().httpsCallable('addphoto')({
        imageUrl,
        name: document.getElementById('name').value,
        date: document.getElementById('date').value,
        description: document.getElementById('description').value,
        relatedPhotos: related ? related.getValue() : [],
      });
      window.location.href = '/photos.html';
    } catch (error) {
      console.error('Upload failed:', error && error.code);
      setStatus(errorMessage(error));
      submitButton.disabled = false;
      submitButton.textContent = 'Save';
    }
  });
});
