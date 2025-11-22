/**
 * Unified Number Input Module
 * 
 * Wraps number inputs with increment/decrement buttons that appear on focus.
 * Buttons are adjacent to the input with rounded edges, while the input loses
 * its roundness when focused.
 */

(function() {
    'use strict';

    /**
     * Initialize a single number input with buttons
     * @param {HTMLInputElement} input - The number input element
     */
    function initNumberInput(input) {
        // Skip if already initialized
        if (input.dataset.numberInputInitialized === 'true') {
            return;
        }

        // Skip if input is disabled, already wrapped, or explicitly excluded
        if (input.disabled || input.closest('.number-input-wrapper') || input.dataset.excludeNumberInput === 'true') {
            return;
        }

        // Mark as initialized
        input.dataset.numberInputInitialized = 'true';

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'number-input-wrapper';

        // Create decrement button
        const decrementBtn = document.createElement('button');
        decrementBtn.type = 'button';
        decrementBtn.className = 'number-input-btn number-input-btn-decrement';
        decrementBtn.innerHTML = '−';
        decrementBtn.setAttribute('aria-label', 'Decrease value');

        // Create increment button
        const incrementBtn = document.createElement('button');
        incrementBtn.type = 'button';
        incrementBtn.className = 'number-input-btn number-input-btn-increment';
        incrementBtn.innerHTML = '+';
        incrementBtn.setAttribute('aria-label', 'Increase value');

        // Store original parent and next sibling
        const parent = input.parentNode;
        const nextSibling = input.nextSibling;

        // Wrap the input
        wrapper.appendChild(decrementBtn);
        wrapper.appendChild(input);
        wrapper.appendChild(incrementBtn);

        // Insert wrapper into DOM
        if (nextSibling) {
            parent.insertBefore(wrapper, nextSibling);
        } else {
            parent.appendChild(wrapper);
        }

        // Get step value (default to 1)
        function getStep() {
            const step = parseFloat(input.step);
            return isNaN(step) || step === 0 ? 1 : step;
        }

        // Decrement handler
        function decrement() {
            const step = getStep();
            const currentValue = parseFloat(input.value) || 0;
            const newValue = currentValue - step;
            
            // Respect min attribute
            const min = input.hasAttribute('min') ? parseFloat(input.min) : null;
            if (min !== null && newValue < min) {
                input.value = min;
            } else {
                input.value = newValue;
            }
            
            // Trigger change event
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // Increment handler
        function increment() {
            const step = getStep();
            const currentValue = parseFloat(input.value) || 0;
            const newValue = currentValue + step;
            
            // Respect max attribute
            const max = input.hasAttribute('max') ? parseFloat(input.max) : null;
            if (max !== null && newValue > max) {
                input.value = max;
            } else {
                input.value = newValue;
            }
            
            // Trigger change event
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // Focus handler - show buttons
        function handleFocus() {
            wrapper.classList.add('focused');
        }

        // Blur handler - hide buttons
        function handleBlur(e) {
            // Check if focus is moving to one of the buttons
            const relatedTarget = e.relatedTarget;
            if (relatedTarget && (relatedTarget === decrementBtn || relatedTarget === incrementBtn)) {
                // Keep focused if moving to button
                return;
            }
            wrapper.classList.remove('focused');
        }

        // Button click handlers
        decrementBtn.addEventListener('click', function(e) {
            e.preventDefault();
            decrement();
            input.focus();
        });

        incrementBtn.addEventListener('click', function(e) {
            e.preventDefault();
            increment();
            input.focus();
        });

        // Input focus/blur handlers
        input.addEventListener('focus', handleFocus);
        input.addEventListener('blur', handleBlur);

        // Handle button focus to keep wrapper focused
        decrementBtn.addEventListener('focus', handleFocus);
        incrementBtn.addEventListener('focus', handleFocus);
        decrementBtn.addEventListener('blur', handleBlur);
        incrementBtn.addEventListener('blur', handleBlur);

        // Handle clicks outside to remove focus
        document.addEventListener('click', function(e) {
            if (!wrapper.contains(e.target)) {
                wrapper.classList.remove('focused');
            }
        });
    }

    /**
     * Initialize all number inputs on the page
     */
    function initAllNumberInputs() {
        const numberInputs = document.querySelectorAll('input[type="number"]:not([data-number-input-initialized="true"])');
        numberInputs.forEach(initNumberInput);
    }

    /**
     * Reinitialize number inputs (useful for dynamically added content)
     */
    function reinitNumberInputs(container) {
        const numberInputs = container.querySelectorAll('input[type="number"]');
        numberInputs.forEach(initNumberInput);
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllNumberInputs);
    } else {
        initAllNumberInputs();
    }

    // Expose for manual initialization
    window.initNumberInputs = initAllNumberInputs;
    window.reinitNumberInputs = reinitNumberInputs;
    window.initNumberInput = initNumberInput;

    // Use MutationObserver to handle dynamically added inputs
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    if (node.tagName === 'INPUT' && node.type === 'number') {
                        initNumberInput(node);
                    } else if (node.querySelectorAll) {
                        const numberInputs = node.querySelectorAll('input[type="number"]');
                        numberInputs.forEach(initNumberInput);
                    }
                }
            });
        });
    });

    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

})();

