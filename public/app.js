document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const functions = firebase.functions();

    // --- References for the Navbar ---
    const loginContainer = document.getElementById('login-container');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const userInfo = document.getElementById('user-info');
    const userName = document.getElementById('user-name');

    // --- References for the new Visual Search UI ---
    const scanButton = document.getElementById('scan-photo-button');
    const cameraInput = document.getElementById('camera-input');
    const statusMessage = document.getElementById('status-message');

    // --- Navbar Auth Logic (remains the same) ---
    auth.onAuthStateChanged(user => {
      if (user) {
        userName.textContent = user.displayName || user.email;
        userInfo.style.display = 'block';
        loginContainer.style.display = 'none';
      } else {
        userName.textContent = '';
        userInfo.style.display = 'none';
        loginContainer.style.display = 'block';
      }
    });

    loginButton.addEventListener('click', () => {
      const provider = new firebase.auth.GoogleAuthProvider();
      auth.signInWithPopup(provider).catch(error => console.error("Sign-in error:", error));
    });

    logoutButton.addEventListener('click', () => {
      auth.signOut().catch(error => console.error("Sign-out error:", error));
    });

    // --- NEW: Visual Search Logic ---

    // When the user clicks the "Scan a Photo" button, trigger the hidden file input
    scanButton.addEventListener('click', () => {
      cameraInput.click();
    });

    // When a photo is captured by the camera, this event will fire
    cameraInput.addEventListener('change', async (e) => {
      if (e.target.files.length > 0) {
        const file = e.target.files[0];
        statusMessage.textContent = 'Analyzing photo...';
        scanButton.disabled = true;

        try {
          // Convert the image to a Base64 string to send to the function
          const base64Image = await toBase64(file);
          
          // Call our new backend function to find the match
          const findPhotoByMatchCallable = functions.httpsCallable('findphotobymatch');
          const result = await findPhotoByMatchCallable({ image: base64Image });
          
          const photoId = result.data.photoId;
          
          if (photoId) {
            statusMessage.textContent = 'Match found! Redirecting...';
            // Redirect to the view-photo page for the matched photo
            window.location.href = `/view-photo.html?id=${photoId}`;
          } else {
            statusMessage.textContent = 'Sorry, no close match was found.';
            scanButton.disabled = false;
          }
        } catch (error) {
          console.error("Error during visual search:", error);
          statusMessage.textContent = `An error occurred: ${error.message}`;
          scanButton.disabled = false;
        }
      }
    });

    // A helper function to convert a file to a Base64 string
    const toBase64 = file => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result.split(',')[1]); // Get only the data part
        reader.onerror = error => reject(error);
    });

  } catch (e) {
    console.error(e);
  }
});
