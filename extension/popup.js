const MESSAGE_TYPES = {
    CANCEL_CHECKOUT: 'CANCEL_CHECKOUT',
    PROCEED_CHECKOUT: 'PROCEED_CHECKOUT',
    PURCHASE_CONFIRMED: 'PURCHASE_CONFIRMED'
};

const DEFAULTS = {
    budget: 500,
    currency: 'USD',
    notifications: true,
    dashboardUrl: 'http://localhost:3000'
};

const CURRENCY_MAP = {
    USD: '$',
    EUR: '€',
    GBP: '£',
    JPY: '¥',
    CAD: '$',
    AUD: '$'
};

const PRICE_ADVICE_THRESHOLDS = {
    LOW: 100,
    HIGH: 500
};

document.addEventListener('DOMContentLoaded', async () => {
    function getElement(id) {
        const el = document.getElementById(id);
        if (!el) console.warn(`[Orion] Missing element: ${id}`);
        return el;
    }

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
            saveSettings: getElement('btn-save-settings'),
            back: getElement('btn-back')
        },
        links: {
            settings: getElement('settings-link'),
            dashboard: getElement('dashboard-link')
        },
        adviceList: getElement('advice-list')
    };

    const missingStates = Object.values(elements.states).some(el => !el);
    if (missingStates) {
        console.error('[Orion] Missing required state elements, aborting');
        return;
    }

    let currentProduct = null;
    let settings = { ...DEFAULTS };

    function showState(stateName) {
        Object.values(elements.states).forEach(el => {
            if (el) el.classList.add('hidden');
        });
        const target = elements.states[stateName];
        if (target) {
            target.classList.remove('hidden');
        }
    }

    function formatPrice(price, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(price);
    }

    function validateBudget(value) {
        const num = parseFloat(value);
        if (isNaN(num) || num < 0) return DEFAULTS.budget;
        return num;
    }

    function validateUrl(value) {
        if (!value || typeof value !== 'string') return DEFAULTS.dashboardUrl;
        try {
            new URL(value);
            return value;
        } catch {
            return DEFAULTS.dashboardUrl;
        }
    }

    function getAdviceBasedOnPrice(price) {
        const advice = [
            'Do you really need this right now?',
            'Is this within your budget?',
            'Have you waited 24 hours to think about it?'
        ];
        
        if (price > PRICE_ADVICE_THRESHOLDS.LOW) {
            advice.push('Could you find a cheaper alternative?');
            advice.push('Is this a want or a need?');
        }
        
        if (price > PRICE_ADVICE_THRESHOLDS.HIGH) {
            advice.push('This is a significant purchase - sleep on it!');
            advice.push('Consider saving for it instead.');
        }
        
        return advice;
    }

    async function loadSettings() {
        try {
            const result = await chrome.storage.local.get(Object.keys(DEFAULTS));
            settings = {
                budget: validateBudget(result.budget),
                currency: result.currency || DEFAULTS.currency,
                notifications: result.notifications ?? DEFAULTS.notifications,
                dashboardUrl: validateUrl(result.dashboardUrl)
            };
            
            elements.settings.currencySelect.value = settings.currency;
            elements.settings.currencySymbol.textContent = CURRENCY_MAP[settings.currency] || '$';
            elements.settings.notificationsToggle.checked = settings.notifications;
            elements.settings.dashboardUrl.value = settings.dashboardUrl;
            elements.budget.input.value = settings.budget;
        } catch (error) {
            console.error('[Orion] Error loading settings:', error);
        }
    }

    async function saveSettings() {
        const newBudget = validateBudget(elements.budget.input.value);
        const newCurrency = elements.settings.currencySelect.value;
        const newNotifications = elements.settings.notificationsToggle.checked;
        const newDashboardUrl = validateUrl(elements.settings.dashboardUrl.value);

        settings = {
            budget: newBudget,
            currency: newCurrency,
            notifications: newNotifications,
            dashboardUrl: newDashboardUrl
        };

        try {
            await chrome.storage.local.set(settings);
            
            elements.buttons.saveSettings.textContent = 'Saved!';
            elements.buttons.saveSettings.disabled = true;
            
            setTimeout(() => {
                elements.buttons.saveSettings.textContent = 'Save Settings';
                elements.buttons.saveSettings.disabled = false;
            }, 1500);
        } catch (error) {
            console.error('[Orion] Error saving settings:', error);
        }
    }

    async function loadPendingProduct() {
        try {
            const result = await chrome.storage.local.get([
                'pendingProduct', 'showIntervention', 'budgetRemaining', 'currency', 'totalSpentThisMonth', 'budget'
            ]);
            
            if (result.showIntervention && result.pendingProduct) {
                const product = result.pendingProduct;
                currentProduct = product;
                
                elements.product.title.textContent = product.title || 'Unknown Product';
                elements.product.merchant.textContent = product.merchant || window.location.hostname;
                
                const currency = result.currency || settings.currency;
                elements.product.price.textContent = formatPrice(product.price || 0, currency);
                
                const spent = result.totalSpentThisMonth ?? 0;
                const budget = result.budget ?? settings.budget;
                const remaining = budget - spent;
                const diff = (product.price || 0) - remaining;
                
                if (diff > 0) {
                    elements.budget.text.textContent = `Over budget by ${formatPrice(diff, currency)}`;
                    elements.product.price.classList.add('over-budget');
                    elements.product.price.classList.remove('affordable');
                } else {
                    elements.budget.text.textContent = `${formatPrice(remaining, currency)} remaining this month (${formatPrice(spent, currency)} spent)`;
                    elements.product.price.classList.add('affordable');
                    elements.product.price.classList.remove('over-budget');
                }
                
                if (elements.adviceList) {
                    const advice = getAdviceBasedOnPrice(product.price || 0);
                    elements.adviceList.innerHTML = advice.map(item => `<li>${item}</li>`).join('');
                }
                
                showState('intervention');
            } else {
                showState('waiting');
            }
        } catch (error) {
            console.error('[Orion] Error loading pending product:', error);
            showState('waiting');
        }
    }

    async function notifyContentScript(type) {
        try {
            const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
            if (tabs[0]?.id) {
                chrome.tabs.sendMessage(tabs[0].id, { type }, () => {});
            }
        } catch (e) {}
    }

    if (elements.settings.currencySelect) {
        elements.settings.currencySelect.addEventListener('change', () => {
            const currency = elements.settings.currencySelect.value;
            if (elements.settings.currencySymbol) {
                elements.settings.currencySymbol.textContent = CURRENCY_MAP[currency] || '$';
            }
        });
    }

    if (elements.buttons.cancel) {
        elements.buttons.cancel.addEventListener('click', async () => {
            elements.buttons.cancel.disabled = true;
            elements.buttons.cancel.textContent = 'Cancelling...';
            
            await chrome.storage.local.set({
                showIntervention: false,
                pendingProduct: null
            });
            
            await notifyContentScript(MESSAGE_TYPES.CANCEL_CHECKOUT);
            
            if (elements.product.savedAmount && currentProduct?.price) {
                elements.product.savedAmount.textContent = formatPrice(currentProduct.price, settings.currency);
            }
            
            showState('cancelled');
            
            setTimeout(() => window.close(), 2000);
        });
    }

    if (elements.buttons.proceed) {
        elements.buttons.proceed.addEventListener('click', async () => {
            elements.buttons.proceed.disabled = true;
            elements.buttons.proceed.textContent = 'Proceeding...';
            
            await chrome.storage.local.set({
                showIntervention: false,
                pendingProduct: null
            });
            
            await notifyContentScript(MESSAGE_TYPES.PROCEED_CHECKOUT);
            
            try {
                const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
                if (tabs[0]?.id) {
                    chrome.runtime.sendMessage({
                        type: MESSAGE_TYPES.PURCHASE_CONFIRMED || 'PURCHASE_CONFIRMED',
                        product: currentProduct
                    });
                }
            } catch (e) {}
            
            window.close();
        });
    }

    if (elements.buttons.saveSettings) {
        elements.buttons.saveSettings.addEventListener('click', saveSettings);
    }

    if (elements.buttons.back) {
        elements.buttons.back.addEventListener('click', () => showState('waiting'));
    }

    if (elements.links.settings) {
        elements.links.settings.addEventListener('click', (e) => {
            e.preventDefault();
            loadSettings();
            showState('settings');
        });
    }

    if (elements.links.dashboard) {
        elements.links.dashboard.addEventListener('click', (e) => {
            e.preventDefault();
            chrome.tabs.create({ url: settings.dashboardUrl });
        });
    }

    await loadSettings();
    await loadPendingProduct();
});
