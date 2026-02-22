document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyze-btn');
    const statusBox = document.getElementById('status-box');
    const statusMessage = document.getElementById('status-message');

    function setStatus(msg, type = 'loading') {
        statusBox.className = type;
        statusMessage.textContent = msg;
        statusBox.classList.remove('hidden');
    }

    analyzeBtn.addEventListener('click', async () => {
        analyzeBtn.disabled = true;
        setStatus('Extracting product info...', 'loading');

        try {
            // Get active tab
            let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            if (!tab.url.startsWith('http')) {
                throw new Error('Cannot analyze this page.');
            }

            // Execute script in the active tab to extract product title and price
            const results = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['content.js']
            });

            const productData = results[0].result;

            if (!productData || !productData.product_title) {
                throw new Error('Could not find a product on this page.');
            }

            setStatus(`Found: ${productData.product_title.substring(0, 30)}...\nAnalyzing with Orion...`, 'loading');

            // Hardcode user data for the demo, bridging to /analyze-demo
            const payload = {
                user_data: {
                    user_id: "demo_user",
                    monthly_income: 8000.0,
                    current_balance: 12400.0,
                    pay_cycle: "bi-weekly",
                    days_until_payday: 14,
                    savings_goals: [
                        {
                            name: "House Down Payment",
                            current_amount: 45000.0,
                            target_amount: 100000.0
                        }
                    ],
                    debts: [],
                    transactions: []
                },
                product_data: {
                    product_title: productData.product_title,
                    price: productData.price || 0.0,
                    category: "Shopping",
                    description: `URL: ${tab.url}`
                }
            };

            const response = await fetch('http://localhost:8000/api/v1/analyze-demo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Backend error: ${response.status}`);
            }

            const analysisResult = await response.json();

            // Success! We encode the result and redirect the original tab to the Orion dashboard
            setStatus('Analysis complete! Redirecting...', 'loading');

            const dashboardUrl = new URL('http://127.0.0.1:5500/frontend/index.html');
            // searchParams.set automatically URL-encodes the value. No need for encodeURIComponent.
            dashboardUrl.searchParams.set('analysis', JSON.stringify({
                product: productData,
                result: analysisResult
            }));
            dashboardUrl.hash = '#page-analytics';

            // Update the tab to the dashboard URL
            chrome.tabs.update(tab.id, { url: dashboardUrl.toString() });

            // Close the popup
            window.close();

        } catch (error) {
            console.error('Error:', error);
            setStatus(error.message || 'An error occurred.', 'error');
            analyzeBtn.disabled = false;
        }
    });
});
