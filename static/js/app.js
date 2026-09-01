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
    // Mobile sidebar toggle
    const menuToggle = document.querySelector('[data-menu-toggle]');
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            document.body.classList.toggle('menu-open');
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

    // SKU Auto-generator button
    const skuGenBtn = document.getElementById('btn-generate-sku');
    const skuField = document.querySelector('input[name="sku"]');
    if (skuGenBtn && skuField) {
        skuGenBtn.addEventListener('click', () => {
            const randomNum = Math.floor(100000 + Math.random() * 900000);
            const generated = `MTX-${randomNum}`;
            skuField.value = generated;
            showToast(`Generated SKU: ${generated}`, 'success');
        });
    }
});
