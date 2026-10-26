// app.js — homepage: sign-in and "Scan Photo".
document.addEventListener('DOMContentLoaded', () => {
  try {
    Gallery.initAuthNav();
    Gallery.initScan();
    // Only the visual-search function is warmed (it has the slowest cold
    // start). This is a single cheap call per homepage visit.
    Gallery.warmUpScan();
  } catch (e) {
    console.error('Failed to initialize the homepage.');
  }
});
