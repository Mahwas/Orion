const MESSAGE_TYPES = {
    CANCEL_CHECKOUT: 'CANCEL_CHECKOUT',
    PROCEED_CHECKOUT: 'PROCEED_CHECKOUT',
    PURCHASE_CONFIRMED: 'PURCHASE_CONFIRMED',
    WAIT_24H: 'WAIT_24H',
    SAVE_TO_WISHLIST: 'SAVE_TO_WISHLIST'
};

const DEFAULTS = {
    budget: 500,
    currency: 'USD',
    notifications: true,
    dashboardUrl: 'http://localhost:3000'
};

const CURRENCY_MAP = {
    USD: '$', EUR: '€', GBP: '£', JPY: '¥', CAD: '$', AUD: '$'
};

const PRICE_ADVICE_THRESHOLDS = {
    LOW: 100,
    HIGH: 500
};

document.addEventListener('DOMContentLoaded', async () => {
    // --- UI Elements ---
    const getElement = (id) => document.getElementById(id);
    
    const elements = {
        states: {
            waiting: getElement('waiting-state'),
            intervention: getElement('intervention-state'),
            cancelled: getElement('cancelled-state'),
            settings: getElement('settings-state')
        },
        product: {
            title: getElement('product-title'),
            merchant: getElement('product-merchant'),
            price: getElement('product-price'),
            savedAmount: getElement('saved-amount')
        },
        budget: {
            text: getElement('budget-text'),
            input: getElement('budget-input')
        },
        settings: {
            currencySelect: getElement('currency-select'),
            currencySymbol: getElement('currency-symbol'),
            notificationsToggle: getElement('notifications-toggle'),
            dashboardUrl: getElement('dashboard-url')
        },
        buttons: {
            cancel: getElement('btn-cancel'),
            proceed: getElement('btn-proceed'),
            wait: getElement('btn-wait'),
            wishlist: getElement('btn-wishlist'),
            saveSettings: getElement('btn-save-settings'),
            back: getElement('btn-back')
        },
        links: {
            settings: getElement('settings-link'),
            dashboard: getElement('dashboard-link')
        },
        adviceList: getElement('advice-list')
    };

    if (Object.values(elements.states).some(el => !el)) {
        console.error('[Orion] Missing required state elements');
        return;
    }

    let currentProduct = null;
    let settings = { ...DEFAULTS };

    // --- Helpers ---

    function showState(stateName) {
        Object.values(elements.states).forEach(el => el && el.classList.add('hidden'));
        const target = elements.states[stateName];
        if (target) target.classList.remove('hidden');
    }

    function formatPrice(price, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency', currency
        }).format(price);
    }

    async function notifyContentScript(type) {
        try {
            const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
            if (tabs[0]?.id) {
                chrome.tabs.sendMessage(tabs[0].id, { type }, () => {});
            }
        } catch (e) {
            console.warn('[Orion] Failed to notify content script:', e);
        }
    }

    // --- Core Logic ---

    async function loadSettings() {
        try {
            const result = await chrome.storage.local.get(Object.keys(DEFAULTS));
            settings = {
                budget: parseFloat(result.budget) || DEFAULTS.budget,
                currency: result.currency || DEFAULTS.currency,
                notifications: result.notifications ?? DEFAULTS.notifications,
                dashboardUrl: result.dashboardUrl || DEFAULTS.dashboardUrl
            };
            
            // Update UI
            if (elements.settings.currencySelect) elements.settings.currencySelect.value = settings.currency;
            if (elements.settings.currencySymbol) elements.settings.currencySymbol.textContent = CURRENCY_MAP[settings.currency] || '$';
            if (elements.settings.notificationsToggle) elements.settings.notificationsToggle.checked = settings.notifications;
            if (elements.settings.dashboardUrl) elements.settings.dashboardUrl.value = settings.dashboardUrl;
            if (elements.budget.input) elements.budget.input.value = settings.budget;
        } catch (error) {
            console.error('[Orion] Error loading settings:', error);
        }
    }

    async function loadPendingProduct() {
        try {
            const result = await chrome.storage.local.get([
                'pendingProduct', 'showIntervention', 'budgetRemaining', 'currency', 'totalSpentThisMonth', 'budget'
            ]);
            
            if (!result.showIntervention || !result.pendingProduct) {
                showState('waiting');
                return;
            }

            currentProduct = result.pendingProduct;
            const currency = result.currency || settings.currency;
            
            // Update Product UI
            elements.product.title.textContent = currentProduct.title || 'Unknown Product';
            elements.product.merchant.textContent = currentProduct.merchant || window.location.hostname;
            elements.product.price.textContent = formatPrice(currentProduct.price || 0, currency);
            
            // Update Budget UI
            const spent = result.totalSpentThisMonth ?? 0;
            const budget = result.budget ?? settings.budget;
            const remaining = Math.max(0, budget - spent);
            const price = currentProduct.price || 0;
            
            if (price > remaining) {
                const diff = price - remaining;
                elements.budget.text.textContent = `Over budget by ${formatPrice(diff, currency)}`;
                elements.product.price.classList.add('over-budget');
                elements.product.price.classList.remove('affordable');
            } else {
                elements.budget.text.textContent = `${formatPrice(remaining, currency)} remaining (${formatPrice(spent, currency)} spent)`;
                elements.product.price.classList.add('affordable');
                elements.product.price.classList.remove('over-budget');
            }
            
            showState('intervention');
        } catch (error) {
            console.error('[Orion] Error loading pending product:', error);
            showState('waiting');
        }
    }

    // --- Event Handlers ---

    async function handleCancel() {
        if (elements.buttons.cancel) {
            elements.buttons.cancel.disabled = true;
            elements.buttons.cancel.textContent = 'Cancelling...';
        }
        
        await chrome.storage.local.set({ showIntervention: false, pendingProduct: null });
        await notifyContentScript(MESSAGE_TYPES.CANCEL_CHECKOUT);
        
        if (elements.product.savedAmount && currentProduct?.price) {
            elements.product.savedAmount.textContent = formatPrice(currentProduct.price, settings.currency);
        }
        
        showState('cancelled');
        setTimeout(() => window.close(), 2000);
    }

    async function handleProceed() {
        if (elements.buttons.proceed) {
            elements.buttons.proceed.disabled = true;
            elements.buttons.proceed.textContent = 'Proceeding...';
        }
        
        await chrome.storage.local.set({ showIntervention: false, pendingProduct: null });
        await notifyContentScript(MESSAGE_TYPES.PROCEED_CHECKOUT);
        
        try {
            chrome.runtime.sendMessage({
                type: MESSAGE_TYPES.PURCHASE_CONFIRMED,
                product: currentProduct
            });
        } catch (e) {}
        
        window.close();
    }

    async function handleSaveSettings() {
        const newBudget = parseFloat(elements.budget.input.value);
        if (isNaN(newBudget) || newBudget < 0) return;

        settings = {
            budget: newBudget,
            currency: elements.settings.currencySelect.value,
            notifications: elements.settings.notificationsToggle.checked,
            dashboardUrl: elements.settings.dashboardUrl.value
        };

        await chrome.storage.local.set(settings);
        
        const btn = elements.buttons.saveSettings;
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = 'Saved!';
            btn.disabled = true;
            setTimeout(() => {
                btn.textContent = originalText;
                btn.disabled = false;
            }, 1500);
        }
    }

    // --- Bind Events ---

    const bindings = [
        { el: elements.buttons.cancel, event: 'click', handler: handleCancel },
        { el: elements.buttons.proceed, event: 'click', handler: handleProceed },
        { el: elements.buttons.wait, event: 'click', handler: async () => {
            await chrome.runtime.sendMessage({ type: MESSAGE_TYPES.WAIT_24H });
            window.close();
        }},
        { el: elements.buttons.wishlist, event: 'click', handler: async () => {
            await chrome.runtime.sendMessage({ type: MESSAGE_TYPES.SAVE_TO_WISHLIST });
            window.close();
        }},
        { el: elements.buttons.saveSettings, event: 'click', handler: handleSaveSettings },
        { el: elements.buttons.back, event: 'click', handler: () => showState('waiting') },
        { el: elements.links.settings, event: 'click', handler: (e) => {
            e.preventDefault();
            loadSettings();
            showState('settings');
        }},
        { el: elements.links.dashboard, event: 'click', handler: (e) => {
            e.preventDefault();
            chrome.tabs.create({ url: settings.dashboardUrl });
        }},
        { el: elements.settings.currencySelect, event: 'change', handler: () => {
            const currency = elements.settings.currencySelect.value;
            if (elements.settings.currencySymbol) {
                elements.settings.currencySymbol.textContent = CURRENCY_MAP[currency] || '$';
            }
        }}
    ];

    bindings.forEach(({ el, event, handler }) => {
        if (el) el.addEventListener(event, handler);
    });

    // Init
    await loadSettings();
    await loadPendingProduct();
});
