// Общая разметка страниц (навбар, пополнение через рекламу, сообщения) и проверка доступа
(function () {
    const AD_VIDEOS = ['ad/ad.mp4', 'ad/videoadd1.mp4', 'ad/videoadd2.mp4', 'ad/videoadd3.mp4'];
    const AD_REWARD = 1000;

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[ch]);
    }

    function formatMoney(value) {
        return Number(value || 0).toFixed(2);
    }

    function formatDate(iso) {
        const d = new Date(iso);
        return isNaN(d) ? '-' : d.toLocaleString('ru-RU');
    }

    // Обновляем все отображения баланса на странице
    function updateBalance(newBalance) {
        document.querySelectorAll('.balance-amount').forEach(element => {
            element.textContent = formatMoney(newBalance);
        });
    }

    function renderNav(user) {
        let right;
        if (user) {
            right = `
                <div class="d-flex align-items-center">
                    <button class="btn btn-success me-3" data-bs-toggle="modal" data-bs-target="#depositModal">
                        <i class="fas fa-plus-circle"></i> Пополнить
                    </button>
                    <span class="balance me-3">Баланс: <span class="balance-amount">${formatMoney(user.balance)}</span>₽</span>
                    <div class="dropdown">
                        <button class="btn btn-dark dropdown-toggle" type="button" id="userMenu" data-bs-toggle="dropdown" aria-expanded="false">
                            ${escapeHtml(user.username)}
                        </button>
                        <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end" aria-labelledby="userMenu">
                            <li><a class="dropdown-item text-light" href="profile.html">Профиль</a></li>
                            ${user.is_admin ? '<li><a class="dropdown-item text-light" href="admin.html">Админ панель</a></li>' : ''}
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item text-light" href="#" id="logoutLink">Выйти</a></li>
                        </ul>
                    </div>
                </div>`;
        } else {
            right = `
                <div class="dropdown">
                    <button class="btn btn-dark dropdown-toggle" type="button" id="authMenu" data-bs-toggle="dropdown" aria-expanded="false">
                        Войти
                    </button>
                    <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end" aria-labelledby="authMenu">
                        <li><a class="dropdown-item text-light" href="login.html">Войти</a></li>
                        <li><a class="dropdown-item text-light" href="register.html">Регистрация</a></li>
                    </ul>
                </div>`;
        }

        const nav = document.createElement('nav');
        nav.className = 'navbar navbar-expand-lg navbar-dark bg-black';
        nav.innerHTML = `
            <div class="container flex-wrap gap-2">
                <a class="navbar-brand" href="index.html">🎰 Виртуальное Казино</a>
                <div class="ms-auto d-flex align-items-center">${right}</div>
            </div>`;
        document.body.prepend(nav);

        const logoutLink = document.getElementById('logoutLink');
        if (logoutLink) {
            logoutLink.addEventListener('click', event => {
                event.preventDefault();
                Casino.logout();
                location.href = 'login.html';
            });
        }
    }

    function renderDepositModal() {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
            <div class="modal fade" id="depositModal" tabindex="-1" aria-labelledby="depositModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content bg-dark text-light">
                        <div class="modal-header">
                            <h5 class="modal-title" id="depositModalLabel">Пополнение баланса</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <button class="btn btn-primary w-100" id="watchAdButton">
                                    <i class="fas fa-play-circle"></i> Смотреть рекламу (+${AD_REWARD}₽)
                                </button>
                            </div>
                            <div id="adPlayer" class="d-none">
                                <video id="adVideo" class="w-100" playsinline>
                                    Ваш браузер не поддерживает видео.
                                </video>
                            </div>
                            <div id="videoError" class="alert alert-danger mt-2 d-none">
                                Ошибка загрузки видео. Пожалуйста, попробуйте позже.
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(wrapper.firstElementChild);

        const depositModal = document.getElementById('depositModal');
        const watchAdButton = document.getElementById('watchAdButton');
        const adPlayer = document.getElementById('adPlayer');
        const adVideo = document.getElementById('adVideo');
        const videoError = document.getElementById('videoError');

        function resetPlayer() {
            adVideo.pause();
            adVideo.removeAttribute('src');
            adVideo.load();
            adPlayer.classList.add('d-none');
            watchAdButton.classList.remove('d-none');
        }

        function showError() {
            videoError.classList.remove('d-none');
            resetPlayer();
        }

        depositModal.addEventListener('show.bs.modal', () => {
            videoError.classList.add('d-none');
            resetPlayer();
        });
        depositModal.addEventListener('hidden.bs.modal', resetPlayer);

        watchAdButton.addEventListener('click', () => {
            watchAdButton.classList.add('d-none');
            adPlayer.classList.remove('d-none');
            videoError.classList.add('d-none');
            adVideo.src = AD_VIDEOS[Math.floor(Math.random() * AD_VIDEOS.length)];
            adVideo.onerror = showError;
            const playPromise = adVideo.play();
            if (playPromise !== undefined) {
                playPromise.catch(error => {
                    console.error('Error playing video:', error);
                    showError();
                });
            }
        });

        // Награда только за полностью досмотренное видео
        adVideo.addEventListener('ended', () => {
            const result = Casino.deposit(AD_REWARD, 'ad', 'Пополнение за просмотр рекламы');
            if (!result.ok) {
                alert(result.error || 'Произошла ошибка при пополнении баланса');
                return;
            }
            updateBalance(result.balance);
            const modal = bootstrap.Modal.getInstance(depositModal);
            if (modal) modal.hide();
        });
    }

    function renderFlash() {
        const flash = Casino.takeFlash();
        const area = document.getElementById('flash-area');
        if (!flash || !area) return;
        const div = document.createElement('div');
        div.className = `alert alert-${flash.category} alert-dismissible fade show`;
        div.setAttribute('role', 'alert');
        div.innerHTML = `${escapeHtml(flash.message)}<button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert" aria-label="Close"></button>`;
        area.appendChild(div);
    }

    // data-auth на <body>: "user" — нужен вход, "admin" — нужны права админа
    const auth = document.body.dataset.auth;
    const user = Casino.currentUser();
    let allowed = true;

    if ((auth === 'user' || auth === 'admin') && !user) {
        Casino.flash('Необходимо войти для доступа к этой странице.');
        location.replace('login.html');
        allowed = false;
    } else if (auth === 'admin' && !user.is_admin) {
        Casino.flash('Недостаточно прав доступа');
        location.replace('index.html');
        allowed = false;
    }

    if (allowed) {
        renderNav(user);
        if (user) renderDepositModal();
        renderFlash();
    }

    window.updateBalance = updateBalance;
    window.escapeHtml = escapeHtml;
    window.formatMoney = formatMoney;
    window.formatDate = formatDate;

    // Код страницы запускается только если доступ разрешен
    Casino.ready = function (fn) {
        if (allowed) fn(Casino.currentUser());
    };
})();
