document.addEventListener('DOMContentLoaded', function() {
    // Global event listeners
    document.querySelectorAll('.nav-button').forEach(button => {
        button.addEventListener('click', handleNavigation);
    });

    // Session timer
    let sessionTimer = null;
    
    function handleNavigation(event) {
        event.preventDefault();
        const target = event.target.dataset.target;
        window.location.href = `/${target}`;
    }

    // Input validation for registration/login forms
    document.querySelectorAll('input[type="password"]').forEach(input => {
        input.addEventListener('input', function() {
            if (this.value.length < 8) {
                this.setCustomValidity('Password must be at least 8 characters');
            } else {
                this.setCustomValidity('');
            }
        });
    });

    // Accessibility enhancements
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('.modal');
            modals.forEach(modal => modal.style.display = 'none');
        }
    });

    // Service worker registration
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js')
            .then(registration => {
                console.log('ServiceWorker registration successful');
            })
            .catch(err => {
                console.log('ServiceWorker registration failed: ', err);
            });
    }
});