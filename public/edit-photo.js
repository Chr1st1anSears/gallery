// edit-photo.js — edit an existing photo's details (editors only).
document.addEventListener('DOMContentLoaded', () => {
  const { el, errorMessage } = Gallery;
  const { createRelatedPhotosEditor, fetchPhotoChoices, requireEditor } = GalleryForm;

  const photoId = new URLSearchParams(window.location.search).get('id');
  const form = document.getElementById('edit-photo-form');
  const nameInput = document.getElementById('name');
  const dateInput = document.getElementById('date');
  const descriptionInput = document.getElementById('description');
  const submitButton = document.getElementById('submit-button');
  const relatedContainer = document.getElementById('related-photos-container');
  const addRelatedButton = document.getElementById('add-related-photo-button');
  const formStatus = document.getElementById('form-status');
  const mainContainer = document.getElementById('main-container');

  let related = null;

  const showFatal = (message) => mainContainer.replaceChildren(el('h3', { text: message }));

  if (!photoId) {
    showFatal('Error: No photo ID specified.');
    return;
  }

  requireEditor().then(async () => {
    try {
      const functions = firebase.functions();
      // Fetch this photo and the dropdown list in parallel.
      const [details, choices] = await Promise.all([
        functions.httpsCallable('getphotodetails')({ photoId }),
        fetchPhotoChoices(),
      ]);
      const photo = details.data;
      nameInput.value = photo.name || '';
      dateInput.value = photo.date || '';
      descriptionInput.value = photo.description || '';

      related = createRelatedPhotosEditor(relatedContainer, choices, photoId);
      (photo.relatedPhotos || []).forEach((r) => related.addRow(r));
    } catch (error) {
      console.error('Error fetching photo:', error && error.code);
      showFatal('Error: ' + errorMessage(error));
    }
  });

  addRelatedButton.addEventListener('click', () => related && related.addRow());

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitButton.disabled = true;
    submitButton.textContent = 'Saving...';
    formStatus.textContent = '';
    try {
      await firebase.functions().httpsCallable('editphoto')({
        photoId,
        updatedData: {
          name: nameInput.value,
          date: dateInput.value,
          description: descriptionInput.value,
          relatedPhotos: related ? related.getValue() : [],
        },
      });
      window.location.href = '/photos.html';
    } catch (error) {
      console.error('Error updating photo:', error && error.code);
      formStatus.textContent = errorMessage(error);
      submitButton.disabled = false;
      submitButton.textContent = 'Save Changes';
    }
  });
});
