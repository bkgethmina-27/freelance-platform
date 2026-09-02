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
    <header style="background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; width: 100%; box-sizing: border-box;">
      <div style="font-size: 1.5rem; font-weight: 800;">
        <a href="/index.html" style="text-decoration: none; color: #1e40af;">NextMarket</a>
      </div>
      <nav style="display: flex; align-items: center; gap: 1.5rem;">
        <a href="/index.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Marketplace</a>
        ${user ? `
          <a href="/gigs.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Post a Gig</a>
          <a href="/sprint.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Progress Tracker</a>
          <a href="/verify.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Milestones</a>
          <a href="/profile.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Profile (${user.full_name.split(' ')[0]})</a>
          <button id="logout-btn" style="background: transparent; border: 1px solid #cbd5e1; padding: 0.4rem 0.8rem; border-radius: 0.375rem; font-weight: 600; cursor: pointer; color: #475569;">Logout</button>
        ` : `
          <a href="/login.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Log In</a>
          <a href="/register.html" style="background: #2563eb; color: #ffffff; padding: 0.5rem 1rem; border-radius: 0.375rem; text-decoration: none; font-weight: 600; font-size: 0.95rem;">Get Started</a>
        `}
      </nav>
    </header>
  `;

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      window.location.href = '/login.html';
    });
  }
});