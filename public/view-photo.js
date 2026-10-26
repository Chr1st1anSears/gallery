// view-photo.js — a single photo with its story and related photos.
document.addEventListener('DOMContentLoaded', () => {
  const { el, photoUrl, safeImageUrl, errorMessage } = Gallery;
  const container = document.getElementById('photo-detail-container');
  const photoId = new URLSearchParams(window.location.search).get('id');

  const showError = (message) => container.replaceChildren(el('h3', { text: message }));

  try {
    Gallery.initScan();
  } catch (e) {
    console.error('Failed to initialize scanning.');
  }

  if (!photoId) {
    showError('Error: No photo ID specified.');
    return;
  }

  const relatedPhotosSection = (related) => {
    if (!Array.isArray(related) || !related.length) return null;
    return el('div', null, [
      el('h4', null, [el('strong', { text: 'Related photos' })]),
      el('ul', null, related.map((r) =>
        el('li', null, [
          el('a', { href: photoUrl(r.id) }, [el('strong', { text: r.name || 'Unknown Photo' })]),
          r.text ? el('br') : null,
          r.text ? el('span', { className: 'related-photo-detail', text: r.text }) : null,
        ])
      )),
    ]);
  };

  firebase.functions().httpsCallable('getphotodetails')({ photoId })
    .then(({ data: photo }) => {
      document.title = (photo.name || 'Photo') + ' - Gallery';
      container.replaceChildren(
        el('h3', { style: { fontSize: '24px' } }, [el('strong', { text: photo.name || 'Untitled' })]),
        el('p', { style: { fontSize: '16px' } }, [el('i', { text: 'Scroll to learn more' })]),
        el('hr'),
        el('img', {
          src: safeImageUrl(photo.imageUrl),
          className: 'img-responsive',
          alt: photo.name || 'Gallery photo',
        }),
        el('hr'),
        el('p', null, [el('strong', { text: 'Date:' }), ' ' + (photo.date || 'Unknown')]),
        // .photo-description uses white-space: pre-wrap to keep line breaks.
        el('p', { className: 'photo-description' }, [
          el('strong', { text: 'Description:' }),
          ' ' + (photo.description || 'No description.'),
        ]),
        relatedPhotosSection(photo.relatedPhotos)
      );
    })
    .catch((error) => {
      console.error('Error fetching photo details:', error && error.code);
      showError('Error: ' + errorMessage(error));
    });
});
