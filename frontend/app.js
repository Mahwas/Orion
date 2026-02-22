console.log("Orion App loaded at " + new Date().toLocaleTimeString());

// =============================================
// SPA Router — handles tab switching
// =============================================
const navLinks = document.querySelectorAll('.nav-links a[data-page]');
const pageViews = document.querySelectorAll('.page-view');

function navigateTo(pageName) {
    // Hide all pages
    pageViews.forEach(view => {
        view.classList.remove('active-page');
    });

    // Show target page
    const target = document.getElementById(`page-${pageName}`);
    if (target) {
        target.classList.add('active-page');
    }

    // Update active nav link
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.dataset.page === pageName) {
            link.classList.add('active');
        }
    });

    // Trigger page-specific logic on first visit
    if (pageName === 'accounts') {
        fetchAllData();
    }
}

// Attach click handlers to nav links
navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.dataset.page;
        navigateTo(page);
    });
});

// =============================================
// Analytics (Extension Bridge)
// =============================================
function handleUrlParams() {
    // Check search params (standard)
    let params = new URLSearchParams(window.location.search);
    let analysisDataParam = params.get('analysis');

    // Fallback: check hash params (if some tool/browser puts them there)
    if (!analysisDataParam && window.location.hash.includes('?')) {
        const hashSearch = window.location.hash.split('?')[1];
        params = new URLSearchParams(hashSearch);
        analysisDataParam = params.get('analysis');
    }

    if (analysisDataParam) {
        try {
            // URLSearchParams.get already decodes once. JSON should be clean now.
            const data = JSON.parse(analysisDataParam);
            console.log("Received Analysis Data:", data);

            // Clean up the URL (remove params but keep hash for routing if needed)
            const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname + window.location.hash;
            window.history.replaceState({}, document.title, cleanUrl);

            // Switch to Analytics tab
            navigateTo('analytics');

            // Render
            renderAnalysis(data.product, data.result);
        } catch (e) {
            console.error("Failed to parse analysis data from URL", e);
        }
    }
}

function renderAnalysis(product, result) {
    const content = document.getElementById('analytics-content');
    const status = document.getElementById('analytics-status');

    status.innerText = "Analysis Complete";
    status.style.color = "var(--accent-primary)";

    let verdictColor = "var(--text-primary)";
    if (result.verdict === "BUY") verdictColor = "var(--accent-income)";
    if (result.verdict === "DO_NOT_BUY") verdictColor = "var(--accent-expense)";
    if (result.verdict === "ALTERNATIVE_RECOMMENDED") verdictColor = "#f59e0b"; // amber

    let html = `
        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: 16px; padding: 30px; margin-bottom: 30px;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 20px;">
                <div>
                    <h2 style="font-size: 1.8rem; margin-bottom: 5px;">${product.product_title || 'Unknown Product'}</h2>
                    <p style="font-size: 1.2rem; color: var(--text-secondary);">$${parseFloat(product.price || 0).toFixed(2)}</p>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-secondary); margin-bottom: 5px;">Verdict</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: ${verdictColor}; padding: 5px 15px; border: 2px solid ${verdictColor}; border-radius: 8px;">
                        ${result.verdict.replace(/_/g, ' ')}
                    </div>
                </div>
            </div>
            
            <div style="padding: 20px; background: rgba(0,0,0,0.3); border-radius: 12px; margin-bottom: 30px;">
                <h3 style="font-size: 1rem; margin-bottom: 10px; color: var(--text-secondary);">Agent Reasoning</h3>
                <p style="line-height: 1.6;">${result.reasoning}</p>
            </div>
    `;

    if (result.similar_products_found && result.similar_products_found.length > 0) {
        html += `
            <h3 style="font-size: 1.2rem; margin-bottom: 15px;">Alternative Recommendations</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px;">
        `;

        result.similar_products_found.forEach(alt => {
            html += `
                <div style="background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); border-radius: 12px; padding: 20px; transition: transform 0.2s;">
                    <h4 style="font-size: 1rem; margin-bottom: 10px;">${alt.title}</h4>
                    <div style="font-size: 1.2rem; font-weight: bold; color: var(--accent-income); margin-bottom: 15px;">$${alt.price.toFixed(2)}</div>
                    ${alt.url ? `<a href="${alt.url}" target="_blank" class="btn" style="text-decoration: none; display: inline-block; text-align: center; font-size: 0.8rem; padding: 8px 15px;">View Deal</a>` : ''}
                </div>
            `;
        });

        html += `</div>`;
    }

    html += `</div>`;
    content.innerHTML = html;
}

