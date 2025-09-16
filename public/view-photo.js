document.addEventListener('DOMContentLoaded', function() {
  try {
    const functions = firebase.functions();

    // Get the photo ID from the URL query string
    const urlParams = new URLSearchParams(window.location.search);
    const photoId = urlParams.get('id');
    const container = document.getElementById('photo-detail-container');
    const scanButton = document.getElementById('scan-photo-button');
    const cameraInput = document.getElementById('camera-input');
    const statusMessage = document.getElementById('status-message');
    
    if (!photoId) {
        container.innerHTML = '<h3>Error: No photo ID specified.</h3>';
        return;
    }

    // Call our backend function to get the enriched photo data
    const getPhotoDetailsCallable = functions.httpsCallable('getphotodetails');
    getPhotoDetailsCallable({ photoId: photoId })
      .then(result => {
        const photo = result.data;
        
        // --- NEW: Logic to build the Related Photos HTML ---
        let relatedPhotosHtml = ''; // Start with an empty string
        // Check if the (enriched) relatedPhotos array exists and has items
        if (photo.relatedPhotos && photo.relatedPhotos.length > 0) {
            // Start building the list
            relatedPhotosHtml = `
                <h4><strong>Related photos</strong></h4>
                <ul>
            `;
            
            // Loop through each related photo and create a list item with a link
            photo.relatedPhotos.forEach(related => {
              // 1. Start the list item.
              relatedPhotosHtml += `<li>`; 
              
              // 2. Add the blue, hyperlinked text (only the name).
              relatedPhotosHtml += `<a href="/view-photo.html?id=${related.id}"><strong>${related.name}</strong></a>`;
              
              // 3. Add the non-hyperlinked relationship text, separated by a line break.
              if (related.text) {
                  // Use a <br> to force a newline, followed by the text.
                  // We wrap the text in a span just to ensure no unintended styling is applied,
                  // but it will inherit the default font size.
                  relatedPhotosHtml += `<br><span class="related-photo-detail">${related.text}</span>`;
              }
              
              // 4. Close the list item.
              relatedPhotosHtml += `</li>`;
          });

            // Close the list
            relatedPhotosHtml += '</ul>';
        }

        // --- UPDATED: The main HTML template ---
        // It now removes the old "People" field and includes our new relatedPhotosHtml block.
        container.innerHTML = `
            <h3 style="font-size: 24px;"><strong>${photo.name || 'Untitled'}</strong></h3>
            <p style="font-size: 16px"><i>Scroll to learn more</i></p>
            <hr>
            <img src="${photo.imageUrl}" class="img-responsive" alt="${photo.description || 'Gallery photo'}">
            <hr>
            <p><strong>Date:</strong> ${photo.date || 'Unknown'}</p>
            <p class="photo-description"><strong>Description:</strong> ${photo.description || 'No description.'}</p>
            ${relatedPhotosHtml} 
        `;
      })
      .catch(error => {
        console.error("Error fetching photo details:", error);
        container.innerHTML = `<h3>Error: ${error.message}</h3>`;
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
    document.getElementById('photo-detail-container').innerHTML = '<h3>Error loading page. Check the console.</h3>';
  }
});