// This function runs once the page is fully loaded.
document.addEventListener('DOMContentLoaded', function() {
  try {
    // Initialize Firebase services
    const auth = firebase.auth();
    const functions = firebase.functions(); // Add Functions service

    // Get references to all the HTML elements we need to interact with
    const loginContainer = document.getElementById('login-container');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const userInfo = document.getElementById('user-info');
    const userName = document.getElementById('user-name');
    const addPhotoButton = document.getElementById('add-photo-button');
    const photoGalleryContainer = document.getElementById('photo-gallery-container');
    const loadingMessage = document.getElementById('loading-message');

    // --- NEW: Function to load and display photos ---
    const loadPhotos = async () => {
      loadingMessage.textContent = "Loading photos...";
      photoGalleryContainer.innerHTML = ''; // Clear previous photos

      try {
        // Get a reference to our new Python Cloud Function
        const getPhotosCallable = functions.httpsCallable('getphotos');
        const result = await getPhotosCallable();
        const photos = result.data;

        if (photos.length === 0) {
          loadingMessage.textContent = 'No photos found. Add one!';
          return;
        }

        // Loop through the photos and create the HTML for each one
        photos.forEach(photo => {
          const photoElement = document.createElement('div');
          photoElement.className = 'media';
          photoElement.innerHTML = `
            <a href="/photos/${photo.id}">
              <div class="media-left">
                  <img src="${photo.imageUrl}" width="175" height="175" alt="gallery photo">
              </div>
              <div class="media-body">
                  <h4>${photo.description || ''}</h4>
                  <p><strong>People:</strong> ${photo.peopleInPhoto || 'Unknown'}</p>
                  <p><strong>Date:</strong> ${photo.dateTaken || 'Unknown'}</p>
              </div>
            </a>
            <div class="media-right">
                <a href="/edit-photo.html?id=${photo.id}" class="btn btn-default btn-sm">Edit</a>
                <button class="btn btn-danger btn-sm delete-button" data-id="${photo.id}">Delete</button>
            </div>
          `;
          photoGalleryContainer.appendChild(photoElement);
        });

        loadingMessage.style.display = 'none'; // Hide loading message
      } catch (error) {
        console.error("Error fetching photos:", error);
        loadingMessage.textContent = "Error loading photos. Check the console.";
      }
    };


    // --- Authentication Logic ---
    auth.onAuthStateChanged(user => {
      if (user) {
        // --- User is SIGNED IN ---
        userName.textContent = user.displayName || user.email;
        userInfo.style.display = 'block';
        addPhotoButton.style.display = 'inline-block';
        loginContainer.style.display = 'none';
        
        // Now that the user is logged in, load their photos.
        loadPhotos();

      } else {
        // --- User is SIGNED OUT ---
        userName.textContent = '';
        userInfo.style.display = 'none';
        addPhotoButton.style.display = 'none';
        loginContainer.style.display = 'block';
        photoGalleryContainer.innerHTML = ''; // Clear photos
        loadingMessage.style.display = 'block';
        loadingMessage.textContent = "Please sign in to view the gallery.";
      }
    });

    // --- Button Click Handlers ---
    loginButton.addEventListener('click', () => {
      const provider = new firebase.auth.GoogleAuthProvider();
      auth.signInWithPopup(provider).catch(error => console.error("Sign-in error:", error));
    });

    logoutButton.addEventListener('click', () => {
      auth.signOut().catch(error => console.error("Sign-out error:", error));
    });

  } catch (e) {
    console.error(e);
    document.getElementById('loading-message').textContent = 'Error loading Firebase SDK.';
  }

// --- NEW: Event listener for delete buttons ---
// We use event delegation since the buttons are created dynamically.
photoGalleryContainer.addEventListener('click', async (e) => {
    if (e.target.classList.contains('delete-button')) {
        const photoId = e.target.dataset.id;
        
        if (confirm("Are you sure you want to delete this photo?")) {
            try {
                const deletePhotoCallable = functions.httpsCallable('deletephoto');
                await deletePhotoCallable({ photoId: photoId });
                // Reload the photos to show the change
                loadPhotos();
            } catch (error) {
                console.error("Error deleting photo:", error);
                alert(`Error: ${error.message}`);
            }
        }
    }
});
});