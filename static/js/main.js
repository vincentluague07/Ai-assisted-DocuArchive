// AiDocArchive - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Theme toggle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.body.classList.toggle('dark-mode', savedTheme === 'dark');
        updateThemeIcon(savedTheme);
        
        themeToggle.addEventListener('click', function() {
            const isDark = document.body.classList.toggle('dark-mode');
            const theme = isDark ? 'dark' : 'light';
            localStorage.setItem('theme', theme);
            updateThemeIcon(theme);
        });
    }
    
    function updateThemeIcon(theme) {
        const icon = themeToggle?.querySelector('i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }
    
    // Sidebar toggle for mobile
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('open');
        });
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
                    sidebar.classList.remove('open');
                }
            }
        });
    }
});

// Global utility functions
window.formatFileSize = function(bytes) {
    if (!bytes) return 'Unknown';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return `${bytes.toFixed(1)} ${units[i]}`;
};

window.formatDate = function(dateStr) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString();
};

window.formatDateTime = function(dateStr) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString();
};

window.escapeHtml = function(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

// Toast notifications
window.showToast = function(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas ${getToastIcon(type)}"></i>
        <span>${escapeHtml(message)}</span>
    `;
    
    const container = document.getElementById('toastContainer') || createToastContainer();
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 12px;';
    document.body.appendChild(container);
    return container;
}

function getToastIcon(type) {
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    return icons[type] || icons.info;
}

// Add toast styles dynamically
const toastStyles = document.createElement('style');
toastStyles.textContent = `
    .toast {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 20px;
        background: var(--bg-secondary);
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transform: translateX(100%);
        opacity: 0;
        transition: all 0.3s ease;
    }
    .toast.show {
        transform: translateX(0);
        opacity: 1;
    }
    .toast-success { border-left: 4px solid #22c55e; }
    .toast-error { border-left: 4px solid #ef4444; }
    .toast-warning { border-left: 4px solid #f59e0b; }
    .toast-info { border-left: 4px solid #3b82f6; }
    .toast-success i { color: #22c55e; }
    .toast-error i { color: #ef4444; }
    .toast-warning i { color: #f59e0b; }
    .toast-info i { color: #3b82f6; }
`;
document.head.appendChild(toastStyles);
