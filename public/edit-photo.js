document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const functions = firebase.functions();

    // --- Get all necessary DOM elements ---
    const urlParams = new URLSearchParams(window.location.search);
    const photoId = urlParams.get('id');
    const editPhotoForm = document.getElementById('edit-photo-form');
    const nameInput = document.getElementById('name');
    const dateInput = document.getElementById('date');
    const descriptionInput = document.getElementById('description');
    const submitButton = document.getElementById('submit-button');
    const relatedPhotosContainer = document.getElementById('related-photos-container');
    const addRelatedPhotoButton = document.getElementById('add-related-photo-button');
    
    let allPhotos = []; // This will store the list of all photos for our dropdowns

    if (!photoId) {
        document.querySelector('.container').innerHTML = '<h3>Error: No photo ID specified.</h3>';
        return;
    }

    // --- Main Authorization and Data Fetching ---
    auth.onAuthStateChanged(user => {
      if (user) {
        // NEW: We need to fetch two sets of data: the details for *this* photo,
        // and the list of *all* photos for the dropdowns. We'll run them in parallel.
        fetchAllData();
      } else {
        window.location.href = '/photos.html';
      }
    });

    const fetchAllData = async () => {
        try {
            const getPhotoDetailsCallable = functions.httpsCallable('getphotodetails');
            const getPhotosCallable = functions.httpsCallable('getphotos');

            // Use Promise.all to fetch both sets of data concurrently for speed
            const [detailsResult, photosResult] = await Promise.all([
                getPhotoDetailsCallable({ photoId: photoId }),
                getPhotosCallable()
            ]);

            const photoToEdit = detailsResult.data;
            allPhotos = photosResult.data.map(p => ({ id: p.id, name: p.name }));

            // Now that we have all the data, populate the entire form
            populateForm(photoToEdit);

        } catch (error) {
            console.error("Error fetching data:", error);
            document.querySelector('.container').innerHTML = `<h3>Error: ${error.message}</h3>`;
        }
    };

    // --- NEW: A central function to populate the form fields ---
    const populateForm = (photo) => {
        nameInput.value = photo.name || '';
        dateInput.value = photo.date || '';
        descriptionInput.value = photo.description || '';

        // If there are existing related photos, create rows for them
        if (photo.relatedPhotos && photo.relatedPhotos.length > 0) {
            photo.relatedPhotos.forEach(related => {
                addNewRelatedPhotoRow(related);
            });
        }
    };

    // --- UPDATED: This function can now take optional data to pre-fill a row ---
    const addNewRelatedPhotoRow = (data = null) => {
        const row = document.createElement('div');
        row.className = 'row related-photo-row';
        row.style.marginBottom = '10px';

        // Filter out the current photo from the dropdown list to prevent self-linking
        const availablePhotos = allPhotos.filter(p => p.id !== photoId);

        const selectHTML = `<option value="">-- Select a Photo --</option>` + 
            availablePhotos.map(p => 
                `<option value="${p.id}" ${data && data.id === p.id ? 'selected' : ''}>${p.name}</option>`
            ).join('');
        
        const textValue = data ? data.text : '';

        row.innerHTML = `
            <div class="col-xs-6"><select class="form-control">${selectHTML}</select></div>
            <div class="col-xs-5"><input type="text" class="form-control" placeholder="Relationship" value="${textValue}"></div>
            <div class="col-xs-1" style="text-align: right;"><button type="button" class="btn btn-danger btn-xs">&times;</button></div>
        `;
        relatedPhotosContainer.appendChild(row);
    };

    // --- Event listeners for adding/removing rows (same as add-photo.js) ---
    addRelatedPhotoButton.addEventListener('click', () => addNewRelatedPhotoRow());
    relatedPhotosContainer.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON' && e.target.className.includes('btn-danger')) {
            e.target.closest('.related-photo-row').remove();
        }
    });

    // --- UPDATED: Form submission logic ---
    editPhotoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        submitButton.disabled = true;
        submitButton.textContent = 'Saving...';

        // NEW: Gather the 'relatedPhotos' data from the UI
        const relatedPhotosData = [];
        const rows = relatedPhotosContainer.querySelectorAll('.related-photo-row');
        rows.forEach(row => {
            const selectedPhotoId = row.querySelector('select').value;
            const relationshipText = row.querySelector('input').value;
            if (selectedPhotoId) { 
                relatedPhotosData.push({ id: selectedPhotoId, text: relationshipText });
            }
        });

        const updatedData = {
            name: nameInput.value,
            date: dateInput.value,
            description: descriptionInput.value,
            relatedPhotos: relatedPhotosData // Include the new array in the update
        };

        try {
            const editPhotoCallable = functions.httpsCallable('editphoto');
            await editPhotoCallable({ photoId: photoId, updatedData: updatedData });
            window.location.href = '/photos.html';
        } catch (error) {
            console.error("Error updating photo:", error);
            alert(`Error: ${error.message}`);
            submitButton.disabled = false;
            submitButton.textContent = 'Save Changes';
        }
    });

  } catch (e) {
    console.error(e);
  }
});