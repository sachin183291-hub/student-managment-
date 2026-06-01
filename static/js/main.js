// ─── Sidebar Toggle ───
const sidebar = document.getElementById('sidebar');
const mainWrapper = document.getElementById('mainWrapper');
const sidebarToggle = document.getElementById('sidebarToggle');
const mobileToggle = document.getElementById('mobileToggle');

if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        mainWrapper.classList.toggle('expanded');
        const icon = sidebarToggle.querySelector('i');
        icon.className = sidebar.classList.contains('collapsed') ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });
}

if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
        sidebar.classList.toggle('mobile-open');
    });
    document.addEventListener('click', (e) => {
        if (!sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
            sidebar.classList.remove('mobile-open');
        }
    });
}

// Restore sidebar state
if (localStorage.getItem('sidebarCollapsed') === 'true') {
    sidebar?.classList.add('collapsed');
    mainWrapper?.classList.add('expanded');
    const icon = sidebarToggle?.querySelector('i');
    if (icon) icon.className = 'bi bi-chevron-right';
}

// ─── Global Search ───
const globalSearch = document.getElementById('globalSearch');
const searchDropdown = document.getElementById('searchDropdown');

if (globalSearch) {
    let searchTimeout;
    globalSearch.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        const q = globalSearch.value.trim();
        if (q.length < 2) {
            searchDropdown.classList.remove('show');
            searchDropdown.innerHTML = '';
            return;
        }
        searchTimeout = setTimeout(async () => {
            try {
                const res = await fetch(`/students/search-suggestions?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                if (data.length === 0) {
                    searchDropdown.innerHTML = '<div class="search-item text-muted-custom">No results found</div>';
                } else {
                    searchDropdown.innerHTML = data.map(s =>
                        `<a href="/students/${s.id}" class="search-item">
              <div class="student-avatar-sm">${s.name[0]}</div>
              <div>
                <div style="font-weight:600;font-size:13px">${s.name}</div>
                <span class="search-item-roll">${s.roll}</span>
              </div>
            </a>`
                    ).join('');
                }
                searchDropdown.classList.add('show');
            } catch (e) {
                console.error(e);
            }
        }, 300);
    });

    document.addEventListener('click', (e) => {
        if (!globalSearch.contains(e.target) && !searchDropdown.contains(e.target)) {
            searchDropdown.classList.remove('show');
        }
    });
}

// ─── Auto Dismiss Alerts ───
document.querySelectorAll('.alert-custom').forEach(alert => {
    setTimeout(() => {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        bsAlert.close();
    }, 5000);
});

// ─── Confirm Delete ───
document.querySelectorAll('.confirm-delete').forEach(btn => {
    btn.addEventListener('click', (e) => {
        if (!confirm('Are you sure you want to delete this record? This action cannot be undone.')) {
            e.preventDefault();
        }
    });
});

// ─── Topbar date ───
const dateEl = document.querySelector('.topbar-date');
if (dateEl) {
    const now = new Date();
    const opts = { day: '2-digit', month: 'short', year: 'numeric' };
    dateEl.innerHTML = `<i class="bi bi-calendar3"></i> ${now.toLocaleDateString('en-IN', opts)}`;
}

// ─── Active filter highlight ───
document.querySelectorAll('.filter-bar select, .filter-bar input').forEach(el => {
    if (el.value) el.style.borderColor = 'var(--primary)';
    el.addEventListener('change', () => {
        el.style.borderColor = el.value ? 'var(--primary)' : '';
    });
});

// ─── Attendance % color helper (used inline) ───
function getAttColor(pct) {
    if (pct >= 75) return 'var(--success)';
    if (pct >= 60) return 'var(--warning)';
    return 'var(--danger)';
}

// ─── Mark All Present / Absent ───
const markAllPresent = document.getElementById('markAllPresent');
const markAllAbsent = document.getElementById('markAllAbsent');

if (markAllPresent) {
    markAllPresent.addEventListener('click', () => {
        document.querySelectorAll('input[value="present"]').forEach(r => r.checked = true);
    });
}
if (markAllAbsent) {
    markAllAbsent.addEventListener('click', () => {
        document.querySelectorAll('input[value="absent"]').forEach(r => r.checked = true);
    });
}

// ─── API Tester ───
async function testApi(method, url, body = null) {
    const responseEl = document.getElementById('apiResponse');
    if (!responseEl) return;
    responseEl.textContent = 'Loading...';
    try {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(url, opts);
        const data = await res.json();
        responseEl.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
        responseEl.textContent = 'Error: ' + e.message;
    }
}
