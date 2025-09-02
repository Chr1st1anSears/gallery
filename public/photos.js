document.addEventListener('DOMContentLoaded', function() {
  try {
    // Initialize Firebase services
    const auth = firebase.auth();
    const functions = firebase.functions();

    // Get references to all the HTML elements
    const loginContainer = document.getElementById('login-container');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const userInfo = document.getElementById('user-info');
    const userName = document.getElementById('user-name');
    const addPhotoButton = document.getElementById('add-photo-button');
    const photoGalleryContainer = document.getElementById('photo-gallery-container');
    const loadingMessage = document.getElementById('loading-message');

    // --- CHANGE #1: The function now accepts a boolean, isLoggedIn ---
    const loadPhotos = async (isLoggedIn) => {
      loadingMessage.textContent = "Loading photos...";
      photoGalleryContainer.innerHTML = '';
      try {
        const getPhotosCallable = functions.httpsCallable('getphotos');
        const result = await getPhotosCallable();
        const photos = result.data;

        if (photos.length === 0) {
          loadingMessage.textContent = 'No photos found.';
          return;
        }

        photos.forEach(photo => {
          const photoElement = document.createElement('div');
          photoElement.className = 'media';

          // --- CHANGE #2: Conditionally create the buttons ---
          // If the user is logged in, create the buttons HTML. Otherwise, create an empty string.
          const adminButtons = isLoggedIn ? `
            <div class="media-right">
                <a href="/edit-photo.html?id=${photo.id}" class="btn btn-default btn-sm">Edit</a>
                <button class="btn btn-danger btn-sm delete-button" data-id="${photo.id}">Delete</button>
            </div>
          ` : '';

          // --- CHANGE #3: Add the buttons (or the empty string) to the template ---
          photoElement.innerHTML = `
            <a href="/view-photo.html?id=${photo.id}">
              <div class="media-left" style="width: 320px; display: flex;">
                  <img src="${photo.imageUrl}" style="max-width: 300px; max-height: 250px;" alt="gallery photo">
              </div>
              <div class="media-body">
                  <h4>${photo.name || 'Untitled'}</h4>
                  <p><strong>Date:</strong> ${photo.date || 'Unknown'}</p>
              </div>
            </a>
            ${adminButtons}
          `;
          photoGalleryContainer.appendChild(photoElement);
        });
        loadingMessage.style.display = 'none';
      } catch (error) {
        console.error("Error fetching photos:", error);
        loadingMessage.textContent = "Error loading photos. Check the console.";
      }
    };

    // Authentication state observer
    auth.onAuthStateChanged(user => {
      if (user) {
        userName.textContent = user.displayName || user.email;
        userInfo.style.display = 'block';
        addPhotoButton.style.display = 'inline-block';
        loginContainer.style.display = 'none';
        loadPhotos(true);
      } else {
        userName.textContent = '';
        userInfo.style.display = 'none';
        addPhotoButton.style.display = 'none';
        loginContainer.style.display = 'block';
        
        loadPhotos(false)
      }
    });

    // Button Click Handlers
    loginButton.addEventListener('click', () => {
      const provider = new firebase.auth.GoogleAuthProvider();
      auth.signInWithPopup(provider).catch(error => console.error("Sign-in error:", error));
    });

    logoutButton.addEventListener('click', () => {
      auth.signOut().catch(error => console.error("Sign-out error:", error));
    });

    // --- MOVED: Event listener for delete buttons ---
    // This now lives inside the main try-catch block with the other listeners.
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

  } catch (e) {
    console.error(e);
    document.getElementById('loading-message').textContent = 'Error loading Firebase SDK.';
  }
});