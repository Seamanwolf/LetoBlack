/**
 * Система Toast уведомлений
 * Заменяет flash сообщения и alert'ы
 */

class ToastManager {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Создаем контейнер для toast'ов если его нет
        this.container = document.querySelector('.toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }

        // Перехватываем flash сообщения при загрузке страницы
        this.convertFlashMessages();
        
        // Перехватываем alert'ы
        this.interceptAlerts();
    }

    /**
     * Показать toast уведомление
     * @param {string} message - Текст сообщения
     * @param {string} type - Тип: success, error, warning, info
     * @param {number} duration - Длительность показа в мс (0 = не скрывать автоматически)
     * @param {string} title - Заголовок (опционально)
     */
    show(message, type = 'info', duration = 5000, title = null) {
        const toast = this.createToast(message, type, title);
        this.container.appendChild(toast);

        // Показываем toast с анимацией
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        // Автоматическое скрытие
        if (duration > 0) {
            setTimeout(() => {
                this.hide(toast);
            }, duration);
        }

        return toast;
    }

    /**
     * Создать элемент toast'а
     */
    createToast(message, type, title) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            danger: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        const titles = {
            success: 'Успешно',
            error: 'Ошибка',
            danger: 'Ошибка',
            warning: 'Внимание',
            info: 'Информация'
        };

        const toastTitle = title || titles[type] || 'Уведомление';
        const iconClass = icons[type] || 'fas fa-info-circle';

        toast.innerHTML = `
            <div class="toast-header">
                <i class="${iconClass} toast-icon ${type}"></i>
                <span class="toast-title">${toastTitle}</span>
                <button class="toast-close" onclick="toastManager.hide(this.closest('.toast'))">&times;</button>
            </div>
            <div class="toast-body">${message}</div>
            <div class="toast-progress">
                <div class="toast-progress-bar"></div>
            </div>
        `;

        return toast;
    }

    /**
     * Скрыть toast
     */
    hide(toast) {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    /**
     * Преобразовать flash сообщения в toast'ы
     */
    convertFlashMessages() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const message = alert.textContent.trim();
            let type = 'info';

            if (alert.classList.contains('alert-success')) type = 'success';
            else if (alert.classList.contains('alert-danger')) type = 'error';
            else if (alert.classList.contains('alert-warning')) type = 'warning';
            else if (alert.classList.contains('alert-info')) type = 'info';

            // Показываем toast и скрываем оригинальный alert
            this.show(message, type);
            alert.style.display = 'none';
        });
    }

    /**
     * Перехватываем стандартные alert'ы
     */
    interceptAlerts() {
        const originalAlert = window.alert;
        window.alert = (message) => {
            this.show(message, 'info');
        };

        // Сохраняем оригинальную функцию для экстренных случаев
        window.originalAlert = originalAlert;
    }

    // Удобные методы для разных типов уведомлений
    success(message, title = null, duration = 5000) {
        return this.show(message, 'success', duration, title);
    }

    error(message, title = null, duration = 7000) {
        return this.show(message, 'error', duration, title);
    }

    warning(message, title = null, duration = 6000) {
        return this.show(message, 'warning', duration, title);
    }

    info(message, title = null, duration = 5000) {
        return this.show(message, 'info', duration, title);
    }
}

// Создаем глобальный экземпляр
const toastManager = new ToastManager();

// Экспортируем для использования в других скриптах
window.toastManager = toastManager;
window.showToast = (message, type, duration, title) => toastManager.show(message, type, duration, title);

// Удобные глобальные функции
window.showSuccess = (message, title, duration) => toastManager.success(message, title, duration);
window.showError = (message, title, duration) => toastManager.error(message, title, duration);
window.showWarning = (message, title, duration) => toastManager.warning(message, title, duration);
window.showInfo = (message, title, duration) => toastManager.info(message, title, duration);

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    // Преобразуем flash сообщения после полной загрузки
    setTimeout(() => {
        toastManager.convertFlashMessages();
        toastManager.showSessionToasts();
    }, 100);
});

// Добавляем метод для показа toast'ов из сессии
ToastManager.prototype.showSessionToasts = function() {
    // Проверяем, есть ли toast'ы в глобальной переменной (переданные с сервера)
    if (typeof window.sessionToasts !== 'undefined' && Array.isArray(window.sessionToasts)) {
        window.sessionToasts.forEach(toast => {
            this.show(toast.message, toast.type, 5000, toast.title);
        });
        // Очищаем после показа
        window.sessionToasts = [];
    }
}; 