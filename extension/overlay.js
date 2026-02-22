(function() {
    if (window.orionOverlayActive) return;
    window.orionOverlayActive = true;

    const STYLES = {
        overlay: `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 10, 15, 0.95);
            z-index: 2147483647;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-family: 'Inter', -apple-system, sans-serif;
            color: white;
            text-align: center;
            padding: 20px;
            backdrop-filter: blur(10px);
        `,
        container: `
            max-width: 400px;
            padding: 40px;
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        `,
        productBox: `
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 16px;
            margin-bottom: 20px;
            text-align: left;
        `
    };

    function createOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'orion-interception-overlay';
        overlay.style.cssText = STYLES.overlay;

        overlay.innerHTML = `
            <div style="${STYLES.container}">
                <div style="font-size: 64px; margin-bottom: 20px;">⚡</div>
                <h1 style="font-size: 28px; margin-bottom: 16px; background: linear-gradient(90deg, #00d4ff, #7b2ff7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Pause for a moment</h1>
                <p style="color: rgba(255,255,255,0.7); margin-bottom: 30px; line-height: 1.6;">Orion detected a checkout. Before you buy, consider if this matches your financial goals.</p>
                
                <div id="orion-product-preview" style="${STYLES.productBox}">
                    <div id="orion-product-title" style="font-weight: 600; margin-bottom: 8px;">Product Loading...</div>
                    <div id="orion-product-price" style="font-size: 24px; font-weight: 700; color: #ff2d6a;">$0.00</div>
                </div>

                <div style="display: flex; flex-direction: column; gap: 12px;">
                    <button id="orion-btn-cancel" style="padding: 16px; border-radius: 12px; border: none; background: #00ff88; color: black; font-weight: 700; cursor: pointer; font-size: 16px;">Cancel Purchase</button>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <button id="orion-btn-wait" style="padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2); background: transparent; color: white; font-weight: 600; cursor: pointer; font-size: 13px;">Wait 24h</button>
                        <button id="orion-btn-wishlist" style="padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2); background: transparent; color: white; font-weight: 600; cursor: pointer; font-size: 13px;">Wishlist</button>
                    </div>
                    <button id="orion-btn-proceed" style="padding: 12px; background: transparent; border: none; color: rgba(255,255,255,0.4); cursor: pointer; font-size: 13px;">Continue anyway</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        return overlay;
    }

    function closeOverlay(overlay) {
        overlay.remove();
        window.orionOverlayActive = false;
    }

    function updateProductInfo() {
        chrome.storage.local.get(['pendingProduct', 'currency'], (result) => {
            if (!result.pendingProduct) return;

            const titleEl = document.getElementById('orion-product-title');
            const priceEl = document.getElementById('orion-product-price');

            if (titleEl) titleEl.textContent = result.pendingProduct.title;
            
            if (priceEl) {
                const currency = result.currency || '$';
                priceEl.textContent = `${currency}${result.pendingProduct.price}`;
            }
        });
    }

    const overlay = createOverlay();
    updateProductInfo();

    // Event Listeners
    const actions = {
        'orion-btn-cancel': () => {
            chrome.runtime.sendMessage({ type: 'CANCEL_CHECKOUT' });
            window.history.back();
            closeOverlay(overlay);
        },
        'orion-btn-wishlist': () => {
            chrome.runtime.sendMessage({ type: 'SAVE_TO_WISHLIST' });
            closeOverlay(overlay);
        },
        'orion-btn-wait': () => {
            chrome.runtime.sendMessage({ type: 'WAIT_24H' });
            closeOverlay(overlay);
        },
        'orion-btn-proceed': () => {
            chrome.runtime.sendMessage({ type: 'PROCEED_CHECKOUT' });
            closeOverlay(overlay);
        }
    };

    Object.entries(actions).forEach(([id, handler]) => {
        const btn = document.getElementById(id);
        if (btn) btn.onclick = handler;
    });

})();
