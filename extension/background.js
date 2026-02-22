const MESSAGE_TYPES = {
    CHECKOUT_DETECTED: 'CHECKOUT_DETECTED',
    GET_PENDING_PRODUCT: 'GET_PENDING_PRODUCT',
    CLEAR_PENDING_PRODUCT: 'CLEAR_PENDING_PRODUCT',
    PURCHASE_CONFIRMED: 'PURCHASE_CONFIRMED',
    GET_BUDGET_STATUS: 'GET_BUDGET_STATUS',
    CANCEL_CHECKOUT: 'CANCEL_CHECKOUT',
    PROCEED_CHECKOUT: 'PROCEED_CHECKOUT',
    WAIT_24H: 'WAIT_24H',
    SAVE_TO_WISHLIST: 'SAVE_TO_WISHLIST'
};

const DEFAULTS = {
    budget: 500,
    currency: 'USD',
    notifications: true,
    dashboardUrl: 'http://localhost:3000',
    budgetResetDay: 1,
    spendingHistory: []
};

// --- Helpers ---

function getMonthKey() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

async function initializeBudget() {
    const keys = ['lastResetMonth', 'spendingHistory', 'budgetRemaining', 'budget', 'currency'];
    const result = await chrome.storage.local.get(keys);
    const currentMonth = getMonthKey();
    
    if (result.lastResetMonth !== currentMonth) {
        const currentBudget = result.budgetRemaining ?? result.budget ?? DEFAULTS.budget;
        await chrome.storage.local.set({
            lastResetMonth: currentMonth,
            budgetRemaining: currentBudget,
            spendingHistory: []
        });
    }
}

// --- Action Handlers ---

async function recordPurchase(product) {
    const result = await chrome.storage.local.get(['spendingHistory', 'budgetRemaining', 'budget']);
    const history = result.spendingHistory || [];
    
    const purchase = {
        ...product,
        month: getMonthKey(),
        timestamp: new Date().toISOString()
    };
    
    history.push(purchase);
    
    // Calculate totals
    const monthKey = getMonthKey();
    const totalSpent = history
        .filter(p => p.month === monthKey)
        .reduce((sum, p) => sum + (p.price || 0), 0);
    
    const budget = result.budget || DEFAULTS.budget;
    const remaining = Math.max(0, budget - totalSpent);
    
    await chrome.storage.local.set({
        spendingHistory: history.slice(-100), // Keep last 100
        budgetRemaining: remaining
    });
    
    return { totalSpent, remaining, budget };
}

async function handleWishlist(product) {
    if (!product) return { status: 'error', message: 'No product to save' };
    
    try {
        const { wishlist = [] } = await chrome.storage.local.get('wishlist');
        wishlist.push({
            ...product,
            timestamp: new Date().toISOString()
        });
        
        await chrome.storage.local.set({ 
            wishlist,
            showIntervention: false,
            pendingProduct: null
        });
        return { status: 'saved_to_wishlist' };
    } catch (error) {
        console.error('[Orion] Error saving to wishlist:', error);
        return { status: 'error', message: error.message };
    }
}

async function handleWait24H(product) {
    if (!product) return { status: 'error', message: 'No product to wait for' };
    
    try {
        const { waitingItems = [] } = await chrome.storage.local.get('waitingItems');
        waitingItems.push({
            ...product,
            expiry: Date.now() + 24 * 60 * 60 * 1000, // 24 hours
            timestamp: new Date().toISOString()
        });
        
        await chrome.storage.local.set({ 
            waitingItems,
            showIntervention: false,
            pendingProduct: null
        });
        return { status: 'waiting_set' };
    } catch (error) {
        console.error('[Orion] Error setting wait timer:', error);
        return { status: 'error', message: error.message };
    }
}

async function handleClearPendingProduct() {
    try {
        await chrome.storage.local.set({ 
            pendingProduct: null,
            showIntervention: false 
        });
        return { status: 'cleared' };
    } catch (error) {
        return { status: 'error', message: error.message };
    }
}

// --- UI Logic ---

async function openPopup() {
    try {
        await chrome.action.openPopup();
    } catch (e) {
        // Fallback: Try injecting overlay
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab?.id) {
            try {
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    files: ['overlay.js']
                });
            } catch (err) {
                console.error('[Orion] Overlay injection failed:', err);
                // Final Fallback: Windows API
                try {
                    await chrome.windows.create({
                        url: 'popup.html',
                        type: 'popup',
                        width: 400,
                        height: 600
                    });
                } catch (winErr) {
                    console.error('[Orion] Window creation failed:', winErr);
                }
            }
        }
    }
}

async function handleCheckoutDetected(message) {
    try {
        await initializeBudget();
        
        const result = await chrome.storage.local.get(['budget', 'currency', 'budgetRemaining', 'spendingHistory']);
        const budget = result.budget ?? DEFAULTS.budget;
        const currency = result.currency ?? DEFAULTS.currency;
        
        const history = result.spendingHistory || [];
        const currentMonth = getMonthKey();
        const totalSpent = history
            .filter(p => p.month === currentMonth)
            .reduce((sum, p) => sum + (p.price || 0), 0);
        
        const productPrice = message.product.price || 0;
        const updatedRemaining = Math.max(0, budget - (totalSpent + productPrice));
        
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

// --- Message Router ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Wrap in async function to handle await properly
    (async () => {
        try {
            let result;
            
            switch (message.type) {
                case MESSAGE_TYPES.CHECKOUT_DETECTED:
                    result = await handleCheckoutDetected(message);
                    break;
                    
                case MESSAGE_TYPES.GET_PENDING_PRODUCT:
                    const { pendingProduct } = await chrome.storage.local.get('pendingProduct');
                    result = { product: pendingProduct };
                    break;
                    
                case MESSAGE_TYPES.CLEAR_PENDING_PRODUCT:
                case MESSAGE_TYPES.CANCEL_CHECKOUT:
                case MESSAGE_TYPES.PROCEED_CHECKOUT:
                    result = await handleClearPendingProduct();
                    break;
                    
                case MESSAGE_TYPES.PURCHASE_CONFIRMED:
                    if (message.product) await recordPurchase(message.product);
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

                case MESSAGE_TYPES.WAIT_24H:
                    const { pendingProduct: waitProd } = await chrome.storage.local.get('pendingProduct');
                    result = await handleWait24H(waitProd);
                    break;

                case MESSAGE_TYPES.SAVE_TO_WISHLIST:
                    const { pendingProduct: wishProd } = await chrome.storage.local.get('pendingProduct');
                    result = await handleWishlist(wishProd);
                    break;
                    
                default:
                    result = { status: 'unknown_message_type' };
            }
            sendResponse(result);
        } catch (error) {
            console.error('[Orion] Message handler error:', error);
            sendResponse({ status: 'error', message: error.message });
        }
    })();
    
    return true; // Keep channel open for async response
});

// --- Initialization ---

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
