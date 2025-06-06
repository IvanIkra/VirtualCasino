// Общие функции для всех игр
function updateBalance(newBalance) {
    const balanceAmountElements = document.querySelectorAll('.balance-amount');
    balanceAmountElements.forEach(element => {
        // Обновляем только числовое значение, оставляя префикс "Баланс: " и символ валюты "₽" вне этого элемента
        element.textContent = newBalance.toFixed(2);
    });
}

function addTransaction(timestamp, type, amount) {
    const tbody = document.querySelector('#transactions tbody');
    const row = document.createElement('tr');
    
    row.innerHTML = `
        <td>${timestamp}</td>
        <td>${type}</td>
        <td>${amount}₽</td>
    `;
    
    tbody.insertBefore(row, tbody.firstChild);
}

// Функция для обновления значения ставки
function updateBetValue() {
    const betType = document.querySelector('input[name="bet_type"]:checked');
    if (betType) {
        const betInput = document.getElementById('bet-amount');
        const multiplier = parseFloat(betType.dataset.multiplier || 1);
        betInput.value = Math.max(1, Math.round(betInput.value * multiplier));
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Инициализация обновления ставки
    const betTypeInputs = document.querySelectorAll('input[name="bet_type"]');
    if (betTypeInputs.length > 0) {
        betTypeInputs.forEach(input => {
            input.addEventListener('change', updateBetValue);
        });
        updateBetValue();
    }
}); 