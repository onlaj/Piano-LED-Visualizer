/**
 * Custom Alert and Confirm Notification System
 * Glassmorphism-styled notifications with stacking and auto-dismiss
 */

(function() {
    'use strict';

    // Alert container and confirm modal elements
    let alertContainer = null;
    let confirmOverlay = null;
    let confirmModal = null;
    let activeAlerts = [];

    /**
     * Initialize notification system
     */
    function init() {
        // Create alert container if it doesn't exist
        if (!alertContainer) {
            alertContainer = document.getElementById('notification-container');
            if (!alertContainer) {
                alertContainer = document.createElement('div');
                alertContainer.id = 'notification-container';
                document.body.appendChild(alertContainer);
            }
        }

        // Create confirm modal if it doesn't exist
        if (!confirmOverlay) {
            confirmOverlay = document.createElement('div');
            confirmOverlay.id = 'confirm-overlay';
            confirmOverlay.className = 'confirm-overlay';
            
            confirmModal = document.createElement('div');
            confirmModal.className = 'confirm-modal';
            
            const messageDiv = document.createElement('div');
            messageDiv.className = 'confirm-message';
            messageDiv.id = 'confirm-message-text';
            
            const buttonsDiv = document.createElement('div');
            buttonsDiv.className = 'confirm-buttons';
            
            const okButton = document.createElement('button');
            okButton.className = 'confirm-btn confirm-btn-ok';
            okButton.textContent = 'OK';
            okButton.id = 'confirm-ok-btn';
            
            const cancelButton = document.createElement('button');
            cancelButton.className = 'confirm-btn confirm-btn-cancel';
            cancelButton.textContent = 'Cancel';
            cancelButton.id = 'confirm-cancel-btn';
            
            buttonsDiv.appendChild(okButton);
            buttonsDiv.appendChild(cancelButton);
            
            confirmModal.appendChild(messageDiv);
            confirmModal.appendChild(buttonsDiv);
            confirmOverlay.appendChild(confirmModal);
            
            document.body.appendChild(confirmOverlay);
        }
    }

    /**
     * Show an alert notification
     * @param {string} message - The message to display
     * @param {string} type - Alert type: 'info', 'warning', or 'error' (default: 'info')
     */
    function showAlert(message, type = 'info') {
        if (!message) return;

        init();

        // Create alert element
        const alert = document.createElement('div');
        alert.className = `notification-alert notification-${type}`;
        
        // Create content wrapper
        const content = document.createElement('div');
        content.className = 'notification-content';
        
        // Create icon based on type
        const icon = document.createElement('div');
        icon.className = 'notification-icon';
        
        let iconSvg = '';
        if (type === 'error') {
            iconSvg = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>';
        } else if (type === 'warning') {
            iconSvg = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>';
        } else {
            iconSvg = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>';
        }
        icon.innerHTML = iconSvg;
        
        // Create message text
        const text = document.createElement('div');
        text.className = 'notification-text';
        text.textContent = message;
        
        // Create close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'notification-close';
        closeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>';
        closeBtn.setAttribute('aria-label', 'Close');
        
        content.appendChild(icon);
        content.appendChild(text);
        alert.appendChild(content);
        alert.appendChild(closeBtn);
        
        // Add to container
        alertContainer.appendChild(alert);
        activeAlerts.push(alert);
        
        // Trigger animation
        requestAnimationFrame(() => {
            alert.classList.add('show');
        });
        
        // Auto-dismiss after 5 seconds
        const dismissTimer = setTimeout(() => {
            dismissAlert(alert);
        }, 5000);
        
        // Manual close handler
        const closeHandler = () => {
            clearTimeout(dismissTimer);
            dismissAlert(alert);
        };
        
        closeBtn.addEventListener('click', closeHandler);
        alert.addEventListener('click', (e) => {
            // Close on click anywhere on alert (except if clicking on close button which is handled above)
            if (e.target === alert || e.target.closest('.notification-content')) {
                closeHandler();
            }
        });
        
        return alert;
    }

    /**
     * Dismiss an alert with animation
     * @param {HTMLElement} alert - The alert element to dismiss
     */
    function dismissAlert(alert) {
        if (!alert || !alert.parentNode) return;
        
        alert.classList.remove('show');
        alert.classList.add('hide');
        
        setTimeout(() => {
            if (alert.parentNode) {
                alert.parentNode.removeChild(alert);
            }
            const index = activeAlerts.indexOf(alert);
            if (index > -1) {
                activeAlerts.splice(index, 1);
            }
        }, 300); // Match CSS transition duration
    }

    /**
     * Show a confirm dialog
     * @param {string} message - The message to display
     * @param {Function} onConfirm - Callback when user confirms
     * @param {Function} onCancel - Optional callback when user cancels
     * @returns {Promise<boolean>} Promise that resolves to true if confirmed, false if cancelled
     */
    function showConfirm(message, onConfirm, onCancel) {
        init();

        return new Promise((resolve) => {
            const messageText = document.getElementById('confirm-message-text');
            const okBtn = document.getElementById('confirm-ok-btn');
            const cancelBtn = document.getElementById('confirm-cancel-btn');
            
            // Set message
            messageText.textContent = message;
            
            // Remove existing event listeners by cloning
            const newOkBtn = okBtn.cloneNode(true);
            const newCancelBtn = cancelBtn.cloneNode(true);
            okBtn.parentNode.replaceChild(newOkBtn, okBtn);
            cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
            
            // Show overlay
            confirmOverlay.classList.add('show');
            document.body.style.overflow = 'hidden';
            
            // Confirm handler
            const confirmHandler = () => {
                hideConfirm();
                resolve(true);
                if (onConfirm) onConfirm();
            };
            
            // Cancel handler
            const cancelHandler = () => {
                hideConfirm();
                resolve(false);
                if (onCancel) onCancel();
            };
            
            newOkBtn.addEventListener('click', confirmHandler);
            newCancelBtn.addEventListener('click', cancelHandler);
            
            // Close on overlay click (outside modal)
            const overlayClickHandler = (e) => {
                if (e.target === confirmOverlay) {
                    cancelHandler();
                }
            };
            confirmOverlay.addEventListener('click', overlayClickHandler);
            
            // Close on Escape key
            const escapeHandler = (e) => {
                if (e.key === 'Escape') {
                    cancelHandler();
                    document.removeEventListener('keydown', escapeHandler);
                }
            };
            document.addEventListener('keydown', escapeHandler);
        });
    }

    /**
     * Hide confirm modal
     */
    function hideConfirm() {
        if (confirmOverlay) {
            confirmOverlay.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    // Expose functions globally
    window.showAlert = showAlert;
    window.showConfirm = showConfirm;

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

