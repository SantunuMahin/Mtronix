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
    // Sidebar toggle (desktop: hide/show + icon-only collapse; mobile <= 900px: drawer)
    const menuToggles = document.querySelectorAll('[data-menu-toggle]');
    const menuClosers = document.querySelectorAll('[data-menu-close]');
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

    menuToggles.forEach((btn) => {
        btn.addEventListener('click', () => {
            if (window.innerWidth <= 900) {
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
    });

    menuClosers.forEach((el) => {
        el.addEventListener('click', () => {
            document.body.classList.remove('menu-open');
        });
    });

    // Close mobile sidebar on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && document.body.classList.contains('menu-open')) {
            document.body.classList.remove('menu-open');
        }
    });

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

    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function enqueueSale(payload, receiptMeta = null) {
        const queue = getQueue();
        const shortCode = String(Date.now()).slice(-5);
        const entry = {
            id: `OFFLINE-${shortCode}`,
            queued_at: new Date().toISOString(),
            payload,
            receipt: receiptMeta,
        };
        queue.push(entry);
        saveQueue(queue);
        return entry;
    }

    function buildOfflineInvoiceHtml(entry) {
        const p = entry.payload || {};
        const r = entry.receipt || {};
        const items = r.items || p.items || [];
        const dt = new Date(entry.queued_at || Date.now());
        const dateStr = dt.toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: true,
        });

        let subtotal = 0;
        const rowsHtml = items.map((item, idx) => {
            const qty = parseInt(item.quantity, 10) || 0;
            const unitPrice = parseFloat(item.unit_price) || 0;
            const lineTotal = qty * unitPrice;
            subtotal += lineTotal;
            const name = escapeHtml(item.display_name || item.custom_name || `Product #${item.product || ''}`);
            const sku = item.sku ? `<div style="font-size:11px;color:#4b5563;">SKU: ${escapeHtml(item.sku)}</div>` : '';
            return `
                <tr>
                    <td style="text-align:center;font-weight:600;">${idx + 1}</td>
                    <td><div style="font-weight:700;">${name}</div>${sku}</td>
                    <td style="text-align:right;font-weight:600;">${qty}</td>
                    <td style="text-align:right;">${unitPrice.toFixed(2)}</td>
                    <td style="text-align:right;font-weight:700;">${lineTotal.toFixed(2)}</td>
                </tr>
            `;
        }).join('');

        const status = (p.payment_status || 'PAID').toUpperCase();
        let paidAmt = parseFloat(p.paid_amount) || 0;
        if (status === 'PAID') paidAmt = subtotal;
        else if (status === 'UNPAID') paidAmt = 0;
        else paidAmt = Math.min(subtotal, Math.max(0, paidAmt));
        const dueAmt = Math.max(0, subtotal - paidAmt);

        const custName = escapeHtml((p.customer_name || '').trim() || 'Walk-in Customer');
        const custPhone = p.customer_phone ? `<div>Phone: ${escapeHtml(p.customer_phone)}</div>` : '';
        const custAddr = p.customer_address ? `<div>Address: ${escapeHtml(p.customer_address)}</div>` : '';

        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Invoice #${escapeHtml(entry.id)} - Mtronix</title>
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color: #000; background: #fff; padding: 28px 34px; }
    .sheet { max-width: 780px; margin: 0 auto; min-height: 980px; display: flex; flex-direction: column; }
    .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; padding-bottom: 16px; border-bottom: 2px solid #000; margin-bottom: 18px; }
    .brand h1 { font-size: 22px; font-weight: 900; letter-spacing: 1px; margin-bottom: 4px; }
    .brand p { font-size: 11.5px; color: #333; line-height: 1.45; }
    .logo { max-height: 54px; width: auto; object-fit: contain; }
    .meta { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 18px; font-size: 12.5px; }
    .meta-box h3 { font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: #555; margin-bottom: 4px; }
    .badge { display: inline-block; padding: 2px 8px; border: 1.5px solid #000; font-size: 10.5px; font-weight: 800; border-radius: 4px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 12.5px; }
    th { text-align: left; border-top: 1.5px solid #000; border-bottom: 1.5px solid #000; padding: 8px 6px; font-size: 11px; text-transform: uppercase; }
    td { padding: 8px 6px; border-bottom: 1px solid #d1d5db; vertical-align: top; }
    .totals { margin-left: auto; width: 270px; font-size: 13px; }
    .tot-row { display: flex; justify-content: space-between; padding: 4px 0; }
    .tot-row.grand { border-top: 2px solid #000; margin-top: 6px; padding-top: 8px; font-size: 15px; font-weight: 900; }
    .bottom { margin-top: auto; padding-top: 48px; }
    .signs { display: flex; justify-content: space-between; gap: 40px; margin-bottom: 22px; }
    .sign-block { width: 210px; text-align: center; }
    .sign-line { border-top: 1.2px solid #000; margin-bottom: 6px; }
    .sign-title { font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .footer { border-top: 1px solid #d1d5db; padding-top: 10px; font-size: 10.5px; color: #4b5563; display: flex; justify-content: space-between; }
    @media print { body { padding: 0; } .sheet { min-height: 275mm; } }
</style>
</head>
<body>
<div class="sheet">
    <div>
        <div class="top">
            <div class="brand">
                <h1>MTRONIX</h1>
                <p>44/45, Madina Electric &amp; Electronics, (2nd floor), shop no. 3, 4. Kaptan Bazar, Dhaka.<br>
                Phone: 01744676770 &bull; Email: mtronix1203@gmail.com</p>
            </div>
            <img class="logo" src="/static/img/logo.png" alt="Mtronix" onerror="this.style.display='none'">
        </div>
        <div class="meta">
            <div class="meta-box">
                <h3>Bill To</h3>
                <div style="font-size:14px;font-weight:800;">${custName}</div>
                ${custPhone}
                ${custAddr}
            </div>
            <div class="meta-box" style="text-align:right;">
                <h3>Offline Invoice</h3>
                <div style="font-size:14px;font-weight:800;">#${escapeHtml(entry.id)}</div>
                <div>Date: ${escapeHtml(dateStr)}</div>
                <div style="margin-top:4px;"><span class="badge">${escapeHtml(status)}</span></div>
            </div>
        </div>
        <table>
            <thead>
                <tr>
                    <th style="width:42px;text-align:center;">SL</th>
                    <th>Description</th>
                    <th style="width:65px;text-align:right;">QTY</th>
                    <th style="width:105px;text-align:right;">Unit Price</th>
                    <th style="width:115px;text-align:right;">Amount</th>
                </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
        </table>
        <div class="totals">
            <div class="tot-row"><span>Subtotal</span><span>BDT ${subtotal.toFixed(2)}</span></div>
            <div class="tot-row"><span>Paid Amount</span><span>BDT ${paidAmt.toFixed(2)}</span></div>
            ${dueAmt > 0 ? `<div class="tot-row"><span>Due Amount</span><span><strong>BDT ${dueAmt.toFixed(2)}</strong></span></div>` : ''}
            <div class="tot-row grand"><span>Total (BDT)</span><span>BDT ${subtotal.toFixed(2)}</span></div>
        </div>
    </div>
    <div class="bottom">
        <div class="signs">
            <div class="sign-block">
                <div class="sign-line"></div>
                <div class="sign-title">Customer's Signature</div>
            </div>
            <div class="sign-block">
                <div class="sign-line"></div>
                <div class="sign-title">Authorized Signature</div>
            </div>
        </div>
        <div class="footer">
            <span><strong>Thank you for doing business with Mtronix!</strong></span>
            <span>Offline Invoice &bull; Pending Server Sync</span>
        </div>
    </div>
</div>
</body>
</html>`;
    }

    function printOfflineInvoice(entry) {
        if (!entry) return;
        const html = buildOfflineInvoiceHtml(entry);
        let iframe = document.getElementById('offline-invoice-print-frame');
        if (!iframe) {
            iframe = document.createElement('iframe');
            iframe.id = 'offline-invoice-print-frame';
            iframe.style.position = 'fixed';
            iframe.style.right = '0';
            iframe.style.bottom = '0';
            iframe.style.width = '0';
            iframe.style.height = '0';
            iframe.style.border = '0';
            document.body.appendChild(iframe);
        }
        const doc = iframe.contentWindow.document;
        doc.open();
        doc.write(html);
        doc.close();
        setTimeout(() => {
            try {
                iframe.contentWindow.focus();
                iframe.contentWindow.print();
            } catch (err) {
                const win = window.open('', '_blank');
                if (win) {
                    win.document.write(html);
                    win.document.close();
                    win.print();
                }
            }
        }, 200);
    }

    function printLastInvoice() {
        const queue = getQueue();
        if (!queue.length) return;
        printOfflineInvoice(queue[queue.length - 1]);
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

    return { getQueue, enqueueSale, syncQueue, printOfflineInvoice, printLastInvoice };
})();
