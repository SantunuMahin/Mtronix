// ─── Toast System ──────────────────────────────────────────────
function showToast(message, type = 'info') {
    let container = document.getElementById('mtronix-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'mtronix-toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast-msg';
    const icon = type === 'success' ? '✓' : (type === 'error' ? '✕' : 'ℹ');
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}

// ─── Copy to Clipboard Helper ──────────────────────────────────
function copyToClipboard(text, label = 'Text') {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(`${label} copied: "${text}"`, 'success');
        }).catch(() => fallbackCopy(text, label));
    } else {
        fallbackCopy(text, label);
    }
}

function fallbackCopy(text, label) {
    const tempInput = document.createElement('input');
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    try {
        document.execCommand('copy');
        showToast(`${label} copied: "${text}"`, 'success');
    } catch (err) {
        showToast(`Could not copy ${label}`, 'error');
    }
    document.body.removeChild(tempInput);
}

document.addEventListener('DOMContentLoaded', () => {
    // Sidebar toggle (desktop: hide/show + icon-only collapse; mobile: drawer)
    const menuToggle = document.querySelector('[data-menu-toggle]');
    const collapseBtn = document.getElementById('btn-sidebar-collapse');
    const rootEl = document.documentElement;

    function syncCollapseBtnIcon() {
        if (!collapseBtn) return;
        const isIcons = rootEl.classList.contains('sidebar-icons');
        collapseBtn.textContent = isIcons ? '»' : '«';
        collapseBtn.title = isIcons ? 'Expand sidebar' : 'Collapse to icons';
    }
    syncCollapseBtnIcon();

    if (collapseBtn) {
        collapseBtn.addEventListener('click', () => {
            rootEl.classList.remove('sidebar-hidden');
            const isIcons = rootEl.classList.toggle('sidebar-icons');
            localStorage.setItem('mtronix_sidebar_mode', isIcons ? 'icons' : 'expanded');
            syncCollapseBtnIcon();
        });
    }

    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            if (window.innerWidth <= 820) {
                document.body.classList.toggle('menu-open');
                return;
            }
            const isHidden = rootEl.classList.toggle('sidebar-hidden');
            if (isHidden) {
                localStorage.setItem('mtronix_sidebar_mode', 'hidden');
            } else {
                const isIcons = rootEl.classList.contains('sidebar-icons');
                localStorage.setItem('mtronix_sidebar_mode', isIcons ? 'icons' : 'expanded');
            }
        });
    }

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
        if (
            document.body.classList.contains('menu-open') &&
            !e.target.closest('.sidebar') &&
            !e.target.closest('[data-menu-toggle]')
        ) {
            document.body.classList.remove('menu-open');
        }
    });

    // Flash message auto-dismiss and close button
    document.querySelectorAll('.flash-message').forEach((msg) => {
        const closeBtn = msg.querySelector('.flash-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                msg.style.opacity = '0';
                msg.style.transition = 'opacity 0.3s';
                setTimeout(() => msg.remove(), 300);
            });
        }
        setTimeout(() => {
            if (msg.parentNode) {
                msg.style.opacity = '0';
                msg.style.transition = 'opacity 0.5s';
                setTimeout(() => msg.remove(), 500);
            }
        }, 5000);
    });

    // Click to copy SKU badges
    document.addEventListener('click', (e) => {
        const skuBadge = e.target.closest('[data-copy-sku]');
        if (skuBadge) {
            const skuVal = skuBadge.getAttribute('data-copy-sku');
            if (skuVal && skuVal !== '—') {
                copyToClipboard(skuVal, 'SKU');
            }
        }
    });

    // Live Product Pricing & Margin Calculator on Product Forms
    const purchaseInput = document.querySelector('input[name="purchase_price"]');
    const sellingInput = document.querySelector('input[name="selling_price"]');
    const profitEl = document.getElementById('calc-profit-val');
    const marginEl = document.getElementById('calc-margin-val');
    const markupEl = document.getElementById('calc-markup-val');

    function updateProductCalculations() {
        if (!profitEl || !marginEl || !markupEl) return;
        const purchase = parseFloat(purchaseInput?.value) || 0;
        const selling = parseFloat(sellingInput?.value) || 0;

        const profit = selling - purchase;
        const marginPct = selling > 0 ? ((profit / selling) * 100) : 0;
        const markupPct = purchase > 0 ? ((profit / purchase) * 100) : (selling > 0 ? 100 : 0);

        profitEl.textContent = `${profit >= 0 ? '+' : ''}BDT ${profit.toFixed(2)}`;
        profitEl.style.color = profit >= 0 ? '#047857' : '#dc2626';

        marginEl.textContent = `${marginPct.toFixed(1)}%`;
        marginEl.style.color = marginPct >= 0 ? '#0f766e' : '#dc2626';

        markupEl.textContent = `${markupPct.toFixed(1)}%`;
    }

    if (purchaseInput && sellingInput && profitEl) {
        purchaseInput.addEventListener('input', updateProductCalculations);
        sellingInput.addEventListener('input', updateProductCalculations);
        updateProductCalculations();
    }

    // ─── Service Worker & Network Status Indicator ────────────────
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
    }

    function updateNetworkStatusUI() {
        const pill = document.getElementById('network-status-pill');
        const dot = document.getElementById('network-status-dot');
        const text = document.getElementById('network-status-text');
        if (!pill || !dot || !text) return;

        if (navigator.onLine) {
            pill.style.background = 'rgba(16, 185, 129, 0.14)';
            pill.style.color = '#6ee7b7';
            dot.style.background = '#10b981';
            text.textContent = 'Online • Ready';
        } else {
            pill.style.background = 'rgba(245, 158, 11, 0.18)';
            pill.style.color = '#fcd34d';
            dot.style.background = '#f59e0b';
            text.textContent = 'Offline • Local Mode';
        }
    }

    updateNetworkStatusUI();
    window.addEventListener('online', () => {
        updateNetworkStatusUI();
        if (window.mtronixOfflineQueue) {
            window.mtronixOfflineQueue.syncQueue();
        }
    });
    window.addEventListener('offline', updateNetworkStatusUI);
});

// ─── Offline POS Sale Queue ───────────────────────────────────
window.mtronixOfflineQueue = (() => {
    const STORAGE_KEY = 'mtronix_offline_sales_queue';

    function getCookie(name) {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
    }

    function getQueue() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        } catch (e) {
            return [];
        }
    }

    function saveQueue(queue) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
        window.dispatchEvent(new CustomEvent('mtronix:queue-updated', { detail: { count: queue.length } }));
    }

    function enqueueSale(payload) {
        const queue = getQueue();
        queue.push({
            id: `OFFLINE-${Date.now()}`,
            queued_at: new Date().toISOString(),
            payload,
        });
        saveQueue(queue);
        return queue.length;
    }

    async function syncQueue() {
        const queue = getQueue();
        if (!queue.length || !navigator.onLine) return { synced: 0, remaining: queue.length };

        const remaining = [];
        let synced = 0;

        for (const entry of queue) {
            try {
                const resp = await fetch('/api/sales/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(entry.payload),
                });
                if (resp.ok) {
                    synced += 1;
                } else {
                    remaining.push(entry);
                }
            } catch (err) {
                remaining.push(entry);
            }
        }

        saveQueue(remaining);
        if (synced > 0) {
            showToast(`Synced ${synced} offline sale(s) to server.`, 'success');
        }
        return { synced, remaining: remaining.length };
    }

    return { getQueue, enqueueSale, syncQueue };
})();
