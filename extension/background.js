const MESSAGE_TYPES = {
    CHECKOUT_DETECTED: 'CHECKOUT_DETECTED',
    GET_PENDING_PRODUCT: 'GET_PENDING_PRODUCT',
    CLEAR_PENDING_PRODUCT: 'CLEAR_PENDING_PRODUCT',
    PURCHASE_CONFIRMED: 'PURCHASE_CONFIRMED',
    GET_BUDGET_STATUS: 'GET_BUDGET_STATUS'
};

const DEFAULTS = {
    budget: 500,
    currency: 'USD',
    notifications: true,
    dashboardUrl: 'http://localhost:3000',
    budgetResetDay: 1,
    spendingHistory: []
};

let pendingProduct = null;

function getMonthKey() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function shouldResetBudget(lastResetMonth) {
    const currentMonth = getMonthKey();
    return lastResetMonth !== currentMonth;
}

async function initializeBudget() {
    const result = await chrome.storage.local.get([
        'lastResetMonth', 'spendingHistory', 'budgetRemaining', 'budget', 'currency'
    ]);
    const currentMonth = getMonthKey();
    
    if (shouldResetBudget(result.lastResetMonth)) {
        const currentBudget = result.budgetRemaining ?? result.budget ?? DEFAULTS.budget;
        await chrome.storage.local.set({
            lastResetMonth: currentMonth,
            budgetRemaining: currentBudget,
            spendingHistory: []
        });
    }
}

async function recordPurchase(product) {
    const result = await chrome.storage.local.get([
        'spendingHistory', 'budgetRemaining', 'budget', 'currency'
    ]);
    const history = result.spendingHistory || [];
    const purchase = {
        ...product,
        month: getMonthKey(),
        timestamp: new Date().toISOString()
    };
    
    history.push(purchase);
    
    const totalSpent = history
        .filter(p => p.month === getMonthKey())
        .reduce((sum, p) => sum + (p.price || 0), 0);
    
    const budget = result.budget || DEFAULTS.budget;
    const remaining = Math.max(0, budget - totalSpent);
    
    await chrome.storage.local.set({
        spendingHistory: history.slice(-100),
        budgetRemaining: remaining
    });
    
    return { totalSpent, remaining, budget };
}

async function openPopup() {
    try {
        await chrome.action.openPopup();
    } catch (e) {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tabs[0] && pendingProduct) {
            const tabId = tabs[0].id;
            
            try {
                const [isCheckout] = await chrome.tabs.executeScript(tabId, {
                    code: `window.Orion && window.Orion.isLikelyCheckoutPage ? window.Orion.isLikelyCheckoutPage() : false`
                });
                
                if (!isCheckout) {
                    await chrome.storage.local.set({ 
                        pendingProduct,
                        showIntervention: true 
                    });
                    chrome.tabs.reload(tabId, { bypassCache: true });
                }
            } catch (err) {
                await chrome.storage.local.set({ 
                    pendingProduct,
                    showIntervention: true 
                });
                chrome.tabs.reload(tabId, { bypassCache: true });
            }
        }
    }
}

async function handleCheckoutDetected(message) {
    pendingProduct = message.product;
    
    try {
        await initializeBudget();
        
        const result = await chrome.storage.local.get([
            'budget', 'currency', 'budgetRemaining', 'spendingHistory'
        ]);
        const budget = result.budget ?? DEFAULTS.budget;
        const currency = result.currency ?? DEFAULTS.currency;
        
        const history = result.spendingHistory || [];
        const monthHistory = history.filter(p => p.month === getMonthKey());
        const totalSpent = monthHistory.reduce((sum, p) => sum + (p.price || 0), 0);
        
        const updatedRemaining = Math.max(0, budget - (totalSpent + (message.product.price || 0)));
        
        await chrome.storage.local.set({ 
            pendingProduct: message.product,
            showIntervention: true,
            budgetRemaining: updatedRemaining,
            currency: currency,
            totalSpentThisMonth: totalSpent,
            budget: budget
        });

        await openPopup();
        return { status: 'intercepted', budgetRemaining: updatedRemaining, totalSpent };
    } catch (error) {
        console.error('[Orion] Error handling checkout:', error);
        return { status: 'error', message: error.message };
    }
}

async function handleGetPendingProduct() {
    return { product: pendingProduct };
}

async function handleClearPendingProduct() {
    pendingProduct = null;
    try {
        await chrome.storage.local.set({ 
            pendingProduct: null,
            showIntervention: false 
        });
        return { status: 'cleared' };
    } catch (error) {
        console.error('[Orion] Error clearing product:', error);
        return { status: 'error', message: error.message };
    }
}

chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
    try {
        let result;
        
        switch (message.type) {
            case MESSAGE_TYPES.CHECKOUT_DETECTED:
                result = await handleCheckoutDetected(message);
                break;
                
            case MESSAGE_TYPES.GET_PENDING_PRODUCT:
                result = await handleGetPendingProduct();
                break;
                
            case MESSAGE_TYPES.CLEAR_PENDING_PRODUCT:
                result = await handleClearPendingProduct();
                break;
                
            case MESSAGE_TYPES.PURCHASE_CONFIRMED:
                if (message.product) {
                    await recordPurchase(message.product);
                }
                result = { status: 'recorded' };
                break;
                
            case MESSAGE_TYPES.GET_BUDGET_STATUS:
                await initializeBudget();
                const status = await chrome.storage.local.get(['budgetRemaining', 'budget', 'totalSpentThisMonth']);
                result = { 
                    remaining: status.budgetRemaining ?? DEFAULTS.budget,
                    budget: status.budget ?? DEFAULTS.budget,
                    spent: status.totalSpentThisMonth ?? 0
                };
                break;
                
            default:
                result = { status: 'unknown_message_type' };
        }
        
        sendResponse(result);
    } catch (error) {
        console.error('[Orion] Message handler error:', error);
        sendResponse({ status: 'error', message: error.message });
    }
    
    return true;
});

chrome.runtime.onInstalled.addListener(async () => {
    try {
        await chrome.storage.local.set({
            enabled: true,
            showIntervention: false,
            pendingProduct: null,
            ...DEFAULTS,
            lastResetMonth: getMonthKey()
        });
    } catch (error) {
        console.error('[Orion] Error initializing storage:', error);
    }
});
