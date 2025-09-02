document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const storage = firebase.storage();
    const functions = firebase.functions();

    const addPhotoForm = document.getElementById('add-photo-form');
    // NEW: Get references to both inputs and the filename display
    const uploadInput = document.getElementById('image-upload');
    const cameraInput = document.getElementById('camera-input');
    const fileNameDisplay = document.getElementById('file-name');
    const submitButton = document.getElementById('submit-button');
    
    let currentUser = null;
    // NEW: A variable to hold the selected file
    let selectedFile = null;

    auth.onAuthStateChanged(user => {
      if (user) {
        currentUser = user;
      } else {
        window.location.href = '/photos.html';
        currentUser = null;
      }
    });

    // NEW: A function to handle when a file is selected from either input
    const handleFileSelect = (e) => {
        if (e.target.files.length > 0) {
            selectedFile = e.target.files[0];
            fileNameDisplay.textContent = `Selected: ${selectedFile.name}`;
        }
    };
    
    // NEW: Attach this handler to both inputs
    uploadInput.addEventListener('change', handleFileSelect);
    cameraInput.addEventListener('change', handleFileSelect);

    addPhotoForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      // CHANGED: Check if our selectedFile variable is set
      if (!currentUser || !selectedFile) {
        alert("You must be logged in and select a file to upload.");
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = 'Uploading...';
      
      // Use the globally stored selectedFile
      const file = selectedFile;
      const filePath = `${currentUser.uid}/${Date.now()}_${file.name}`;
      const storageRef = storage.ref(filePath);

      try {
        // The rest of this function remains the same
        const uploadTask = await storageRef.put(file);
        const downloadURL = await uploadTask.ref.getDownloadURL();

        const name = document.getElementById('name').value;
        const date = document.getElementById('date').value;
        const people = document.getElementById('people').value;
        const description = document.getElementById('description').value;

        const addPhotoCallable = functions.httpsCallable('addphoto');
        await addPhotoCallable({
            imageUrl: downloadURL,
            name: name,
            date: date,
            people: people,
            description: description
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