// =============================================
// Dashboard logic
// =============================================
const balance = document.getElementById('balance');
const incomeDisplay = document.getElementById('income');
const expenseDisplay = document.getElementById('expense');
const list = document.getElementById('list');

const bankList = document.getElementById('bank-list');
const bankForm = document.getElementById('bank-form');
const bankName = document.getElementById('bank-name');
const bankBalance = document.getElementById('bank-balance');
const historyTitle = document.getElementById('history-title');

const API_BASE = "http://localhost:8000/api/v1";
const localStorageBanks = JSON.parse(localStorage.getItem('banks'));
let banks = []; // We will populate this from the DB

let activeBankId = null;

async function init() {
    try {
        const response = await fetch(`${API_BASE}/all-data`);
        const data = await response.json();

        // Flatten accounts from all users into the dashboard 'banks' list
        banks = [];
        data.users.forEach(user => {
            user.accounts.forEach(acc => {
                banks.push({
                    id: acc.id,
                    name: `${user.name}'s ${acc.type}`,
                    balance: acc.balance,
                    transactions: acc.transactions // Store transactions for filtering
                });
            });
        });

        bankList.innerHTML = '';
        banks.forEach(addBankDOM);
        updateValues();
        updateHistoryDOM();
    } catch (error) {
        console.error("Failed to sync with DB:", error);
        // Fallback to local storage if DB is down
        banks = localStorageBanks || [];
        bankList.innerHTML = '';
        banks.forEach(addBankDOM);
        updateValues();
    }
}

async function addBank(e) {
    console.log("Adding bank account...");
    e.preventDefault();

    if (bankName.value.trim() === '' || bankBalance.value.trim() === '') {
        alert('Please add a bank name and balance');
        return;
    }

    const payload = {
        user_id: 1, // Defaulting to John Doe for the demo
        account_type: bankName.value,
        balance: +bankBalance.value
    };

    try {
        const response = await fetch(`${API_BASE}/bank-accounts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Failed to create bank account');

        const data = await response.json();

        // Clear inputs
        const nameVal = bankName.value;
        const balanceVal = +bankBalance.value;
        bankName.value = '';
        bankBalance.value = '';

        // Update local state immediately instead of waiting for full init() re-fetch
        const newBank = {
            id: data.account_id,
            name: `John Doe's ${nameVal}`,
            balance: balanceVal,
            transactions: [{
                merchant: "Account Opening",
                amount: balanceVal,
                category: "Initial Deposit",
                timestamp: new Date().toISOString(),
                type: "CREDIT"
            }]
        };

        banks.push(newBank);

        // Instant update without clearing everything
        addBankDOM(newBank);
        selectBank(data.account_id); // This handles setting active class and updating history
        updateValues();
        updateLocalStorage();

    } catch (error) {
        console.error("Error adding bank:", error);
        alert("Failed to sync with backend. Check if the server is running.");

        // Fallback for demo if backend is truly unreachable and user wants local-only
        const bank = {
            id: generateID(),
            name: bankName.value,
            balance: +bankBalance.value,
            transactions: [{
                id: generateID(),
                merchant: "Initial Deposit (Local Only)",
                amount: +bankBalance.value,
                category: "Opening Balance",
                timestamp: new Date().toISOString(),
                type: "CREDIT"
            }]
        };
        banks.push(bank);
        addBankDOM(bank);
        updateValues();
        updateLocalStorage();
        bankName.value = '';
        bankBalance.value = '';
    }
}

function generateID() {
    return Math.floor(Math.random() * 100000000);
}

