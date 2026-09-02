async function renderNavbar() {
    const navContainer = document.getElementById('navbar-container');
    if (!navContainer) return;

    let user = null;
    try {
        const res = await fetch('http://127.0.0.1:5000/api/auth/me');
        if (res.ok) {
            user = await res.json();
        }
    } catch (e) {
        console.log("Not logged in");
    }

    let authLinks = '';
    let roleLinks = '';

    if (user) {
        const initial = user.full_name ? user.full_name.charAt(0).toUpperCase() : 'U';
        if (user.role === 'freelancer') {
            roleLinks += `<li><a href="/sprint.html">14-Day Sprint</a></li>`;
        }
        roleLinks += `<li><a href="/gigs.html">Manage Gigs</a></li>`;
        roleLinks += `<li><a href="/verify.html">Milestones</a></li>`;

        authLinks = `
            ${roleLinks}
            <li>
                <a href="/profile.html" class="profile-badge">
                    <div class="profile-avatar">${initial}</div>
                    <span>${user.full_name.split(' ')[0]}</span>
                </a>
            </li>
            <li><button id="navLogoutBtn">Logout</button></li>
        `;
    } else {
        authLinks = `
            <li><a href="/verify.html">Milestones</a></li>
            <li><a href="/login.html">Login</a></li>
            <li><a href="/register.html" class="btn-nav">Get Started</a></li>
        `;
    }

    navContainer.innerHTML = `
        <nav class="navbar">
            <div class="nav-container">
                <a href="/index.html" class="logo">NextMarket</a>
                <ul class="nav-links">
                    <li><a href="/index.html">Marketplace</a></li>
                    ${authLinks}
                </ul>
            </div>
        </nav>
    `;

    const logoutBtn = document.getElementById('navLogoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('http://127.0.0.1:5000/api/auth/logout', { method: 'POST' });
            window.location.href = '/login.html';
        });
    }
}

document.addEventListener('DOMContentLoaded', renderNavbar);