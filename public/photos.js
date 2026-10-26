// photos.js — the full list of photos, with editor controls for editors.
document.addEventListener('DOMContentLoaded', () => {
  const { el, photoUrl, safeImageUrl, errorMessage } = Gallery;
  const functions = firebase.functions();

  const addPhotoButton = document.getElementById('add-photo-button');
  const container = document.getElementById('photo-gallery-container');
  const loadingMessage = document.getElementById('loading-message');
  const statusMessage = document.getElementById('status-message');

  let photos = null; // Cached list so auth changes don't refetch.
  let editorMode = false;

  const deleteButton = (photo) => {
    // Two-step confirm (no blocking confirm() dialog).
    const button = el('button', { type: 'button', className: 'btn btn-danger btn-sm', text: 'Delete' });
    let armed = false;
    button.addEventListener('click', async () => {
      if (!armed) {
        armed = true;
        button.textContent = 'Click again to delete';
        setTimeout(() => { armed = false; button.textContent = 'Delete'; }, 4000);
        return;
      }
      button.disabled = true;
      button.textContent = 'Deleting...';
      try {
        await functions.httpsCallable('deletephoto')({ photoId: photo.id });
        photos = photos.filter((p) => p.id !== photo.id);
        render();
      } catch (error) {
        statusMessage.textContent = errorMessage(error);
        button.disabled = false;
        button.textContent = 'Delete';
        armed = false;
      }
    });
    return button;
  };

  const render = () => {
    container.replaceChildren();
    if (!photos.length) {
      loadingMessage.textContent = 'No photos found.';
      loadingMessage.style.display = '';
      return;
    }
    loadingMessage.style.display = 'none';

    for (const photo of photos) {
      const link = el('a', { href: photoUrl(photo.id) }, [
        el('div', { className: 'media-left', style: { width: '320px', display: 'flex' } }, [
          el('img', {
            src: safeImageUrl(photo.imageUrl),
            alt: photo.name || 'Gallery photo',
            loading: 'lazy',
            style: { maxWidth: '300px', maxHeight: '250px' },
          }),
        ]),
        el('div', { className: 'media-body' }, [
          el('h4', { style: { fontSize: '20px' } }, [el('strong', { text: photo.name || 'Untitled' })]),
          el('p', { text: photo.date || 'Unknown date' }),
        ]),
      ]);

      const adminButtons = editorMode
        ? el('div', { className: 'media-right' }, [
            el('a', {
              href: '/edit-photo.html?id=' + encodeURIComponent(photo.id),
              className: 'btn btn-default btn-sm',
              text: 'Edit',
            }),
            deleteButton(photo),
          ])
        : null;

      container.appendChild(el('div', { className: 'media' }, [link, adminButtons]));
    }
  };

  const loadPhotos = async () => {
    if (photos) return render();
    loadingMessage.textContent = 'Loading photos...';
    try {
      const result = await functions.httpsCallable('getphotos')();
      photos = Array.isArray(result.data) ? result.data : [];
      render();
    } catch (error) {
      console.error('Error fetching photos:', error && error.code);
      loadingMessage.textContent = 'Error loading photos. Please try again later.';
    }
  };

  try {
    Gallery.initScan();
    Gallery.initAuthNav((user, editor) => {
      editorMode = editor;
      addPhotoButton.style.display = editor ? 'inline-block' : 'none';
      loadPhotos();
    });
  } catch (e) {
    loadingMessage.textContent = 'An error occurred initializing the app.';
  }
});