function selectBank(id) {
    activeBankId = id;

    // Update active class
    const bankItems = document.querySelectorAll('.bank-list li');
    bankItems.forEach(item => {
        item.classList.remove('active-bank');
        if (parseInt(item.dataset.id) === id) {
            item.classList.add('active-bank');
        }
    });

    const bank = banks.find(b => b.id === id);
    if (bank) {
        historyTitle.innerText = `${bank.name} History`;
    } else {
        historyTitle.innerText = 'History';
    }

    updateHistoryDOM();
}

function addBankDOM(bank) {
    const item = document.createElement('li');
    item.dataset.id = bank.id;

    // Add class based on value
    item.classList.add(bank.balance < 0 ? 'minus' : 'plus');

    if (activeBankId === bank.id) {
        item.classList.add('active-bank');
    }

    const sign = bank.balance < 0 ? '-' : '';

    item.innerHTML = `
        <div class="transaction-info">
            <span class="transaction-text">${bank.name}</span> 
            <span>${sign}$${Math.abs(bank.balance).toFixed(2)}</span>
        </div>
        <button class="delete-btn" onclick="removeBank(event, ${bank.id}); return false;">✖</button>
    `;

    item.onclick = () => selectBank(bank.id);

    bankList.appendChild(item);
}

function updateHistoryDOM() {
    list.innerHTML = '';

    if (activeBankId === null) {
        const item = document.createElement('li');
        item.style.justifyContent = 'center';
        item.style.background = 'transparent';
        item.style.border = 'none';
        item.style.boxShadow = 'none';
        item.innerHTML = `<span class="transaction-text" style="color: var(--text-secondary); font-style: italic;">Select a bank account.</span>`;
        list.appendChild(item);
        return;
    }

    const bank = banks.find(b => b.id === activeBankId);
    if (!bank || !bank.transactions || bank.transactions.length === 0) {
        const item = document.createElement('li');
        item.style.justifyContent = 'center';
        item.style.background = 'transparent';
        item.style.border = 'none';
        item.style.boxShadow = 'none';
        item.innerHTML = `<span class="transaction-text" style="color: var(--text-secondary); font-style: italic;">No transactions yet...</span>`;
        list.appendChild(item);
        return;
    }

    bank.transactions.forEach(tx => {
        const item = document.createElement('li');
        const isCredit = tx.type === 'CREDIT';
        item.classList.add(isCredit ? 'plus' : 'minus');

        item.innerHTML = `
            <div class="transaction-info">
                <div>
                    <span class="transaction-text" style="display: block;">${tx.merchant}</span>
                    <small style="color: var(--text-secondary); font-size: 0.75rem;">${tx.category} • ${new Date(tx.timestamp).toLocaleDateString()}</small>
                </div>
                <span class="font-bold">${isCredit ? '+' : '-'}$${tx.amount.toFixed(2)}</span>
            </div>
        `;
        list.appendChild(item);
    });
}

