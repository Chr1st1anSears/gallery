document.addEventListener('DOMContentLoaded', function() {
  try {
    const auth = firebase.auth();

    const loginContainer = document.getElementById('login-container');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const userInfo = document.getElementById('user-info');
    const userName = document.getElementById('user-name');

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

  } catch (e) {
    console.error(e);
  }
});