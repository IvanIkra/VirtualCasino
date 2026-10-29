// Хранилище казино: пользователи, баланс, транзакции и настройки игр живут в localStorage браузера
(function () {
    const USERS_KEY = 'casino_users';
    const SESSION_KEY = 'casino_current_user';
    const CONFIGS_KEY = 'casino_game_configs';
    const FLASH_KEY = 'casino_flash';
    const MAX_TRANSACTIONS = 200;
    const START_BALANCE = 1000;

    const DEFAULT_CONFIGS = {
        slots: {
            SYMBOLS: ['🍒', '🍊', '🍋', '🍇', '7️⃣', '💎'],
            WEIGHTS: { '🍒': 30, '🍊': 25, '🍋': 20, '🍇': 15, '7️⃣': 7, '💎': 3 },
            PAYOUTS: { '🍒': 2, '🍊': 3, '🍋': 4, '🍇': 5, '7️⃣': 10, '💎': 20 }
        }
    };

    function read(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (e) {
            return fallback;
        }
    }

    function write(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {
            console.error('Не удалось сохранить данные:', e);
        }
    }

    function money(value) {
        return Math.round(value * 100) / 100;
    }

    async function hashPassword(username, password) {
        const data = new TextEncoder().encode(username + ':' + password);
        if (window.crypto && crypto.subtle) {
            const buf = await crypto.subtle.digest('SHA-256', data);
            return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
        }
        // Запасной вариант для небезопасного контекста (например, file://)
        let h = 0x811c9dc5;
        for (const b of data) {
            h ^= b;
            h = Math.imul(h, 0x01000193) >>> 0;
        }
        return 'fnv-' + h.toString(16);
    }

    function getUsers() {
        return read(USERS_KEY, {});
    }

    function saveUsers(users) {
        write(USERS_KEY, users);
    }

    function newUser(username, passwordHash, isAdmin) {
        return {
            username: username,
            passwordHash: passwordHash,
            balance: START_BALANCE,
            total_income: 0,
            total_expense: 0,
            is_admin: isAdmin,
            created_at: new Date().toISOString(),
            transactions: []
        };
    }

    // Создаем пользователя админа, если его нет
    async function ensureAdmin() {
        const users = getUsers();
        if (!users.admin) {
            users.admin = newUser('admin', await hashPassword('admin', 'admin'), true);
            saveUsers(users);
        }
    }

    function currentUser() {
        const username = read(SESSION_KEY, null);
        if (!username) return null;
        return getUsers()[username] || null;
    }

    // Изменяет текущего пользователя: всегда читаем свежие данные, чтобы не затереть изменения из другой вкладки
    function updateCurrentUser(mutator) {
        const username = read(SESSION_KEY, null);
        const users = getUsers();
        const user = username && users[username];
        if (!user) return { ok: false, error: 'Вы не авторизованы' };
        const result = mutator(user) || { ok: true };
        if (result.ok) {
            user.balance = money(user.balance);
            user.transactions = user.transactions.slice(-MAX_TRANSACTIONS);
            saveUsers(users);
            result.balance = user.balance;
        }
        return result;
    }

    function addTransaction(user, tx) {
        user.transactions.push(Object.assign({
            game_type: null,
            bet_type: null,
            bet_value: null,
            result: null,
            timestamp: new Date().toISOString()
        }, tx));
    }

    function placeBet(amount, gameType, details) {
        amount = Number(amount);
        if (!isFinite(amount) || amount <= 0) {
            return { ok: false, error: 'Неверная сумма ставки' };
        }
        return updateCurrentUser(user => {
            if (user.balance < amount) {
                return { ok: false, error: 'Недостаточно средств' };
            }
            user.balance -= amount;
            user.total_expense = money(user.total_expense + amount);
            addTransaction(user, Object.assign({ type: 'bet', amount: -money(amount), game_type: gameType }, details));
            return { ok: true };
        });
    }

    function addWin(amount, gameType, details) {
        amount = money(amount);
        return updateCurrentUser(user => {
            user.balance += amount;
            user.total_income = money(user.total_income + amount);
            addTransaction(user, Object.assign({ type: 'win', amount: amount, game_type: gameType }, details));
            return { ok: true };
        });
    }

    function deposit(amount, source, description) {
        return updateCurrentUser(user => {
            user.balance += amount;
            user.total_income = money(user.total_income + amount);
            addTransaction(user, { type: 'deposit', amount: amount, game_type: source, result: description });
            return { ok: true };
        });
    }

    async function register(username, password, confirmPassword) {
        username = (username || '').trim();
        if (!username || !password) return { ok: false, error: 'Все поля обязательны для заполнения' };
        if (password !== confirmPassword) return { ok: false, error: 'Пароли не совпадают' };
        await ensureAdmin();
        const users = getUsers();
        if (users[username]) return { ok: false, error: 'Пользователь с таким именем уже существует' };
        users[username] = newUser(username, await hashPassword(username, password), false);
        saveUsers(users);
        write(SESSION_KEY, username);
        return { ok: true };
    }

    async function login(username, password) {
        username = (username || '').trim();
        await ensureAdmin();
        const user = getUsers()[username];
        if (user && user.passwordHash === await hashPassword(username, password)) {
            write(SESSION_KEY, username);
            return { ok: true };
        }
        return { ok: false, error: 'Неверное имя пользователя или пароль' };
    }

    function logout() {
        try {
            localStorage.removeItem(SESSION_KEY);
        } catch (e) { /* ничего страшного */ }
    }

    function adminUpdateBalance(username, amount, action) {
        amount = Number(amount);
        if (!isFinite(amount) || amount <= 0) return { ok: false, error: 'Неверная сумма' };
        const users = getUsers();
        const user = users[username];
        if (!user) return { ok: false, error: 'Пользователь не найден' };
        if (action === 'add') {
            user.balance = money(user.balance + amount);
            addTransaction(user, { type: 'admin_add', amount: amount, game_type: 'admin' });
        } else if (action === 'subtract') {
            if (user.balance < amount) return { ok: false, error: 'Недостаточно средств на балансе' };
            user.balance = money(user.balance - amount);
            addTransaction(user, { type: 'admin_subtract', amount: -amount, game_type: 'admin' });
        } else {
            return { ok: false, error: 'Неверное действие' };
        }
        saveUsers(users);
        return { ok: true };
    }

    function getConfigs() {
        return Object.assign({}, DEFAULT_CONFIGS, read(CONFIGS_KEY, {}));
    }

    function getConfig(gameType) {
        return getConfigs()[gameType] || null;
    }

    function getDefaultConfig(gameType) {
        return JSON.parse(JSON.stringify(DEFAULT_CONFIGS[gameType] || null));
    }

    function saveConfig(gameType, config) {
        const stored = read(CONFIGS_KEY, {});
        if (config === null) {
            delete stored[gameType];
        } else {
            stored[gameType] = config;
        }
        write(CONFIGS_KEY, stored);
    }

    // Сообщение, которое покажется на следующей открытой странице (аналог flash во Flask)
    function flash(message, category) {
        try {
            sessionStorage.setItem(FLASH_KEY, JSON.stringify({ message: message, category: category || 'danger' }));
        } catch (e) { /* без сообщения тоже можно */ }
    }

    function takeFlash() {
        try {
            const raw = sessionStorage.getItem(FLASH_KEY);
            sessionStorage.removeItem(FLASH_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    window.Casino = {
        money: money,
        getUsers: getUsers,
        currentUser: currentUser,
        ensureAdmin: ensureAdmin,
        register: register,
        login: login,
        logout: logout,
        placeBet: placeBet,
        addWin: addWin,
        deposit: deposit,
        adminUpdateBalance: adminUpdateBalance,
        getConfigs: getConfigs,
        getConfig: getConfig,
        getDefaultConfig: getDefaultConfig,
        saveConfig: saveConfig,
        flash: flash,
        takeFlash: takeFlash
    };
})();