async function removeBank(e, id) {
    console.log("Removing bank account ID: " + id);
    e.stopPropagation();

    // Find the element for a smooth animation
    const li = e.target.closest('li');
    if (li) {
        li.classList.add('removing');
    }

    // Save original state for revert if needed
    const originalBanks = [...banks];
    const originalActiveId = activeBankId;

    // 1. Update state immediately (Optimistic UI)
    banks = banks.filter(bank => bank.id !== id);
    if (activeBankId === id) {
        activeBankId = null;
        historyTitle.innerText = 'History';
    }

    // 2. Refresh UI immediately (No lag!)
    updateValues();
    updateHistoryDOM();
    updateLocalStorage();

    // Just remove the one item from the DOM smoothly
    setTimeout(() => {
        if (li) li.remove();

        // If we removed the active bank, we need to show the "select an account" message in history
        if (originalActiveId === id) {
            updateHistoryDOM();
        }
    }, 150);

    // 3. Sync with background in the background
    try {
        const response = await fetch(`${API_BASE}/bank-accounts/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Server rejected deletion');
        }

    } catch (error) {
        console.error("Error deleting bank:", error);
        alert("Failed to delete account from server. Reverting...");

        // REVERT if server failed
        banks = originalBanks;
        activeBankId = originalActiveId;
        bankList.innerHTML = '';
        banks.forEach(addBankDOM);
        updateValues();
        updateHistoryDOM();
    }
}

function updateValues() {
    const amounts = banks.map(bank => bank.balance);
    const total = amounts.reduce((acc, item) => (acc += item), 0).toFixed(2);

    const income = amounts
        .filter(item => item > 0)
        .reduce((acc, item) => (acc += item), 0)
        .toFixed(2);

    const expense = (
        amounts.filter(item => item < 0).reduce((acc, item) => (acc += item), 0) *
        -1
    ).toFixed(2);

    balance.innerText = `$${total}`;
    incomeDisplay.innerText = `+$${income}`;
    expenseDisplay.innerText = `-$${expense}`;

    // Animate balance change
    balance.animate([
        { transform: 'scale(1.1)', color: 'white' },
        { transform: 'scale(1)', color: 'inherit' }
    ], {
        duration: 300,
        easing: 'ease-out'
    });
}

function updateLocalStorage() {
    localStorage.setItem('banks', JSON.stringify(banks));
}

bankForm.addEventListener('submit', addBank);

// =============================================
// Accounts (Data) page logic
// =============================================
const dataContent = document.getElementById('data-content');

async function fetchAllData() {
    try {
        const response = await fetch(`${API_BASE}/all-data`);
        if (!response.ok) throw new Error('Backend not reachable');
        const data = await response.json();
        renderData(data.users);
    } catch (error) {
        dataContent.innerHTML = `
            <div style="text-align: center; padding: 50px; background: rgba(239, 68, 68, 0.1); border-radius: 16px; border: 1px solid var(--accent-expense);">
                <h2 style="color: var(--accent-expense); margin-bottom: 10px;">Connection Error</h2>
                <p style="color: var(--text-secondary);">Unable to connect to the Orion Backend. Please ensure the server is running on port 8000.</p>
                <button onclick="fetchAllData()" class="btn" style="max-width: 200px; margin-top: 20px;">Retry Connection</button>
            </div>
        `;
    }
}

function renderData(users) {
    if (!users || users.length === 0) {
        dataContent.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">No data found in database.</p>';
        return;
    }

    let html = '';
    users.forEach(user => {
        html += `
            <div class="user-section" style="margin-bottom: 40px;">
                <div class="glass-panel" style="padding: 20px; border-radius: 16px; margin-bottom: 20px; background: rgba(255,255,255,0.05);">
                    <h2 style="font-size: 1.5rem; color: #fff;">${user.name}</h2>
                    <p style="color: var(--text-secondary);">${user.email}</p>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px;">
        `;

        user.accounts.forEach(acc => {
            html += `
                <div class="account-card glass-panel" style="padding: 0; overflow: hidden; border-radius: 16px;">
                    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 25px; border-bottom: 1px solid var(--glass-border);">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div>
                                <div style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px;">${acc.type} Account</div>
                                <div style="font-size: 2rem; font-weight: 700; color: #fff; margin-top: 5px;">$${acc.balance.toFixed(2)}</div>
                            </div>
                            <div style="background: rgba(99, 102, 241, 0.2); padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; color: var(--accent-primary); font-weight: 600; border: 1px solid var(--accent-primary);">${acc.currency}</div>
                        </div>
                    </div>
                    <div style="padding: 20px;">
                        <h4 style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 15px; text-transform: uppercase;">Recent Activity</h4>
                        <ul style="list-style: none;">
            `;

            acc.transactions.forEach(tx => {
                const isCredit = tx.type === 'CREDIT';
                html += `
                    <li style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 12px; margin-bottom: 8px; border-left: 3px solid ${isCredit ? 'var(--accent-income)' : 'var(--accent-expense)'}">
                        <div>
                            <div style="font-weight: 500; font-size: 0.95rem;">${tx.merchant}</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary);">${new Date(tx.timestamp).toLocaleDateString()} • ${tx.category}</div>
                        </div>
                        <div style="font-weight: 700; color: ${isCredit ? 'var(--accent-income)' : 'var(--accent-expense)'}">
                            ${isCredit ? '+' : '-'}$${tx.amount.toFixed(2)}
                        </div>
                    </li>
                `;
            });

            html += `
                        </ul>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    dataContent.innerHTML = html;
}

// =============================================
// Boot
// =============================================
handleUrlParams();
init();
