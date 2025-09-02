document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const storage = firebase.storage();
    const functions = firebase.functions(); // Make sure Functions is initialized

    const addPhotoForm = document.getElementById('add-photo-form');
    const fileInput = document.getElementById('image');
    const submitButton = document.getElementById('submit-button');
    let currentUser = null;

    auth.onAuthStateChanged(user => {
      if (user) {
        currentUser = user;
      } else {
        window.location.href = '/';
        currentUser = null;
      }
    });

    addPhotoForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (!currentUser || !fileInput.files.length) {
        alert("You must be logged in and select a file to upload.");
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = 'Uploading...';

      const file = fileInput.files[0];
      const filePath = `${currentUser.uid}/${Date.now()}_${file.name}`;
      const storageRef = storage.ref(filePath);

      try {
        // 1. Upload the file to Cloud Storage
        const uploadTask = await storageRef.put(file);
        
        // 2. Get the public URL of the uploaded file
        const downloadURL = await uploadTask.ref.getDownloadURL();

        // --- UPDATED SECTION ---
        // 3. Get the other form details
        const name = document.getElementById('name').value;
        const date = document.getElementById('date').value;
        const people = document.getElementById('people').value;
        const description = document.getElementById('description').value;

        // Call the 'addphoto' Cloud Function with the new details
        const addPhotoCallable = functions.httpsCallable('addphoto');
        await addPhotoCallable({
            imageUrl: downloadURL,
            name: name,
            date: date,
            people: people,
            description: description
        });


        // 5. Redirect home to see the new photo in the gallery
        window.location.href = '/';

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