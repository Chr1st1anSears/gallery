// photo-form.js — shared "Related Photos" editor for the Add and Edit pages.
(function () {
  'use strict';
  const { el } = Gallery;

  /**
   * Creates a related-photos editor inside `container`.
   *   allPhotos: [{id, name}] used to fill the dropdowns
   *   excludeId: photo ID to leave out (prevents linking a photo to itself)
   * Returns { addRow(data?), getValue() }.
   */
  function createRelatedPhotosEditor(container, allPhotos, excludeId) {
    const choices = allPhotos.filter((p) => p.id !== excludeId);

    const addRow = (data) => {
      const select = el('select', { className: 'form-control', 'aria-label': 'Related photo' }, [
        el('option', { value: '', text: '-- Select a Photo --' }),
        ...choices.map((p) => {
          const option = el('option', { value: p.id, text: p.name || 'Untitled' });
          if (data && data.id === p.id) option.selected = true;
          return option;
        }),
      ]);
      const text = el('input', {
        type: 'text',
        className: 'form-control',
        placeholder: 'Relationship (e.g., husband, sister)',
        maxlength: '300',
        'aria-label': 'Relationship',
      });
      text.value = (data && data.text) || '';

      const row = el('div', { className: 'row related-photo-row', style: { marginBottom: '10px' } });
      const remove = el('button', {
        type: 'button',
        className: 'btn btn-danger btn-xs',
        'aria-label': 'Remove related photo',
        text: '\u00d7',
        onclick: () => row.remove(),
      });
      row.append(
        el('div', { className: 'col-xs-6' }, [select]),
        el('div', { className: 'col-xs-5' }, [text]),
        el('div', { className: 'col-xs-1', style: { textAlign: 'right' } }, [remove])
      );
      container.appendChild(row);
    };

    const getValue = () =>
      Array.from(container.querySelectorAll('.related-photo-row'))
        .map((row) => ({ id: row.querySelector('select').value, text: row.querySelector('input').value }))
        .filter((r) => r.id);

    return { addRow, getValue };
  }

  /** Fetches [{id, name}] for the dropdowns. */
  async function fetchPhotoChoices() {
    const result = await firebase.functions().httpsCallable('getphotos')();
    return (result.data || []).map((p) => ({ id: p.id, name: p.name }));
  }

  /**
   * Redirects away unless the current user is an editor.
   * Resolves with the user once confirmed.
   */
  function requireEditor() {
    return new Promise((resolve) => {
      const unsubscribe = firebase.auth().onAuthStateChanged(async (user) => {
        unsubscribe();
        if (user && (await Gallery.isEditor(user, true))) {
          resolve(user);
        } else {
          window.location.replace('/photos.html');
        }
      });
    });
  }

  window.GalleryForm = { createRelatedPhotosEditor, fetchPhotoChoices, requireEditor };
})();
