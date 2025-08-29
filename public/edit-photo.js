document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const functions = firebase.functions();

    // Get the photo ID from the URL query string (e.g., ?id=12345)
    const urlParams = new URLSearchParams(window.location.search);
    const photoId = urlParams.get('id');

    // Get form elements
    const editPhotoForm = document.getElementById('edit-photo-form');
    const descriptionInput = document.getElementById('description');
    const peopleInput = document.getElementById('peopleInPhoto');
    const dateInput = document.getElementById('dateTaken');
    const submitButton = document.getElementById('submit-button');
    
    if (!photoId) {
        document.querySelector('.container').innerHTML = '<h3>Error: No photo ID specified.</h3>';
        return;
    }

    auth.onAuthStateChanged(user => {
      if (user) {
        // --- User is logged in, fetch the photo details ---
        const getPhotoDetailsCallable = functions.httpsCallable('getphotodetails');
        getPhotoDetailsCallable({ photoId: photoId })
          .then(result => {
            const photo = result.data;
            // Populate the form with the photo's data
            descriptionInput.value = photo.description || '';
            peopleInput.value = photo.peopleInPhoto || '';
            dateInput.value = photo.dateTaken || '';
          })
          .catch(error => {
            console.error("Error fetching photo details:", error);
            document.querySelector('.container').innerHTML = `<h3>Error: ${error.message}</h3>`;
          });
      } else {
        // Redirect if not logged in
        window.location.href = '/';
      }
    });

    // Handle form submission
    editPhotoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        submitButton.disabled = true;
        submitButton.textContent = 'Saving...';

        const updatedData = {
            description: descriptionInput.value,
            peopleInPhoto: peopleInput.value,
            dateTaken: dateInput.value
        };

        try {
            const editPhotoCallable = functions.httpsCallable('editphoto');
            await editPhotoCallable({ photoId: photoId, updatedData: updatedData });
            window.location.href = '/'; // Redirect home on success
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