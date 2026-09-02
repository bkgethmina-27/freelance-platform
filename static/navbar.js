document.addEventListener('DOMContentLoaded', async () => {
  const container = document.getElementById('navbar-container');
  if (!container) return;

  let user = null;
  try {
    const res = await fetch('/api/auth/me');
    if (res.ok) {
      user = await res.json();
    }
  } catch (err) {
    console.log('User not logged in');
  }

  container.innerHTML = `
    <nav class="navbar">
      <div class="navbar-brand">
        <a href="/index.html"><strong>NextMarket</strong></a>
      </div>
      <div class="navbar-links">
        <a href="/index.html">Marketplace</a>
        ${user ? `
          <a href="/sprint.html">Progress Tracker</a>
          <a href="/verify.html">Milestones</a>
          <a href="/profile.html">My Profile (${user.full_name.split(' ')[0]})</a>
          <button id="logout-btn" class="btn btn-outline" style="margin-left:10px;">Logout</button>
        ` : `
          <a href="/login.html">Log In</a>
          <a href="/register.html" class="btn btn-primary" style="margin-left:10px;">Get Started</a>
        `}
      </div>
    </nav>
  `;

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      window.location.href = '/login.html';
    });
  }
});