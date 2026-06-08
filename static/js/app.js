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
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (msg.parentNode) {
                msg.style.opacity = '0';
                msg.style.transition = 'opacity 0.5s';
                setTimeout(() => msg.remove(), 500);
            }
        }, 5000);
    });
});
