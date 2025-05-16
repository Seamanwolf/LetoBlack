/**
 * Простая реализация модальных окон без зависимости от Bootstrap API
 */
class SimpleModal {
    /**
     * Создает новый экземпляр SimpleModal
     * @param {HTMLElement|string} modalElement - Элемент модального окна или его ID
     */
    constructor(modalElement) {
        if (typeof modalElement === 'string') {
            this.modal = document.getElementById(modalElement);
            if (!this.modal) {
                console.error(`Modal element with ID "${modalElement}" not found.`);
                return;
            }
        } else {
            this.modal = modalElement;
        }
        
        // Привязываем методы к текущему экземпляру
        this.show = this.show.bind(this);
        this.hide = this.hide.bind(this);
        this._handleBackdropClick = this._handleBackdropClick.bind(this);
        
        // Инициализируем обработчики событий
        this._initEventHandlers();
    }
    
    /**
     * Показывает модальное окно
     */
    show() {
        // Добавляем класс для блокировки прокрутки страницы
        document.body.classList.add('modal-open');
        
        // Создаем фон модального окна
        this.backdrop = document.createElement('div');
        this.backdrop.className = 'modal-backdrop fade show';
        document.body.appendChild(this.backdrop);
        
        // Добавляем обработчик клика по фону
        this.backdrop.addEventListener('click', this._handleBackdropClick);
        
        // Показываем модальное окно
        this.modal.style.display = 'block';
        
        // Добавляем классы для анимации
        setTimeout(() => {
            this.modal.classList.add('show');
        }, 0);
    }
    
    /**
     * Скрывает модальное окно
     */
    hide() {
        this.modal.classList.remove('show');
        
        // Ждем окончания анимации
        setTimeout(() => {
            this.modal.style.display = 'none';
            document.body.classList.remove('modal-open');
            
            // Удаляем фон
            if (this.backdrop) {
                this.backdrop.removeEventListener('click', this._handleBackdropClick);
                this.backdrop.remove();
                this.backdrop = null;
            }
        }, 150); // Длительность анимации
    }
    
    /**
     * Инициализирует обработчики событий
     * @private
     */
    _initEventHandlers() {
        // Обработка кнопок закрытия модального окна
        const closeButtons = this.modal.querySelectorAll('[data-bs-dismiss="modal"]');
        closeButtons.forEach(button => {
            button.addEventListener('click', this.hide);
        });
    }
    
    /**
     * Обработчик клика по фону модального окна
     * @private
     */
    _handleBackdropClick(event) {
        if (event.target === this.backdrop) {
            this.hide();
        }
    }
}

// Инициализация модальных окон при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Регистрируем обработчики для кнопок открытия модальных окон
    document.querySelectorAll('[data-bs-toggle="modal"]').forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            
            const targetSelector = this.getAttribute('data-bs-target');
            const modalElement = document.querySelector(targetSelector);
            
            if (modalElement) {
                const modal = new SimpleModal(modalElement);
                modal.show();
            }
        });
    });
}); 