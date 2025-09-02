document.addEventListener('DOMContentLoaded', function() {
  try {
    const functions = firebase.functions();

    // Get the photo ID from the URL query string (e.g., ?id=12345)
    const urlParams = new URLSearchParams(window.location.search);
    const photoId = urlParams.get('id');

    const container = document.getElementById('photo-detail-container');
    
    if (!photoId) {
        container.innerHTML = '<h3>Error: No photo ID specified.</h3>';
        return;
    }

    // Call our existing backend function to get the photo's data
    const getPhotoDetailsCallable = functions.httpsCallable('getphotodetails');
    getPhotoDetailsCallable({ photoId: photoId })
      .then(result => {
        const photo = result.data;
        
        // Build the HTML with the photo data
        container.innerHTML = `
            <h3>${photo.name || 'Untitled'}</h3>
            <img src="${photo.imageUrl}" class="img-responsive" alt="${photo.description || 'Gallery photo'}">
            <hr>
            <h4>Details</h4>
            <p><strong>Date:</strong> ${photo.date || 'Unknown'}</p>
            <p><strong>People:</strong> ${photo.people || 'Unknown'}</p>
            <p><strong>Description:</strong> ${photo.description || 'No description.'}</p>
        `;
      })
      .catch(error => {
        console.error("Error fetching photo details:", error);
        container.innerHTML = `<h3>Error: ${error.message}</h3>`;
      });

  } catch (e) {
    console.error(e);
    document.getElementById('photo-detail-container').innerHTML = '<h3>Error loading page. Check the console.</h3>';
  }
});