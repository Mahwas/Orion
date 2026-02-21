(function() {
    'use strict';

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

    const CHECKOUT_KEYWORDS = [
        'checkout', 'buy now', 'purchase', 'pay now', 'place order',
        'complete order', 'submit order', 'finish checkout', 'finalize',
        'secure checkout', 'make payment', 'confirm order', 'process order',
        'continue to payment', 'proceed to payment', 'proceed to checkout',
        'continue to checkout', 'review order', 'review and pay',
        'continue to shipping', 'continue to billing', 'express checkout',
        'quick checkout', 'guest checkout', 'one-click checkout',
        'buy with prime', 'pay with paypal', 'pay with apple pay',
        'pay with google pay', 'pay with card', 'pay with credit card'
    ];

    const FORM_KEYWORDS = ['checkout', 'order', 'payment'];

    const IFRAME_CHECKOUT_KEYWORDS = ['checkout', 'payment', 'order', 'purchase', 'basket', 'cart'];

    let PLATFORM_URL_PATTERNS = [];
    let CHECKOUT_QUERY_PARAMS = [];
    let NEGATIVE_URL_PATTERNS = [];
    let PLATFORM_BUTTON_SELECTORS = [];
    let ONE_CLICK_BUTTONS = [];
    let CART_INDICATORS = [];
    let PRICE_INDICATORS = [];
    let CHECKOUT_FIELD_SELECTORS = [];
    let PRICE_SELECTORS = [];
    let CURRENCY_SYMBOLS = [];

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

    async function loadConfig() {
        try {
            if (typeof chrome === 'undefined' || !chrome.runtime) {
                console.warn('[Orion] Chrome API not available, using defaults');
                applyDefaults();
                return;
            }
            
            const response = await fetch(chrome.runtime.getURL('config/selectors.json'));
            const config = await response.json();
            
            PLATFORM_URL_PATTERNS = config.platformUrlPatterns.map(p => new RegExp(p.replace(/\\\//g, '/'), 'i'));
            CHECKOUT_QUERY_PARAMS = config.checkoutQueryParams || [];
            NEGATIVE_URL_PATTERNS = config.negativeUrlPatterns.map(p => new RegExp(p.replace(/\\\//g, '/'), 'i'));
            PLATFORM_BUTTON_SELECTORS = config.platformButtonSelectors || [];
            ONE_CLICK_BUTTONS = config.oneClickButtons || [];
            CART_INDICATORS = config.cartIndicators || [];
            PRICE_INDICATORS = config.priceIndicators || [];
            CHECKOUT_FIELD_SELECTORS = config.checkoutFieldSelectors || [];
            PRICE_SELECTORS = config.priceSelectors || [];
            CURRENCY_SYMBOLS = config.currencySymbols || ['$', '€', '£', '¥'];
            
            console.log('[Orion] Config loaded successfully');
        } catch (e) {
            console.warn('[Orion] Failed to load config, using defaults:', e);
            applyDefaults();
        }
    }

    function applyDefaults() {
        PLATFORM_URL_PATTERNS = DEFAULT_CONFIG.platformUrlPatterns;
        PLATFORM_BUTTON_SELECTORS = DEFAULT_CONFIG.platformButtonSelectors;
        ONE_CLICK_BUTTONS = DEFAULT_CONFIG.oneClickButtons;
        PRICE_SELECTORS = DEFAULT_CONFIG.priceSelectors;
        CURRENCY_SYMBOLS = DEFAULT_CONFIG.currencySymbols;
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
                if (typeof obj[key] === 'object') {
                    const nested = this.findInSchema(obj[key]);
                    if (nested) return nested;
                }
            }
            return null;
        },

        extract() {
            for (const selector of PRICE_SELECTORS) {
                const priceEl = document.querySelector(selector);
(selector);
                if (priceEl) {
                    const text = priceEl.textContent || '';
                    const match = text.match(/[\d,]+\.?\d*/);
                    if (match) {
                        return parseFloat(match[0].replace(/,/g, ''));
                    }
                }
            }
            
            const ogPrice = document.querySelector('meta[property="og:price:amount"]');
            if (ogPrice) {
                return parseFloat(ogPrice.content);
            }
            
            const jsonLdScripts = document.querySelectorAll('[type="application/ld+json"]');
            for (const script of jsonLdScripts) {
                try {
                    const data = JSON.parse(script.textContent);
                    const price = this.findInSchema(data);
                    if (price) return price;
                } catch (e) {}
            }
            
            return null;
        }
    };

    let interceptLock = Promise.resolve();
    let lastDetectedProduct = null;
    let hasShownInterception = false;
    let observer = null;

    function acquireInterceptLock() {
        let release;
        interceptLock = new Promise(resolve => { release = resolve; });
        return release;
    }

    function extractPrice() {
        return PriceExtractor.extract();
    }

    function extractCurrency() {
        const pageText = document.body?.textContent || '';
        for (const symbol of CURRENCY_SYMBOLS) {
            const regex = new RegExp(symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*[\\d,]+\\.?\\d*');
            if (regex.test(pageText)) {
                return symbol;
            }
        }
        return 'USD';
    }

    function extractProductInfo() {
        const titleSelectors = [
            '#productTitle', 
            'h1[itemprop="name"]', 
            '[itemprop="name"]',
            '.product-title', 
            'h1[class*="product"]',
            'h1'
        ];
        
        let title = null;
        for (const selector of titleSelectors) {
            const el = document.querySelector(selector);
            if (el && el.textContent?.trim()) {
                title = el.textContent.trim();
                break;
            }
        }
        
        if (!title) {
            title = document.title.split('|')[0].split('-')[0].split('–')[0].trim();
        }

        const price = extractPrice();
        const currency = extractCurrency();

        const merchant = window.location.hostname
            .replace('www.', '')
            .replace('checkout.', '')
            .replace('store.', '')
            .split('.')[0];

        return {
            title: title || 'Unknown Product',
            price: price || 0,
            currency: currency,
            merchant: merchant,
            url: window.location.href,
            timestamp: new Date().toISOString()
        };
    }

    function isCheckoutKeyword(text) {
        if (!text) return false;
        const lowerText = text.toLowerCase();
        return CHECKOUT_KEYWORDS.some(keyword => lowerText.includes(keyword));
    }

    function isCheckoutPage() {
        const url = window.location.href.toLowerCase();
        const path = window.location.pathname.toLowerCase();
        
        if (NEGATIVE_URL_PATTERNS.some(pattern => pattern.test(url) || pattern.test(path))) {
            return false;
        }
        
        return PLATFORM_URL_PATTERNS.some(pattern => pattern.test(url) || pattern.test(path));
    }

    function hasCheckoutQueryParam() {
        const url = new URL(window.location.href);
        const params = url.searchParams;
        
        for (const key of CHECKOUT_QUERY_PARAMS) {
            if (params.has(key) || url.hash.includes(key)) {
                return true;
            }
        }
        
        if (window.location.hash.includes('checkout') || window.location.hash.includes('payment')) {
            return true;
        }
        
        return false;
    }

    function hasCartIndicators() {
        return CART_INDICATORS.some(selector => {
            const el = document.querySelector(selector);
            if (!el) return false;
            
            const text = el.textContent || el.value || '';
            const match = text.match(/\d+/);
            if (match && parseInt(match[0]) > 0) {
                return true;
            }
            
            return el.offsetParent !== null;
        });
    }

    function hasPriceIndicators() {
        return PRICE_INDICATORS.some(selector => {
            const el = document.querySelector(selector);
            return el && el.offsetParent !== null;
        });
    }

    function hasCheckoutFormFields() {
        const fields = document.querySelectorAll(CHECKOUT_FIELD_SELECTORS);
        return fields.length >= 2;
    }

    function isLikelyCheckoutPage() {
        return (
            isCheckoutPage() ||
            hasCheckoutQueryParam() ||
            hasCartIndicators() ||
            (hasPriceIndicators() && hasCheckoutFormFields())
        );
    }

    function shouldInterceptForm(form) {
        if (!form) return false;
        
        const formAction = (form.action || '').toLowerCase();
        const formId = (form.id || '').toLowerCase();
        const formClass = (form.className || '').toLowerCase();
        const formName = (form.name || '').toLowerCase();

        if (FORM_KEYWORDS.some(k => formAction.includes(k) || formId.includes(k) || formClass.includes(k) || formName.includes(k))) {
            return true;
        }

        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) {
            const btnText = (submitBtn.textContent || submitBtn.value || '').toLowerCase();
            if (isCheckoutKeyword(btnText)) {
                return true;
            }
        }

        return false;
    }

    function findCheckoutButtons() {
        const buttons = [];
        const allElements = document.querySelectorAll('button, input[type="submit"], a');

        allElements.forEach(btn => {
            if (btn.dataset.orionIntercepted) return;

            const text = (btn.textContent || btn.value || '').toLowerCase();
            const id = (btn.id || '').toLowerCase();
            const className = (btn.className || '').toLowerCase();
            const dataAttr = (
                (btn.dataset?.testid || '') + ' ' +
                (btn.dataset?.track || '') + ' ' +
                (btn.dataset?.cy || '') + ' ' +
                (btn.dataset?.name || '')
            ).toLowerCase();

            const isCheckoutBtn = 
                isCheckoutKeyword(text) ||
                PLATFORM_BUTTON_SELECTORS.some(sel => {
                    try {
                        return btn.matches(sel) || btn.closest(sel);
                    } catch (e) { return false; }
                }) ||
                ONE_CLICK_BUTTONS.some(sel => {
                    try {
                        return btn.matches(sel) || className.includes(sel.replace(/[.#]/g, ''));
                    } catch (e) { return false; }
                }) ||
                (id.includes('checkout') || id.includes('buy') || id.includes('pay') || id.includes('order')) ||
                (className.includes('checkout') || className.includes('buy') || className.includes('pay') || 
                 className.includes('apple-pay') || className.includes('google-pay') || className.includes('paypal')) ||
                (dataAttr.includes('checkout') || dataAttr.includes('buy') || dataAttr.includes('pay') || 
                 dataAttr.includes('order') || dataAttr.includes('submit'));

            if (isCheckoutBtn) {
                buttons.push(btn);
            }
        });

        return buttons;
    }

    function attachKeyboardListeners() {
        const checkoutFields = document.querySelectorAll(
            'input[type="text"], input[type="email"], input[type="tel"], input[type="password"]'
        );

        checkoutFields.forEach(field => {
            if (field.dataset.orionKeyIntercepted) return;
            field.dataset.orionKeyIntercepted = 'true';

            field.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const form = field.closest('form');
                    if (form && shouldInterceptForm(form)) {
                        interceptCheckout(e);
                    }
                }
            });
        });
    }

    function attachOneClickListeners() {
        ONE_CLICK_BUTTONS.forEach(selector => {
            try {
                const buttons = document.querySelectorAll(selector);
                buttons.forEach(btn => {
                    if (btn.dataset.orionOneClickIntercepted) return;
                    btn.dataset.orionOneClickIntercepted = 'true';
                    btn.addEventListener('click', interceptCheckout);
                });
            } catch (e) {}
        });
    }

    async function checkCheckoutPage() {
        if (hasShownInterception) return;
        
        if (isLikelyCheckoutPage()) {
            const product = extractProductInfo();
            lastDetectedProduct = product;
            hasShownInterception = true;

            const release = await acquireInterceptLock();
            
            try {
                chrome.runtime.sendMessage({
                    type: MESSAGE_TYPES.CHECKOUT_DETECTED,
                    product: product
                }, () => {
                    setTimeout(release, CONFIG.INTERCEPT_TIMEOUT);
                });
            } catch (e) {
                release();
            }
        }
    }

    function interceptCheckout(event) {
        if (hasShownInterception) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            return;
        }
        
        const product = extractProductInfo();
        lastDetectedProduct = product;
        hasShownInterception = true;

        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        const release = acquireInterceptLock();
        
        try {
            chrome.runtime.sendMessage({
                type: MESSAGE_TYPES.CHECKOUT_DETECTED,
                product: product
            }, () => {
                setTimeout(release, CONFIG.INTERCEPT_TIMEOUT);
            });
        } catch (e) {
            release();
        }
    }

    function handlePopupMessage(message, sender, sendResponse) {
        if (message.type === MESSAGE_TYPES.CANCEL_CHECKOUT) {
            console.log('[Orion] Checkout cancelled by user');
            window.history.back();
            hasShownInterception = false;
        }
        
        if (message.type === MESSAGE_TYPES.PROCEED_CHECKOUT) {
            console.log('[Orion] User decided to proceed');
            hasShownInterception = false;
        }
        
        sendResponse({ status: 'ok' });
        return true;
    }

    chrome.runtime.onMessage.addListener(handlePopupMessage);

    function attachInterceptors() {
        const buttons = findCheckoutButtons();
        
        buttons.forEach(btn => {
            if (!btn.dataset.orionIntercepted) {
                btn.addEventListener('click', interceptCheckout);
                btn.dataset.orionIntercepted = 'true';
            }
        });

        attachFormListeners();
        attachKeyboardListeners();
        attachOneClickListeners();
    }

    function runDetectionPass(delay) {
        setTimeout(() => {
            attachInterceptors();
            checkCheckoutPage();
        }, delay);
    }

    let formInterceptDebounce = null;
    function debouncedIntercept(event) {
        if (formInterceptDebounce) return;
        formInterceptDebounce = true;
        interceptCheckout(event);
        setTimeout(() => { formInterceptDebounce = null; }, CONFIG.DEBOUNCE_DELAY);
    }

    let observerThrottleTimeout = null;
    function throttledObserverCallback(callback) {
        if (observerThrottleTimeout) return;
        observerThrottleTimeout = setTimeout(() => {
            observerThrottleTimeout = null;
            callback();
        }, CONFIG.DEBOUNCE_DELAY);
    }

    function attachFormListeners() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            if (form.dataset.orionFormIntercepted) return;
            form.dataset.orionFormIntercepted = 'true';

            form.addEventListener('submit', (e) => {
                if (shouldInterceptForm(form)) {
                    debouncedIntercept(e);
                }
            });
        });
    }

    function setupScopedObserver() {
        if (observer) return;
        
        const scopedContainers = document.querySelectorAll(
            CONFIG.SCOPED_OBSERVER_SELECTORS.join(', ')
        );
        
        const target = scopedContainers.length > 0 ? document.body : document.body;
        
        observer = new MutationObserver(() => {
            throttledObserverCallback(() => {
                attachInterceptors();
                checkCheckoutPage();
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['class', 'data-testid', 'disabled', 'aria-disabled']
        });
    }

    function setupIframeDetection() {
        const checkIframes = () => {
            const iframes = document.querySelectorAll('iframe');
            iframes.forEach(iframe => {
                try {
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                    if (iframeDoc) {
                        const iframeContent = iframeDoc.body?.textContent?.toLowerCase() || '';
                        if (IFRAME_CHECKOUT_KEYWORDS.some(k => iframeContent.includes(k))) {
                            const iframeButtons = iframeDoc.querySelectorAll('button, input[type="submit"], a');
                            iframeButtons.forEach(btn => {
                                if (!btn.dataset.orionIframeIntercepted) {
                                    btn.dataset.orionIframeIntercepted = 'true';
                                    btn.addEventListener('click', interceptCheckout);
                                }
                            });
                        }
                    }
                } catch (e) {}
            });
        };
        
        const iframeObserver = new MutationObserver(checkIframes);
        iframeObserver.observe(document.body, { childList: true, subtree: true });
        checkIframes();
    }

    let historyDebounceTimeout = null;
    function debouncedHistoryCheck() {
        if (historyDebounceTimeout) clearTimeout(historyDebounceTimeout);
        historyDebounceTimeout = setTimeout(checkCheckoutPage, CONFIG.DEBOUNCE_DELAY);
    }

    function init() {
        loadConfig().then(() => {
            CONFIG.DETECTION_DELAYS.forEach(delay => runDetectionPass(delay));

            checkCheckoutPage();
            
            setupScopedObserver();
            setupIframeDetection();

            const originalPushState = history.pushState;
            history.pushState = function() {
                originalPushState.apply(this, arguments);
                debouncedHistoryCheck();
            };

            window.addEventListener('popstate', debouncedHistoryCheck);
            window.addEventListener('hashchange', debouncedHistoryCheck);

            window.addEventListener('beforeunload', () => {
                if (observer) observer.disconnect();
                if (historyDebounceTimeout) clearTimeout(historyDebounceTimeout);
            });

            console.log('[Orion] Extension active - checkout monitoring enabled');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    if (typeof window !== 'undefined') {
        window.Orion = {
            isCheckoutPage,
            isCheckoutKeyword,
            shouldInterceptForm,
            findCheckoutButtons,
            extractProductInfo,
            extractPrice,
            extractCurrency,
            interceptCheckout,
            isLikelyCheckoutPage,
            hasCartIndicators,
            hasPriceIndicators,
            hasCheckoutFormFields,
            hasCheckoutQueryParam
        };
    }
})();
