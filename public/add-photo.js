document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const storage = firebase.storage();
    const functions = firebase.functions();

    // --- Get all necessary DOM elements ---
    const addPhotoForm = document.getElementById('add-photo-form');
    const uploadInput = document.getElementById('image-upload');
    const cameraInput = document.getElementById('camera-input');
    const fileNameDisplay = document.getElementById('file-name');
    const submitButton = document.getElementById('submit-button');
    const relatedPhotosContainer = document.getElementById('related-photos-container');
    const addRelatedPhotoButton = document.getElementById('add-related-photo-button');

    let currentUser = null;
    let selectedFile = null;
    let allPhotos = []; // NEW: This will store the list of all photos for our dropdowns

    // --- Main Authorization and Data Fetching ---
    auth.onAuthStateChanged(user => {
      if (user) {
        currentUser = user;
        // NEW: Once the user is logged in, fetch all photos to populate the dropdowns.
        fetchAllPhotos();
      } else {
        window.location.href = '/photos.html';
        currentUser = null;
      }
    });

    // --- NEW: Function to fetch all photos ---
    const fetchAllPhotos = async () => {
      try {
        const getPhotosCallable = functions.httpsCallable('getphotos');
        const result = await getPhotosCallable();
        // We only need the id and name for the dropdown
        allPhotos = result.data.map(photo => ({ id: photo.id, name: photo.name }));
        // Add the first empty row to the form now that we have the data
        addNewRelatedPhotoRow(); 
      } catch (error) {
        console.error("Error fetching photo list:", error);
        relatedPhotosContainer.innerHTML = '<p class="text-danger">Could not load photo list for dropdowns.</p>';
      }
    };

    // --- NEW: Function to create a single 'Related Photo' row UI ---
    const addNewRelatedPhotoRow = () => {
      const row = document.createElement('div');
      row.className = 'row related-photo-row'; // Bootstrap row for alignment
      row.style.marginBottom = '10px';

      // Create the dropdown (select) element
      const selectElement = document.createElement('select');
      selectElement.className = 'form-control';
      selectElement.innerHTML = `<option value="">-- Select a Photo --</option>` + 
        allPhotos.map(photo => `<option value="${photo.id}">${photo.name}</option>`).join('');

      // Create the text input for the relationship
      const textInput = document.createElement('input');
      textInput.type = 'text';
      textInput.className = 'form-control';
      textInput.placeholder = 'Relationship (e.g., husband, sister)';
      
      // Create the remove button
      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'btn btn-danger btn-xs';
      removeButton.innerHTML = '&times;'; // A simple 'x' character

      // Assemble the row using Bootstrap's grid system
      row.innerHTML = `
        <div class="col-xs-6"></div>
        <div class="col-xs-5"></div>
        <div class="col-xs-1" style="text-align: right;"></div>
      `;
      row.children[0].appendChild(selectElement);
      row.children[1].appendChild(textInput);
      row.children[2].appendChild(removeButton);

      relatedPhotosContainer.appendChild(row);
    };

    // --- Event listener for the 'Add another' button ---
    addRelatedPhotoButton.addEventListener('click', addNewRelatedPhotoRow);

    // --- NEW: Use event delegation to handle all 'remove' button clicks ---
    relatedPhotosContainer.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON' && e.target.className.includes('btn-danger')) {
        // Find the parent '.related-photo-row' and remove it
        e.target.closest('.related-photo-row').remove();
      }
    });

    // --- File selection logic (unchanged) ---
    const handleFileSelect = (e) => {
      if (e.target.files.length > 0) {
        selectedFile = e.target.files[0];
        fileNameDisplay.textContent = `Selected: ${selectedFile.name}`;
      }
    };
    uploadInput.addEventListener('change', handleFileSelect);
    cameraInput.addEventListener('change', handleFileSelect);

    // --- UPDATED: Form submission logic ---
    addPhotoForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (!currentUser || !selectedFile) {
        alert("You must be logged in and select a file to upload.");
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = 'Uploading...';
      
      try {
        const filePath = `${currentUser.uid}/${Date.now()}_${selectedFile.name}`;
        const storageRef = storage.ref(filePath);
        const uploadTask = await storageRef.put(selectedFile);
        const downloadURL = await uploadTask.ref.getDownloadURL();

        // --- NEW: Gather the 'relatedPhotos' data from the UI ---
        const relatedPhotosData = [];
        const rows = relatedPhotosContainer.querySelectorAll('.related-photo-row');
        rows.forEach(row => {
          const photoId = row.querySelector('select').value;
          const relationshipText = row.querySelector('input').value;
          // Only add it if a photo has been selected
          if (photoId) { 
            relatedPhotosData.push({ id: photoId, text: relationshipText });
          }
        });

        const addPhotoCallable = functions.httpsCallable('addphoto');
        await addPhotoCallable({
          imageUrl: downloadURL,
          name: document.getElementById('name').value,
          date: document.getElementById('date').value,
          description: document.getElementById('description').value,
          relatedPhotos: relatedPhotosData // Send the new array to the backend
        });

        window.location.href = '/photos.html';
      } catch (error) {
        console.error("Error in the upload process:", error);
        alert("An error occurred. Check the console.");
        submitButton.disabled = false;
        submitButton.textContent = 'Save';
      }
    });
  } catch (e) {
    console.error(e);
  }
});