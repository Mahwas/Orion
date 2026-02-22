(function() {
    'use strict';

    // --- Configuration & Constants ---
    const CONFIG = {
        DETECTION_DELAYS: [1000],
        DEBOUNCE_DELAY: 500,
        INTERCEPT_TIMEOUT: 3000,
        SCOPED_OBSERVER_SELECTORS: [
            '#checkout', '#cart', '#basket', '#payment',
            '.checkout', '.cart', '.basket', '.payment',
            '[data-checkout]', '[data-cart]', '[data-payment]',
            'form[action*="checkout"]', 'form[action*="order"]',
            'main', 'section', 'article'
        ]
    };

    const MESSAGE_TYPES = {
        CHECKOUT_DETECTED: 'CHECKOUT_DETECTED',
        CANCEL_CHECKOUT: 'CANCEL_CHECKOUT',
        PROCEED_CHECKOUT: 'PROCEED_CHECKOUT'
    };

    // Default selectors (fallback if config load fails)
    const DEFAULT_CONFIG = {
        platformUrlPatterns: [
            /\/checkout/i, /\/cart/i, /\/basket/i, /\/payment/i, /\/order/i,
            /\/billing/i, /\/shipping/i, /\/order-confirmation/i, /\/warenkorb/i,
            /\/winkelwagen/i, /\/panier/i, /\/carrito/i, /\/checkouts/i, /\/gp\/buy/i
        ],
        checkoutKeywords: ['checkout', 'buy now', 'purchase', 'pay now', 'place order'],
        platformButtonSelectors: [
            '.btn--checkout', '[name="checkout"]', '.checkout-btn', '.checkout-button',
            '#place_order', '#buy-now-button', '.amazon-pay-button'
        ],
        oneClickButtons: [
            '.apple-pay-button', '.google-pay-button', '.paypal-button',
            '[data-google-pay]', '[data-apple-pay]', '#paypal-button'
        ],
        priceSelectors: ['.price', '#price', '[data-price]', '.product-price', '.sale-price'],
        currencySymbols: ['$', '€', '£', '¥']
    };

    // State
    let state = {
        platformUrlPatterns: [],
        checkoutQueryParams: [],
        negativeUrlPatterns: [],
        platformButtonSelectors: [],
        oneClickButtons: [],
        cartIndicators: [],
        priceIndicators: [],
        checkoutFieldSelectors: [],
        priceSelectors: [],
        currencySymbols: [],
        hasShownInterception: false,
        interceptLock: Promise.resolve(),
        observer: null,
        historyDebounceTimeout: null,
        formInterceptDebounce: null,
        observerThrottleTimeout: null
    };

    // --- Core Logic ---

    async function loadConfig() {
        try {
            if (typeof chrome === 'undefined' || !chrome.runtime) {
                console.warn('[Orion] Chrome API not available, using defaults');
                applyDefaults();
                return;
            }
            
            const url = chrome.runtime.getURL('config/selectors.json');
            const response = await fetch(url);
            if (!response.ok) throw new Error('Config fetch failed');
            
            const config = await response.json();
            
            state.platformUrlPatterns = (config.platformUrlPatterns || []).map(p => new RegExp(p.replace(/\\\//g, '/'), 'i'));
            state.checkoutQueryParams = config.checkoutQueryParams || [];
            state.negativeUrlPatterns = (config.negativeUrlPatterns || []).map(p => new RegExp(p.replace(/\\\//g, '/'), 'i'));
            state.platformButtonSelectors = config.platformButtonSelectors || [];
            state.oneClickButtons = config.oneClickButtons || [];
            state.cartIndicators = config.cartIndicators || [];
            state.priceIndicators = config.priceIndicators || [];
            state.checkoutFieldSelectors = config.checkoutFieldSelectors || [];
            state.priceSelectors = config.priceSelectors || [];
            state.currencySymbols = config.currencySymbols || DEFAULT_CONFIG.currencySymbols;
            
            console.log('[Orion] Config loaded successfully');
        } catch (e) {
            console.warn('[Orion] Failed to load config, using defaults:', e);
            applyDefaults();
        }
    }

    function applyDefaults() {
        state.platformUrlPatterns = DEFAULT_CONFIG.platformUrlPatterns;
        state.platformButtonSelectors = DEFAULT_CONFIG.platformButtonSelectors;
        state.oneClickButtons = DEFAULT_CONFIG.oneClickButtons;
        state.priceSelectors = DEFAULT_CONFIG.priceSelectors;
        state.currencySymbols = DEFAULT_CONFIG.currencySymbols;
    }

    // --- Extraction Logic ---

    // --- Extraction Logic ---

    // Helper to check if an element is visible
    function isElementVisible(el) {
        if (!el || !el.offsetParent) return false; // Not in DOM or hidden by display:none
        const style = window.getComputedStyle(el);
        return style.width !== '0' && style.height !== '0' && style.opacity !== '0' &&
               style.visibility !== 'hidden' && style.display !== 'none';
    }

    // Helper to find price-like numbers in text
    function findPriceInText(text, currencySymbols) {
        if (!text) return null;
        // Regex to find numbers that look like prices, potentially with currency symbols
        // Handles formats like $1,234.56, €1.234,56, 1.234,56€, 1234.56
        const priceRegex = new RegExp(
            `(${currencySymbols.map(s => `\\${s}`).join('|')}|\\b)\\s*` + // Optional currency symbol
            `(\\d{1,3}(?:[.,]\\d{3})*(?:[.,]\\d{2})?|\\d+(?:[.,]\\d+)?)\\s*` + // Price number
            `(?:(${currencySymbols.map(s => `\\${s}`).join('|')})|\\b)`, 'g' // Optional trailing currency symbol
        );

        let match;
        let bestPrice = null;

        while ((match = priceRegex.exec(text)) !== null) {
            let priceStr = match[2];
            // Normalize: remove thousands separators, replace comma decimal with dot
            priceStr = priceStr.replace(/,/g, ''); // Remove all commas
            if (priceStr.match(/\d+\.\d{2},\d{2}/)) { // Example: 1.234,56
                priceStr = priceStr.replace(/\./g, '').replace(/,/g, '.');
            } else if (priceStr.match(/\d+,\d{2}/)) { // Example: 123,45
                 priceStr = priceStr.replace(/,/g, '.');
            }
            
            const price = parseFloat(priceStr);
            if (!isNaN(price) && price > 0) {
                // Heuristic: prefer larger prices (might indicate product price over sub-total)
                if (bestPrice === null || price > bestPrice) {
                    bestPrice = price;
                }
            }
        }
        return bestPrice;
    }

    const PriceExtractor = {
        findInSchema(obj) {
            if (!obj) return null;
            if (obj.offers) {
                const offers = Array.isArray(obj.offers) ? obj.offers[0] : obj.offers;
                return parseFloat(offers.price || offers.highPrice || offers.lowPrice);
            }
            if (obj.price) return parseFloat(obj.price);
            for (const key of Object.keys(obj)) {
                if (typeof obj[key] === 'object' && obj[key] !== null) {
                    const nested = this.findInSchema(obj[key]);
                    if (nested) return nested;
                }
            }
            return null;
        },

        extract() {
            let extractedPrice = null;

            // 1. Try JSON-LD (most reliable semantic data)
            const jsonLdScripts = document.querySelectorAll('[type="application/ld+json"]');
            for (const script of jsonLdScripts) {
                try {
                    const data = JSON.parse(script.textContent);
                    const price = this.findInSchema(data);
                    if (price) return price; // Return immediately if found in schema
                } catch (e) { /* console.error("JSON-LD parse error:", e); */ }
            }

            // 2. Try Meta tags (Open Graph price)
            const ogPrice = document.querySelector('meta[property="og:price:amount"]');
            if (ogPrice && ogPrice.content) return parseFloat(ogPrice.content);
            
            // 3. Try DOM selectors (more robust approach)
            const allPriceElements = document.querySelectorAll(state.priceSelectors.join(',') + ', [class*="price"], [id*="price"]');
            let potentialPrices = [];

            allPriceElements.forEach(el => {
                if (!isElementVisible(el)) return;

                const text = el.textContent || el.value || '';
                const priceValue = findPriceInText(text, state.currencySymbols);
                if (priceValue !== null) {
                    potentialPrices.push({ price: priceValue, element: el, text: text });
                }
            });

            // Heuristic to pick the "best" price if multiple are found
            if (potentialPrices.length > 0) {
                // First, look for a clear sale price or current price, prioritizing elements that are explicitly marked
                const salePriceKeywords = /sale|current|deal|offer|lower|discount|final/i;
                const amazonCurrentPriceIndicator = el => el.closest('.a-price-whole') || el.closest('.a-price-fraction') || el.closest('[data-a-color="price"]');
                const bestMatch = potentialPrices.find(p => 
                    salePriceKeywords.test(p.element.className || '') || 
                    salePriceKeywords.test(p.element.id || '') ||
                    amazonCurrentPriceIndicator(p.element)
                );

                if (bestMatch) {
                    extractedPrice = bestMatch.price;
                } else {
                    // If no explicit "sale" or "current" indicator, take the lowest price found
                    potentialPrices.sort((a, b) => a.price - b.price); // Sort ascending
                    extractedPrice = potentialPrices[0].price;
                }
            }

            if (extractedPrice !== null) return extractedPrice;

            // 4. Fallback to broad text search in the body if specific selectors fail
            return findPriceInText(document.body.innerText, state.currencySymbols);
        }
    };

    function extractCurrency() {
        const pageText = document.body?.textContent || '';
        for (const symbol of state.currencySymbols) {
            // Escape special regex chars
            const escapedSymbol = symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escapedSymbol + '\\s*[\\d,]+\\.?\\d*');
            if (regex.test(pageText)) return symbol;
        }
        return 'USD';
    }

    function extractProductInfo() {
        const titleSelectors = [
            '#productTitle', // Amazon specific
            'h1.product-title', // Generic
            'span.a-size-large.product-title-word-break', // Amazon specific
            'h1[itemprop="name"]', // Semantic
            '[itemprop="name"]', // Semantic
            '.product-title', // Generic
            'h1[class*="product"]', // Generic
            'h1' // Broad
        ];
        
        let title = '';
        for (const selector of titleSelectors) {
            const el = document.querySelector(selector);
            if (el && el.textContent?.trim()) {
                title = el.textContent.trim();
                break;
            }
        }
        
        // Fallback to document.title if no specific title found
        if (!title) {
            // Split by common separators and take the first part
            title = document.title.split('|')[0]
                                 .split('-')[0]
                                 .split('–')[0]
                                 .trim();
        }

        const merchant = window.location.hostname
            .replace(/^www\.|^checkout\.|^store\./, '')
            .split('.')[0];

        return {
            title: title || 'Unknown Product', // Default if still no title
            price: PriceExtractor.extract() || 0,
            currency: extractCurrency(),
            merchant: merchant,
            url: window.location.href,
            timestamp: new Date().toISOString()
        };
    }

    // --- Detection Logic ---

    function isCheckoutKeyword(text) {
        if (!text) return false;
        const lowerText = text.toLowerCase();
        const keywords = [
            'checkout', 'buy now', 'purchase', 'pay now', 'place order',
            'complete order', 'submit order', 'finish checkout', 'finalize',
            'secure checkout', 'make payment', 'confirm order', 'process order',
            'continue to payment', 'proceed to payment', 'proceed to checkout',
            'continue to checkout', 'review order', 'review and pay',
            'buy with prime', 'pay with paypal', 'pay with apple pay'
        ];
        return keywords.some(k => lowerText.includes(k));
    }

    function isCheckoutPage() {
        const url = window.location.href.toLowerCase();
        const path = window.location.pathname.toLowerCase();
        
        if (state.negativeUrlPatterns.some(p => p.test(url) || p.test(path))) return false;
        return state.platformUrlPatterns.some(p => p.test(url) || p.test(path));
    }

    function isLikelyCheckoutPage() {
        // Check URL patterns
        if (isCheckoutPage()) return true;

        // Check query params / hash
        const url = new URL(window.location.href);
        const hasParam = state.checkoutQueryParams.some(key => 
            url.searchParams.has(key) || url.hash.includes(key)
        );
        if (hasParam || url.hash.includes('checkout') || url.hash.includes('payment')) return true;

        // Check DOM indicators
        const hasCart = state.cartIndicators.some(sel => {
            const el = document.querySelector(sel);
            if (!el) return false;
            const match = (el.textContent || el.value || '').match(/\d+/);
            return (match && parseInt(match[0]) > 0) || el.offsetParent !== null;
        });
        if (hasCart) return true;

        const hasPrice = state.priceIndicators.some(sel => !!document.querySelector(sel)?.offsetParent);
        const hasFields = document.querySelectorAll(state.checkoutFieldSelectors.join(',')).length >= 2;
        
        return hasPrice && hasFields;
    }

    function findInShadowDOM(root, selector) {
        let found = Array.from(root.querySelectorAll(selector));
        const children = root.querySelectorAll('*');
        for (const child of children) {
            if (child.shadowRoot) {
                found = found.concat(findInShadowDOM(child.shadowRoot, selector));
            }
        }
        return found;
    }

    function findCheckoutButtons() {
        const buttons = [];
        const allElements = findInShadowDOM(document, 'button, input[type="submit"], a');

        allElements.forEach(btn => {
            if (btn.dataset.orionIntercepted) return;

            const text = (btn.textContent || btn.value || '').toLowerCase();
            const id = (btn.id || '').toLowerCase();
            const className = (btn.className || '').toLowerCase();
            const dataAttr = [
                btn.dataset.testid, btn.dataset.track, btn.dataset.cy, btn.dataset.name
            ].filter(Boolean).join(' ').toLowerCase();

            const matchesSelector = state.platformButtonSelectors.some(sel => btn.matches(sel) || btn.closest(sel));
            const matchesOneClick = state.oneClickButtons.some(sel => btn.matches(sel) || className.includes(sel.replace(/[.#]/g, '')));
            
            const isExplicitCheckout = 
                isCheckoutKeyword(text) ||
                id.match(/checkout|buy|pay|order/i) || // Added 'i' flag for case-insensitivity
                className.match(/checkout|buy|pay|apple-pay|google-pay|paypal/i) || // Added 'i' flag
                dataAttr.match(/checkout|buy|pay|order|submit/i); // Added 'i' flag

            if (matchesSelector || matchesOneClick || isExplicitCheckout) {
                buttons.push(btn);
            }
        });

        return buttons;
    }

    // --- Interception Logic ---

    function acquireLock() {
        let release;
        state.interceptLock = new Promise(resolve => { release = resolve; });
        return release;
    }

    async function handleInterception(event = null) {
        if (state.hasShownInterception) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            return;
        }

        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        const product = extractProductInfo();
        state.hasShownInterception = true;
        
        const release = acquireLock();

        try {
            chrome.runtime.sendMessage({
                type: MESSAGE_TYPES.CHECKOUT_DETECTED,
                product: product
            }, () => {
                setTimeout(release, CONFIG.INTERCEPT_TIMEOUT);
            });
        } catch (e) {
            console.error('[Orion] Message send failed', e);
            release();
        }
    }

    function attachListeners() {
        // Buttons
        const buttons = findCheckoutButtons();
        buttons.forEach(btn => {
            if (!btn.dataset.orionIntercepted) {
                btn.addEventListener('click', handleInterception);
                btn.dataset.orionIntercepted = 'true';
            }
        });

        // Forms
        document.querySelectorAll('form').forEach(form => {
            if (form.dataset.orionFormIntercepted) return;
            form.dataset.orionFormIntercepted = 'true';
            
            form.addEventListener('submit', (e) => {
                // Check if form is relevant
                const formKeywords = ['checkout', 'order', 'payment'];
                const formStr = (form.action + form.id + form.className + form.name).toLowerCase();
                const isRelevant = formKeywords.some(k => formStr.includes(k));
                
                // Check submit button text
                const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                const btnText = (submitBtn?.textContent || submitBtn?.value || '').toLowerCase();
                
                if (isRelevant || isCheckoutKeyword(btnText)) {
                    if (!state.formInterceptDebounce) {
                        state.formInterceptDebounce = true;
                        handleInterception(e);
                        setTimeout(() => { state.formInterceptDebounce = null; }, CONFIG.DEBOUNCE_DELAY);
                    }
                }
            });
        });

        // Keyboard (Enter key)
        const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"]');
        inputs.forEach(input => {
            if (input.dataset.orionKeyIntercepted) return;
            input.dataset.orionKeyIntercepted = 'true';
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const form = input.closest('form');
                    // Minimal check for form relevance
                    if (form && (form.action.includes('checkout') || form.id.includes('checkout'))) {
                        handleInterception(e);
                    }
                }
            });
        });
    }

    // --- Initialization & Observers ---

    function setupObservers() {
        // Main DOM Observer
        if (!state.observer) {
            state.observer = new MutationObserver(() => {
                if (!state.observerThrottleTimeout) {
                    state.observerThrottleTimeout = setTimeout(() => {
                        state.observerThrottleTimeout = null;
                        attachListeners();
                        if (isLikelyCheckoutPage()) handleInterception();
                    }, CONFIG.DEBOUNCE_DELAY);
                }
            });
            
            state.observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class', 'disabled']
            });
        }

        // History / Navigation Observer
        const debouncedCheck = () => {
            if (state.historyDebounceTimeout) clearTimeout(state.historyDebounceTimeout);
            state.historyDebounceTimeout = setTimeout(() => {
                 if (isLikelyCheckoutPage()) handleInterception();
            }, CONFIG.DEBOUNCE_DELAY);
        };

        window.addEventListener('popstate', debouncedCheck);
        window.addEventListener('hashchange', debouncedCheck);
        
        const originalPushState = history.pushState;
        history.pushState = function() {
            originalPushState.apply(this, arguments);
            debouncedCheck();
        };
    }

    function init() {
        // Only run on http/https pages
        if (!window.location.protocol.startsWith('http')) {
            return;
        }

        // Check if extension context is still valid (prevents errors on extension reload)
        if (!chrome.runtime?.id) {
            return;
        }

        loadConfig().then(() => {
            CONFIG.DETECTION_DELAYS.forEach(delay => 
                setTimeout(() => {
                    attachListeners();
                    if (isLikelyCheckoutPage()) handleInterception();
                }, delay)
            );

            setupObservers();
            console.log('[Orion] Monitoring initialized');
        });

        // Listen for messages from popup/background
        chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
            if (message.type === MESSAGE_TYPES.CANCEL_CHECKOUT) {
                window.history.back();
                state.hasShownInterception = false;
            } else if (message.type === MESSAGE_TYPES.PROCEED_CHECKOUT) {
                state.hasShownInterception = false;
            }
            sendResponse({ status: 'ok' });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
