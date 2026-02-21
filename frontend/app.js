const balance = document.getElementById('balance');
const incomeDisplay = document.getElementById('income');
const expenseDisplay = document.getElementById('expense');
const list = document.getElementById('list');

const bankList = document.getElementById('bank-list');
const bankForm = document.getElementById('bank-form');
const bankName = document.getElementById('bank-name');
const bankBalance = document.getElementById('bank-balance');
const historyTitle = document.getElementById('history-title');

const localStorageBanks = JSON.parse(localStorage.getItem('banks'));
let banks = localStorage.getItem('banks') !== null ? localStorageBanks : [];

let activeBankId = null;

function init() {
    bankList.innerHTML = '';
    banks.forEach(addBankDOM);
    updateValues();
    updateHistoryDOM();
}

function addBank(e) {
    e.preventDefault();

    if (bankName.value.trim() === '' || bankBalance.value.trim() === '') {
        alert('Please add a bank name and balance');
    } else {
        const bank = {
            id: generateID(),
            name: bankName.value,
            balance: +bankBalance.value
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
        <button class="delete-btn" onclick="removeBank(event, ${bank.id})">✖</button>
    `;

    item.onclick = () => selectBank(bank.id);

    bankList.appendChild(item);
}

function updateHistoryDOM() {
    list.innerHTML = '';

    const item = document.createElement('li');
    item.style.justifyContent = 'center';
    item.style.background = 'transparent';
    item.style.border = 'none';
    item.style.boxShadow = 'none';

    if (activeBankId !== null) {
        item.innerHTML = `<span class="transaction-text" style="color: var(--text-secondary); font-style: italic;">No transactions yet...</span>`;
    } else {
        item.innerHTML = `<span class="transaction-text" style="color: var(--text-secondary); font-style: italic;">Select a bank account.</span>`;
    }
    list.appendChild(item);
}

function removeBank(e, id) {
    e.stopPropagation();
    banks = banks.filter(bank => bank.id !== id);
    if (activeBankId === id) {
        activeBankId = null;
        historyTitle.innerText = 'History';
    }
    updateLocalStorage();
    init();
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

init();
