document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();
    const functions = firebase.functions();
    const AUTHORIZED_USERS = [
        "crsears1995@gmail.com",
        "crsears@google.com",
        "vorobyshek077@gmail.com",
        "vorobeva@bc.edu",
    ];  
    const loginContainer = document.getElementById('login-container');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const userInfo = document.getElementById('user-info');
    const userName = document.getElementById('user-name');
    const addPhotoButton = document.getElementById('add-photo-button');
    const photoGalleryContainer = document.getElementById('photo-gallery-container');
    const loadingMessage = document.getElementById('loading-message');

    const loadPhotos = async (isAuthorized) => {
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

          // Conditionally create the buttons if the user is authorized
          const adminButtons = isAuthorized ? `
            <div class="media-right">
                <a href="/edit-photo.html?id=${photo.id}" class="btn btn-default btn-sm">Edit</a>
                <button class="btn btn-danger btn-sm delete-button" data-id="${photo.id}">Delete</button>
            </div>
          ` : '';

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

    auth.onAuthStateChanged(user => {
      if (user) {
        // User is logged in.
        userName.textContent = user.displayName || user.email;
        userInfo.style.display = 'block';
        loginContainer.style.display = 'none';

        // Check if their email is in our allowlist.
        const isAuthorized = AUTHORIZED_USERS.includes(user.email);

        // Show/hide the "Add Photo" button based on authorization.
        addPhotoButton.style.display = isAuthorized ? 'inline-block' : 'none';
        
        // Load the photo list, passing authorization status to show/hide edit/delete buttons.
        loadPhotos(isAuthorized);

      } else {
        // User is logged out.
        userName.textContent = '';
        userInfo.style.display = 'none';
        addPhotoButton.style.display = 'none';
        loginContainer.style.display = 'block';
        
        // Load photos without any admin controls.
        loadPhotos(false);
      }
    });

    // --- Button Click Handlers (Unchanged) ---
    loginButton.addEventListener('click', () => {
      const provider = new firebase.auth.GoogleAuthProvider();
      auth.signInWithPopup(provider).catch(error => console.error("Sign-in error:", error));
    });

    logoutButton.addEventListener('click', () => {
      auth.signOut().catch(error => console.error("Sign-out error:", error));
    });

    photoGalleryContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('delete-button')) {
            const photoId = e.target.dataset.id;
            
            if (confirm("Are you sure you want to delete this photo?")) {
                try {
                    const deletePhotoCallable = functions.httpsCallable('deletephoto');
                    await deletePhotoCallable({ photoId: photoId });
                    // Reload photos, assuming user is still authorized.
                    loadPhotos(true);
                } catch (error) {
                    console.error("Error deleting photo:", error);
                    alert(`Error: ${error.message}`);
                }
            }
        }
    });

  } catch (e) {
    console.error(e);
    document.getElementById('loading-message').textContent = 'An error occurred initializing the app.';
  }
});