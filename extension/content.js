// Extract product title and approximate price from the current page
(function extractProduct() {
    let title = document.title;

    // Attempt to refine title if it's too long (e.g. "Amazon.com : Apple Vision Pro : Electronics" -> "Apple Vision Pro")
    if (title.includes('Amazon.com') || title.includes(':')) {
        const parts = title.split(/[:|]/);
        // Usually the product name is the largest string, or the first meaningful one
        let bestPart = parts[0].trim();
        for (let p of parts) {
            if (p.length > bestPart.length && !p.includes('Amazon') && !p.includes('Electronics')) {
                bestPart = p.trim();
            }
        }
        title = bestPart;
    }

    // Attempt to find a price
    let price = 0;

    // Look for common price patterns like $99.99 or $1,200.00
    // We'll search the body text, but it's tricky.
    // A better approach for a quick extension is to look at specific classes or just do a regex on the body text
    const priceRegex = /\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)/g;

    // Heuristic: check specific common price selectors first
    const priceSelectors = [
        '.a-price-whole', // Amazon
        '[data-test="product-price"]', // Target
        '.priceView-hero-price span', // BestBuy
        '.price', // Generic
        '#price'  // Generic
    ];

    let priceText = null;
    for (const selector of priceSelectors) {
        const el = document.querySelector(selector);
        if (el && el.innerText.includes('$')) {
            priceText = el.innerText;
            break;
        }
    }

    // Fallback: search the first 5000 chars of body text for a price
    if (!priceText) {
        const bodyText = document.body.innerText.substring(0, 5000);
        let match;
        let maxPrice = 0;
        // Find *highest* reasonable price in the first bit of text (often the product price is higher than related items)
        while ((match = priceRegex.exec(bodyText)) !== null) {
            const val = parseFloat(match[1].replace(/,/g, ''));
            if (val > maxPrice && val < 100000) { // arbitrary cap to avoid crazy values
                maxPrice = val;
                priceText = match[0];
            }
        }
    }

    if (priceText) {
        // clean up price string and convert to float
        const cleanPrice = priceText.replace(/[^0-9.]/g, '');
        price = parseFloat(cleanPrice);
    } else {
        // Fallback for demo if no price found
        price = 0.0;
    }

    return {
        product_title: title,
        price: price
    };
})();
