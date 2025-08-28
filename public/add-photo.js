// public/add-photo.js

document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const storage = firebase.storage();
    // const functions = firebase.functions(); // We'll use this later
    // const db = firebase.firestore(); // We'll use this later

    const addPhotoForm = document.getElementById('add-photo-form'); // Make sure your <form> has this ID
    const fileInput = document.getElementById('image'); // Your <input type="file">
    const submitButton = document.getElementById('submit-button'); // Your submit button

    let currentUser = null;

    auth.onAuthStateChanged(user => {
      if (user) {
        currentUser = user;
      } else {
        // If user is not logged in, redirect them to the home page
        window.location.href = '/';
        currentUser = null;
      }
    });

    addPhotoForm.addEventListener('submit', async (e) => {
      e.preventDefault(); // Stop the form from submitting the traditional way

      if (!currentUser || !fileInput.files.length) {
        alert("You must be logged in and select a file to upload.");
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = 'Uploading...';

      // 1. Get the selected file
      const file = fileInput.files[0];
      const filePath = `${currentUser.uid}/${Date.now()}_${file.name}`;
      const storageRef = storage.ref(filePath);

      try {
        // 2. Upload the file to Cloud Storage
        const uploadTask = await storageRef.put(file);
        console.log('File uploaded successfully!');

        // 3. Get the public URL of the uploaded file
        const downloadURL = await uploadTask.ref.getDownloadURL();
        console.log('File available at', downloadURL);

        // --- NEXT STEP will go here ---
        // 4. Call a Cloud Function to save metadata to Firestore
        
        alert("Photo uploaded successfully! (Next step is saving the details)");
        window.location.href = '/'; // Redirect home for now

      } catch (error) {
        console.error("Error uploading file:", error);
        alert("Error uploading file. Check the console.");
        submitButton.disabled = false;
        submitButton.textContent = 'Save';
      }
    });

  } catch (e) {
    console.error(e);
    // Handle error loading Firebase SDK
  }
});