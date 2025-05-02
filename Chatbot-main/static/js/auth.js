document.addEventListener('DOMContentLoaded', function() {
    // Handle form submissions
    const signupForm = document.getElementById('signupForm');
    const loginForm = document.getElementById('loginForm');
    
    if (signupForm) {
        signupForm.addEventListener('submit', handleAuthForm);
    }
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleAuthForm);
    }
});

async function handleAuthForm(e) {
    e.preventDefault();
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Disable button during submission
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Processing...';
    
    try {
        const formData = new FormData(form);
        const url = form.id === 'signupForm' ? '/signup' : '/login';
        
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'Accept': 'application/json'
            }
        });
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            const data = await response.json();
            
            if (data.success) {
                if (data.redirect) {
                    window.location.href = data.redirect;
                }
            } else {
                showAlert('error', data.error || 'Authentication failed');
            }
        } else {
            // Handle HTML response (like redirects)
            window.location.href = response.url;
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('error', 'An error occurred. Please try again.');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = form.id === 'signupForm' ? 'Sign Up' : 'Log In';
    }
}

function showAlert(type, message) {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.alert');
    existingAlerts.forEach(alert => alert.remove());
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const authCard = document.querySelector('.auth-card');
    if (authCard) {
        authCard.insertBefore(alertDiv, authCard.firstChild);
        
        // Remove alert after 5 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }
}