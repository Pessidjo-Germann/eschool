// Modern eSchool JavaScript - Enhanced User Experience

document.addEventListener('DOMContentLoaded', function() {
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Navbar scroll effect
    let lastScrollTop = 0;
    const navbar = document.querySelector('.modern-nav');
    
    window.addEventListener('scroll', function() {
        let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        if (scrollTop > 100) {
            navbar.style.background = 'rgba(255, 255, 255, 0.98)';
            navbar.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
        } else {
            navbar.style.background = 'rgba(255, 255, 255, 0.95)';
            navbar.style.boxShadow = 'none';
        }
        
        lastScrollTop = scrollTop;
    });

    // Add active class to current nav link
    const currentLocation = location.pathname;
    const navLinks = document.querySelectorAll('.modern-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentLocation) {
            link.classList.add('active');
        }
    });

    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
                entry.target.style.animationDelay = `${Array.from(entry.target.parentElement.children).indexOf(entry.target) * 0.1}s`;
            }
        });
    }, observerOptions);

    // Observe elements for animation
    document.querySelectorAll('.feature-card, .modern-card').forEach(card => {
        observer.observe(card);
    });

    // Enhanced dropdown behavior
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu');
        
        if (toggle && menu) {
            toggle.addEventListener('mouseenter', function() {
                menu.classList.add('show');
                toggle.setAttribute('aria-expanded', 'true');
            });
            
            dropdown.addEventListener('mouseleave', function() {
                menu.classList.remove('show');
                toggle.setAttribute('aria-expanded', 'false');
            });
        }
    });

    // Loading animation for buttons
    document.querySelectorAll('.modern-btn, .modern-btn-filled').forEach(button => {
        button.addEventListener('click', function(e) {
            if (!this.classList.contains('loading')) {
                this.classList.add('loading');
                
                // Create ripple effect
                const ripple = document.createElement('span');
                ripple.classList.add('ripple');
                this.appendChild(ripple);
                
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.width = ripple.style.height = size + 'px';
                ripple.style.left = x + 'px';
                ripple.style.top = y + 'px';
                
                setTimeout(() => {
                    ripple.remove();
                    this.classList.remove('loading');
                }, 600);
            }
        });
    });

    // Form enhancements
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            // Add floating labels effect
            input.addEventListener('focus', function() {
                this.parentElement.classList.add('focused');
            });
            
            input.addEventListener('blur', function() {
                if (!this.value) {
                    this.parentElement.classList.remove('focused');
                }
            });
            
            // Check if input has value on load
            if (input.value) {
                input.parentElement.classList.add('focused');
            }
        });
    });

    // Copy to clipboard functionality
    document.querySelectorAll('[data-copy]').forEach(button => {
        button.addEventListener('click', function() {
            const text = this.getAttribute('data-copy');
            navigator.clipboard.writeText(text).then(() => {
                // Show success feedback
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="bi bi-check"></i> Copié!';
                this.classList.add('btn-success');
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.classList.remove('btn-success');
                }, 2000);
            });
        });
    });

    // Theme toggle (if needed)
    const themeToggle = document.querySelector('[data-theme-toggle]');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('dark-theme');
            localStorage.setItem('theme', document.body.classList.contains('dark-theme') ? 'dark' : 'light');
        });
        
        // Apply saved theme
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-theme');
        }
    }

    // Progress indicator for long content
    const progressBar = document.createElement('div');
    progressBar.className = 'reading-progress';
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        z-index: 9999;
        transition: width 0.3s ease;
    `;
    document.body.appendChild(progressBar);

    window.addEventListener('scroll', function() {
        const scrolled = (window.pageYOffset / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
        progressBar.style.width = scrolled + '%';
    });

    console.log('🎓 eSchool loaded successfully!');

    // Authentication page enhancements
    if (document.querySelector('.auth-form')) {
        initAuthEnhancements();
    }
});

// Authentication page specific enhancements
function initAuthEnhancements() {
    const authForm = document.querySelector('.auth-form');
    const passwordInput = document.querySelector('#id_password1, #id_password');
    const confirmPasswordInput = document.querySelector('#id_password2');
    
    // Add loading state to form submission
    if (authForm) {
        authForm.addEventListener('submit', function() {
            this.classList.add('loading');
        });
    }
    
    // Real-time password validation
    if (passwordInput) {
        passwordInput.addEventListener('input', function() {
            const password = this.value;
            showPasswordStrength(password);
        });
    }
    
    // Confirm password validation
    if (confirmPasswordInput && passwordInput) {
        confirmPasswordInput.addEventListener('input', function() {
            const password = passwordInput.value;
            const confirmPassword = this.value;
            
            if (confirmPassword && password !== confirmPassword) {
                this.setCustomValidity('Les mots de passe ne correspondent pas');
                this.classList.add('is-invalid');
            } else {
                this.setCustomValidity('');
                this.classList.remove('is-invalid');
            }
        });
    }
    
    // Enhanced form field animations
    const formInputs = document.querySelectorAll('.modern-input');
    formInputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
            
            // Add a subtle scale animation
            this.style.transform = 'scale(1.02)';
        });
        
        input.addEventListener('blur', function() {
            this.style.transform = 'scale(1)';
            
            if (!this.value) {
                this.parentElement.classList.remove('focused');
            }
        });
        
        // Check if input has value on load
        if (input.value) {
            input.parentElement.classList.add('focused');
        }
    });
    
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
}

// Password strength indicator
function showPasswordStrength(password) {
    // Remove existing strength indicator if any
    const existingIndicator = document.querySelector('.password-strength');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    if (!password) return;
    
    const passwordInput = document.querySelector('#id_password1, #id_password');
    const strength = calculatePasswordStrength(password);
    
    const strengthIndicator = document.createElement('div');
    strengthIndicator.className = 'password-strength';
    strengthIndicator.innerHTML = `
        <div class="strength-bar ${strength.level >= 1 ? (strength.level === 1 ? 'weak' : strength.level === 2 ? 'medium' : 'strong') : ''}"></div>
        <div class="strength-bar ${strength.level >= 2 ? (strength.level === 2 ? 'medium' : 'strong') : ''}"></div>
        <div class="strength-bar ${strength.level >= 3 ? 'strong' : ''}"></div>
        <div class="strength-bar ${strength.level >= 4 ? 'strong' : ''}"></div>
    `;
    
    passwordInput.parentElement.appendChild(strengthIndicator);
    
    // Add strength text
    const strengthText = document.createElement('small');
    strengthText.className = 'strength-text mt-1 d-block';
    strengthText.style.color = strength.level <= 1 ? '#ef4444' : strength.level === 2 ? '#f59e0b' : '#10b981';
    strengthText.textContent = strength.text;
    
    strengthIndicator.appendChild(strengthText);
}

function calculatePasswordStrength(password) {
    let score = 0;
    let text = 'Très faible';
    
    // Length check
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    
    // Character variety checks
    if (/[a-z]/.test(password)) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    
    // Determine strength level and text
    if (score >= 5) {
        text = 'Très fort';
    } else if (score >= 4) {
        text = 'Fort';
    } else if (score >= 3) {
        text = 'Moyen';
    } else if (score >= 2) {
        text = 'Faible';
    }
    
    return {
        level: Math.min(Math.floor(score / 1.5), 4),
        text: text
    };
}

// Custom styles for eSchool project
