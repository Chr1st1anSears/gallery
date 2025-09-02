document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const functions = firebase.functions();

    // Get the photo ID from the URL query string (e.g., ?id=12345)
    const urlParams = new URLSearchParams(window.location.search);
    const photoId = urlParams.get('id');

    // Get form elements
    const editPhotoForm = document.getElementById('edit-photo-form');
    const nameInput = document.getElementById('name');
    const dateInput = document.getElementById('date');
    const peopleInput = document.getElementById('people');
    const descriptionInput = document.getElementById('description');
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
            // Populate the form with the new data fields
            nameInput.value = photo.name || '';
            dateInput.value = photo.date || '';
            peopleInput.value = photo.people || '';
            descriptionInput.value = photo.description || '';
          })
          .catch(error => {
            console.error("Error fetching photo details:", error);
            document.querySelector('.container').innerHTML = `<h3>Error: ${error.message}</h3>`;
          });
      } else {
        // Redirect if not logged in
        window.location.href = '/photos.html';
      }
    });

    // Handle form submission
    editPhotoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        submitButton.disabled = true;
        submitButton.textContent = 'Saving...';

        const updatedData = {
            name: nameInput.value,
            date: dateInput.value,
            people: peopleInput.value,
            description: descriptionInput.value
        };

        try {
            const editPhotoCallable = functions.httpsCallable('editphoto');
            await editPhotoCallable({ photoId: photoId, updatedData: updatedData });
            window.location.href = '/photos.html'; // Redirect home on success
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