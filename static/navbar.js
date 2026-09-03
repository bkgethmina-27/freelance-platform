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

  const mode = localStorage.getItem('nm_mode') === 'client' ? 'client' : 'freelancer';

  const freelancerLinks = `
    <a href="/gigs.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Post a Gig</a>
    <a href="/sprint.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Progress Tracker</a>
  `;
  const clientLinks = `
    <a href="/index.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Marketplace</a>
    <a href="/verify.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Milestones</a>
  `;

  container.innerHTML = `
    <header style="background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; width: 100%; box-sizing: border-box; flex-wrap: wrap; gap: 0.75rem;">
      <div style="font-size: 1.5rem; font-weight: 800;">
        <a href="/index.html" style="text-decoration: none; color: #1e40af;">NextMarket</a>
      </div>
      <nav style="display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;">
        ${user ? `
          <div style="display: flex; border: 1px solid #cbd5e1; border-radius: 9999px; padding: 0.2rem; background: #f1f5f9;">
            <button id="mode-freelancer" style="border: none; padding: 0.35rem 0.9rem; border-radius: 9999px; font-weight: 600; font-size: 0.85rem; cursor: pointer; ${mode === 'freelancer' ? 'background: #2563eb; color: #fff;' : 'background: transparent; color: #64748b;'}">Freelancer</button>
            <button id="mode-client" style="border: none; padding: 0.35rem 0.9rem; border-radius: 9999px; font-weight: 600; font-size: 0.85rem; cursor: pointer; ${mode === 'client' ? 'background: #2563eb; color: #fff;' : 'background: transparent; color: #64748b;'}">Client</button>
          </div>
          ${mode === 'client' ? clientLinks : freelancerLinks}
          <a href="/profile.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Profile (${user.full_name.split(' ')[0]})</a>
          <button id="logout-btn" style="background: transparent; border: 1px solid #cbd5e1; padding: 0.4rem 0.8rem; border-radius: 0.375rem; font-weight: 600; cursor: pointer; color: #475569;">Logout</button>
        ` : `
          <a href="/index.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Marketplace</a>
          <a href="/login.html" style="text-decoration: none; color: #475569; font-weight: 600; font-size: 0.95rem;">Log In</a>
          <a href="/register.html" style="background: #2563eb; color: #ffffff; padding: 0.5rem 1rem; border-radius: 0.375rem; text-decoration: none; font-weight: 600; font-size: 0.95rem;">Get Started</a>
        `}
      </nav>
    </header>
  `;

  const freelancerBtn = document.getElementById('mode-freelancer');
  const clientBtn = document.getElementById('mode-client');
  if (freelancerBtn) {
    freelancerBtn.addEventListener('click', () => {
      localStorage.setItem('nm_mode', 'freelancer');
      window.location.href = '/gigs.html';
    });
  }
  if (clientBtn) {
    clientBtn.addEventListener('click', () => {
      localStorage.setItem('nm_mode', 'client');
      window.location.href = '/index.html';
    });
  }

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      window.location.href = '/login.html';
    });
  }
});