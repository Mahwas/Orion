# Orion - Shopping Assistant

A Chrome extension that helps prevent impulsive purchases by intercepting checkout flows and prompting users to reconsider their buying decisions.

![Version](https://img.shields.io/badge/version-1.0-blue)
![Manifest](https://img.shields.io/badge/manifest-v3-green)

## Features

- **Checkout Detection**: Automatically detects checkout pages across 50+ e-commerce platforms
- **Price Extraction**: Extracts product name, price, and merchant from various sources (DOM, meta tags, JSON-LD)
- **Budget Tracking**: Monthly budget tracking with automatic reset
- **One-Click Purchase Prevention**: Intercepts Apple Pay, Google Pay, PayPal, and express checkout buttons
- **Iframe Support**: Detects checkout flows within iframes (Stripe, PayPal)
- **Smart Delays**: Multiple detection passes to catch dynamically loaded content

## How It Works

1. When you click a checkout/buy button or navigate to a checkout page
2. Orion intercepts the action and extracts product information
3. A popup appears showing:
   - Product details (name, price, merchant)
   - Budget status (remaining this month)
   - Thought-provoking questions to help you reconsider
4. You can either:
   - **Cancel Purchase**: Block the transaction and navigate away
   - **I'll Think About It**: Proceed anyway (and optionally track the purchase)

## Installation

### From Source

1. Clone the repository
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable **Developer mode** (top right toggle)
4. Click **Load unpacked**
5. Select the `extension` folder

### Development Mode

For development with auto-reload:

```bash
# Using Chrome extension reloader (recommended)
# Install: https://chrome.google.com/webstore/detail/extensions-reloader/fimgcfajfkdnkhnfnfblhkfkgcjnlmfj
```

## Project Structure

```
extension/
├── manifest.json          # Extension configuration
├── background.js          # Service worker (budget, storage, messaging)
├── content.js            # Page script (detection, interception)
├── popup.html            # Extension popup UI
├── popup.js              # Popup logic
├── styles.css            # Popup styling
├── config/
│   └── selectors.json    # Platform-specific selectors
└── README.md             # This file
```

## Configuration

### Budget Settings

- Set monthly spending limit
- Currency selection (USD, EUR, GBP, JPY, CAD, AUD)
- Budget automatically resets each month

### Dashboard

Configure a dashboard URL to track spending history (default: `http://localhost:3000`)

## Technical Details

### Detection Methods

1. **URL Pattern Matching**: Checks against 30+ checkout URL patterns
2. **Button Detection**: Identifies checkout buttons by text, classes, IDs, and data attributes
3. **Form Analysis**: Intercepts form submissions with checkout-related keywords
4. **Keyboard Shortcuts**: Captures Enter key in checkout form fields

### Price Extraction (in order of priority)

1. CSS selectors (`.price`, `#price`, `[data-price]`, etc.)
2. Open Graph meta tags (`og:price:amount`)
3. JSON-LD structured data (`application/ld+json`)

### Browser Storage

| Key | Type | Description |
|-----|------|-------------|
| `budget` | number | Monthly budget limit |
| `currency` | string | Selected currency |
| `budgetRemaining` | number | Remaining budget |
| `spendingHistory` | array | Last 100 purchases |
| `pendingProduct` | object | Current intercepted product |
| `showIntervention` | boolean | Whether to show popup |
| `lastResetMonth` | string | YYYY-MM of last budget reset |

## Permissions

- `activeTab`: Access current tab information
- `scripting`: Inject content scripts
- `storage`: Persist user settings and budget
- `tabs`: Create and update tabs

## Supported Platforms

Tested on major e-commerce platforms including:

- Amazon, eBay, Walmart, Target
- Shopify stores (generic)
- WooCommerce stores
- BigCommerce stores
- And 40+ more checkout patterns

## License

MIT License

## Contributing

Pull requests are welcome! Please ensure:
- Tests pass before submitting
- Code follows existing style
- New features include documentation
