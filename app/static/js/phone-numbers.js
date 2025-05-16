/**
 * JavaScript для страницы управления корпоративными номерами
 */

console.log('phone-numbers.js подключён');

// Добавляем базовое логирование
console.log('=== ИНИЦИАЛИЗАЦИЯ СКРИПТА PHONE-NUMBERS.JS ===');

// Функция для логирования
function log(message, type = 'info') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${type.toUpperCase()}] ${message}`;
    console.log(logMessage);
    
    // Добавляем визуальное логирование на страницу
    const logContainer = document.getElementById('logContainer') || createLogContainer();
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${type}`;
    logEntry.textContent = logMessage;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Создаем контейнер для логов, если его нет
function createLogContainer() {
    const container = document.createElement('div');
    container.id = 'logContainer';
    container.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 400px;
        height: 300px;
        background: rgba(0, 0, 0, 0.8);
        color: #fff;
        padding: 10px;
        overflow-y: auto;
        z-index: 9999;
        font-family: monospace;
        font-size: 12px;
    `;
    document.body.appendChild(container);
    return container;
}

// Стили для логов
const style = document.createElement('style');
style.textContent = `
    .log-entry {
        margin: 2px 0;
        padding: 2px 5px;
        border-radius: 3px;
    }
    .log-info { color: #fff; }
    .log-error { color: #ff6b6b; }
    .log-warn { color: #ffd93d; }
    .log-success { color: #6bff6b; }
`;
document.head.appendChild(style);

// Единая функция для управления модальными окнами
function manageModal(modalId, action = 'show', options = {}) {
    const modalElement = document.getElementById(modalId);
    if (!modalElement) {
        console.error(`Модальное окно с ID ${modalId} не найдено`);
        return;
    }

    if (action === 'show') {
        // Удаляем атрибут aria-hidden
        modalElement.removeAttribute('aria-hidden');
        
        // Показываем модальное окно
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        } else {
            modalElement.style.display = 'block';
            modalElement.classList.add('show');
            document.body.classList.add('modal-open');
            
            // Создаем фон модального окна
            const backdrop = document.createElement('div');
            backdrop.className = 'modal-backdrop fade show';
            document.body.appendChild(backdrop);
        }

        // Устанавливаем фокус на первый интерактивный элемент
        const focusableElements = modalElement.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }

        // Добавляем обработчики клавиатуры
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                manageModal(modalId, 'hide');
            } else if (e.key === 'Tab') {
                const firstFocusable = focusableElements[0];
                const lastFocusable = focusableElements[focusableElements.length - 1];

                if (e.shiftKey && document.activeElement === firstFocusable) {
                    e.preventDefault();
                    lastFocusable.focus();
                } else if (!e.shiftKey && document.activeElement === lastFocusable) {
                    e.preventDefault();
                    firstFocusable.focus();
                }
            }
        };

        modalElement.addEventListener('keydown', handleKeyDown);
        modalElement._keydownHandler = handleKeyDown;

        // Вызываем callback после показа, если он указан
        if (options.onShow) {
            options.onShow();
        }
    } else if (action === 'hide') {
        // Устанавливаем атрибут aria-hidden
        modalElement.setAttribute('aria-hidden', 'true');
        
        // Скрываем модальное окно
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
            }
        } else {
            modalElement.style.display = 'none';
            modalElement.classList.remove('show');
            document.body.classList.remove('modal-open');
            
            // Удаляем фон модального окна
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
        }

        // Удаляем обработчик клавиатуры
        if (modalElement._keydownHandler) {
            modalElement.removeEventListener('keydown', modalElement._keydownHandler);
            delete modalElement._keydownHandler;
        }

        // Вызываем callback после скрытия, если он указан
        if (options.onHide) {
            options.onHide();
        }
    }
}

// Алиасы для обратной совместимости
function showModal(modalId, options = {}) {
    manageModal(modalId, 'show', options);
    // Если открывается модальное окно свободных номеров — подгружаем их
    if (modalId === 'freeNumbersModal' && typeof loadFreeNumbers === 'function') {
        loadFreeNumbers();
    }
}

function hideModal(modalId, options = {}) {
    manageModal(modalId, 'hide', options);
}

function openModal(modalId, options = {}) {
    manageModal(modalId, 'show', options);
    // Если открывается модальное окно свободных номеров — подгружаем их
    if (modalId === 'freeNumbersModal' && typeof loadFreeNumbers === 'function') {
        loadFreeNumbers();
    }
}

// Инициализация обработчиков событий при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded');
    log('DOM полностью загружен');
    
    // Обработчики для кнопок открытия модальных окон
    document.querySelectorAll('[data-bs-toggle="modal"]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const modalId = this.getAttribute('data-bs-target').replace('#', '');
            const numberId = this.getAttribute('data-number-id');
            const phoneNumber = this.getAttribute('data-number-phone');
            
            if (numberId) {
                // Заполняем поля в модальном окне
                const modalElement = document.getElementById(modalId);
                if (modalElement) {
                    const idInput = modalElement.querySelector('[name="number_id"]');
                    if (idInput) idInput.value = numberId;
                    
                    const numberSpan = modalElement.querySelector('[data-number-span]');
                    if (numberSpan && phoneNumber) numberSpan.textContent = phoneNumber;
                }
            }
            
            showModal(modalId);
        });
    });

    // Обработчики для кнопок закрытия модальных окон
    document.querySelectorAll('[data-bs-dismiss="modal"]').forEach(button => {
        button.addEventListener('click', function() {
            const modalId = this.closest('.modal').id;
            hideModal(modalId);
        });
    });

    // Обработчики для форм в модальных окнах
    document.querySelectorAll('.modal form').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const modalId = this.closest('.modal').id;
            const formData = new FormData(this);
            const data = Object.fromEntries(formData.entries());
            
            // Определяем тип действия на основе ID модального окна
            let action = '';
            let endpoint = '';
            
            switch (modalId) {
                case 'assignNumberModal':
                    action = 'assign';
                    endpoint = '/admin/api/assign_number';
                    break;
                case 'moveNumberModal':
                    action = 'move';
                    endpoint = '/admin/api/move_number';
                    break;
                case 'deleteNumberModal':
                    action = 'delete';
                    endpoint = '/admin/api/delete_number';
                    break;
            }
            
            if (action && endpoint) {
                fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        hideModal(modalId);
                        showSuccessModal(result.message || 'Операция выполнена успешно');
                        // Обновляем данные на странице
                        if (typeof refreshPhoneNumbersData === 'function') {
                            refreshPhoneNumbersData();
                        }
                    } else {
                        showErrorModal(result.message || 'Произошла ошибка');
                    }
                })
                .catch(error => {
                    console.error('Ошибка:', error);
                    showErrorModal('Произошла ошибка при выполнении операции');
                });
            }
        });
    });
    
    // Создаем отладочную панель
    let debugPanel = document.createElement('div');
    debugPanel.className = 'debug-panel';
    debugPanel.style.cssText = `
        position: fixed;
        bottom: 0;
        right: 0;
        width: 300px;
        height: 200px;
        background-color: rgba(0, 0, 0, 0.8);
        color: lime;
        font-family: monospace;
        padding: 10px;
        overflow: auto;
        z-index: 10000;
        border: 1px solid lime;
        font-size: 12px;
    `;
    
    // Добавляем кнопки управления на панель
    debugPanel.innerHTML = `
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <h4 style="margin: 0; color: yellow;">Отладочная информация</h4>
            <div>
                <button id="debug-test-btn" style="background: green; color: white; border: none; padding: 2px 5px; margin-right: 5px; cursor: pointer;">Тест</button>
                <button id="debug-hide-btn" style="background: red; color: white; border: none; padding: 2px 5px; cursor: pointer;">x</button>
            </div>
        </div>
        <div id="debug-content"></div>
    `;
    
    document.body.appendChild(debugPanel);
    
    // Добавляем обработчики для кнопок
    document.getElementById('debug-hide-btn').addEventListener('click', function() {
        if (debugPanel.style.height === '30px') {
            debugPanel.style.height = '200px';
            this.textContent = 'x';
        } else {
            debugPanel.style.height = '30px';
            this.textContent = '+';
        }
    });
    
    // Кнопка для тестирования модальных окон и функций удаления
    document.getElementById('debug-test-btn').addEventListener('click', function() {
        log('Запуск тестирования модальных окон');
        
        // Создаем тестовую форму удаления
        const testForm = document.createElement('div');
        testForm.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border: 2px solid blue;
            z-index: 10001;
            color: black;
        `;
        
        testForm.innerHTML = `
            <h3>Тест удаления номера</h3>
            <div style="margin-bottom: 10px;">
                <label>ID номера: <input id="test-id-input" type="text" value="1"></label>
            </div>
            <div style="margin-bottom: 20px;">
                <label>Номер: <input id="test-number-input" type="text" value="+79999999999"></label>
            </div>
            <div>
                <button id="test-modal-btn" style="margin-right: 10px;">Открыть модальное окно</button>
                <button id="test-direct-delete-btn">Удалить напрямую</button>
                <button id="test-close-btn" style="margin-left: 10px; background: #f44336; color: white;">Закрыть</button>
            </div>
        `;
        
        document.body.appendChild(testForm);
        
        // Обработчики для тестовой формы
        document.getElementById('test-close-btn').addEventListener('click', function() {
            document.body.removeChild(testForm);
        });
        
        document.getElementById('test-modal-btn').addEventListener('click', function() {
            const numberId = document.getElementById('test-id-input').value;
            const phoneNumber = document.getElementById('test-number-input').value;
            
            // Заполняем поля в модальном окне
            document.getElementById('deleteNumberId').value = numberId;
            document.getElementById('deleteNumberSpan').textContent = phoneNumber;
            
            // Пробуем открыть модальное окно
            log('Тест: открываем модальное окно удаления');
            
            try {
                const modalElement = document.getElementById('deleteConfirmModal');
                
                if (!modalElement) {
                    log('ОШИБКА: Модальное окно не найдено в DOM!');
                    alert('Модальное окно не найдено!');
                    return;
                }
                
                // Пробуем показать через Bootstrap
                if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                    log('Тест: используем bootstrap.Modal');
                    const modal = new bootstrap.Modal(modalElement);
                    modal.show();
                } else {
                    // Запасной вариант через прямое управление DOM
                    log('Тест: используем прямое управление DOM');
                    modalElement.style.display = 'block';
                    modalElement.classList.add('show');
                    document.body.classList.add('modal-open');
                    
                    // Создаем фон модального окна
                    const backdrop = document.createElement('div');
                    backdrop.className = 'modal-backdrop fade show';
                    document.body.appendChild(backdrop);
                }
            } catch (error) {
                log(`ОШИБКА: ${error.message}`);
                alert(`Ошибка: ${error.message}`);
            }
        });
        
        document.getElementById('test-direct-delete-btn').addEventListener('click', function() {
            const numberId = document.getElementById('test-id-input').value;
            
            if (confirm(`Вы уверены, что хотите удалить номер с ID ${numberId}?`)) {
                log(`Тест: удаляем номер с ID ${numberId}`);
                deleteNumber(numberId);
            }
        });
    });
    
    // Функция для добавления сообщений в отладочную панель
    function debugLog(message) {
        const content = document.getElementById('debug-content');
        const time = new Date().toLocaleTimeString();
        content.innerHTML += `<div>[${time}] ${message}</div>`;
        content.scrollTop = content.scrollHeight;
        console.log(`[DEBUG] ${message}`);
    }
    
    // Сразу логируем информацию о странице
    debugLog('Страница загружена, начинаем инициализацию');
    debugLog(`Всего элементов на странице: ${document.querySelectorAll('*').length}`);
    
    // Функция для проверки наличия элементов в DOM
    function checkElement(selector, description) {
        const elements = document.querySelectorAll(selector);
        debugLog(`${description}: найдено ${elements.length} элементов`);
        return elements;
    }
    
    // Проверяем существование основных элементов
    checkElement('.delete-icon', 'Иконки удаления');
    checkElement('.fa-trash-alt', 'Иконки корзины');
    checkElement('[data-action="delete-number"]', 'Элементы с атрибутом data-action');
    checkElement('#confirmDeleteBtn', 'Кнопка подтверждения удаления');
    checkElement('#deleteConfirmModal', 'Модальное окно подтверждения удаления');
    
    // Проверка существующего JavaScript
    debugLog(`SimpleModal ${typeof SimpleModal !== 'undefined' ? 'определен' : 'НЕ определен'}`);
    debugLog(`bootstrap ${typeof bootstrap !== 'undefined' ? 'определен' : 'НЕ определен'}`);
    
    // Проверяем, что SimpleModal определен
    if (typeof SimpleModal === 'undefined') {
        console.error('SimpleModal не определен. Проверьте порядок загрузки скриптов на странице.');
        
        // Определяем простую замену для SimpleModal если он не загружен
        window.SimpleModal = class SimpleModalFallback {
            constructor(modalId) {
                this.modalId = modalId;
                this.modalElement = document.getElementById(modalId);
            }
            
            show() {
                console.log(`Показываем модальное окно ${this.modalId}`);
                if (this.modalElement) {
                    this.modalElement.style.display = 'block';
                    this.modalElement.classList.add('show');
                    document.body.classList.add('modal-open');
                } else {
                    alert('Модальное окно не найдено. Используем стандартный alert.');
                }
            }
            
            hide() {
                console.log(`Скрываем модальное окно ${this.modalId}`);
                if (this.modalElement) {
                    this.modalElement.style.display = 'none';
                    this.modalElement.classList.remove('show');
                    document.body.classList.remove('modal-open');
                }
            }
        };
        
        console.log('Создан временный класс SimpleModal для обеспечения работы скрипта.');
    }
    
    // Обработчик кнопки добавления номера
    document.getElementById('submitAddNumberForm').addEventListener('click', function() {
        const phoneNumberInput = document.getElementById('phoneNumberInput');
        let phoneNumber = phoneNumberInput.value.trim();
        const department = document.getElementById('departmentSelect').value;
        
        // Проверка обязательных полей
        if (!phoneNumber) {
            const modal = new SimpleModal('validationErrorModal');
            document.getElementById('validationErrorMessage').textContent = 'Пожалуйста, введите номер телефона';
            modal.show();
            return;
        }
        
        if (!department) {
            const modal = new SimpleModal('validationErrorModal');
            document.getElementById('validationErrorMessage').textContent = 'Пожалуйста, выберите отдел';
            modal.show();
            return;
        }
        
        // Исправляем префикс, если нужно
        const fullNumber = fixPhoneNumberPrefix(phoneNumber);
        
        console.log('Отправка данных:', { fullNumber, department });
        
        fetch('/admin/api/add_number', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone_number: fullNumber,
                department: department,
                additional_numbers: []
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Закрываем модальное окно
                const modal = new SimpleModal('addNumberModal');
                modal.hide();
                
                // Показываем сообщение об успехе
                const successModal = new SimpleModal('successModal');
                document.getElementById('successMessage').textContent = 'Номер успешно добавлен';
                successModal.show();
                
                // Устанавливаем таймер для перезагрузки страницы
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                // Показываем сообщение об ошибке
                const errorModal = new SimpleModal('errorModal');
                document.getElementById('errorMessage').textContent = data.message || 'Ошибка при добавлении номера';
                errorModal.show();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Показываем сообщение об ошибке
            const errorModal = new SimpleModal('errorModal');
            document.getElementById('errorMessage').textContent = 'Произошла ошибка при добавлении номера';
            errorModal.show();
        });
    });
    
    // Обработчик кнопки добавления дополнительного номера
    document.getElementById('addAdditionalNumberButton').addEventListener('click', function() {
        const additionalNumberInput = document.getElementById('addAdditionalNumberInput');
        const additionalNumber = additionalNumberInput.value.trim();
        
        if (!additionalNumber) {
            const modal = new SimpleModal('validationErrorModal');
            document.getElementById('validationErrorMessage').textContent = 'Пожалуйста, введите дополнительный номер';
            modal.show();
            return;
        }
        
        // Получаем значение отдела из основного селекта
        const department = document.getElementById('departmentSelect').value;
        if (!department) {
            const modal = new SimpleModal('validationErrorModal');
            document.getElementById('validationErrorMessage').textContent = 'Пожалуйста, выберите отдел для дополнительного номера';
            modal.show();
            return;
        }
        
        // Исправляем префикс, если нужно
        const fullNumber = fixPhoneNumberPrefix(additionalNumber);
        
        // Отправляем запрос на добавление дополнительного номера как отдельного
        fetch('/admin/api/add_number', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone_number: fullNumber,
                department: department,
                additional_numbers: []
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Очищаем поле ввода
                additionalNumberInput.value = '';
                
                // Показываем сообщение об успехе
                const successModal = new SimpleModal('successModal');
                document.getElementById('successMessage').textContent = 'Дополнительный номер успешно добавлен как свободный';
                successModal.show();
            } else {
                // Показываем сообщение об ошибке
                const errorModal = new SimpleModal('errorModal');
                document.getElementById('errorMessage').textContent = data.message || 'Ошибка при добавлении дополнительного номера';
                errorModal.show();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Показываем сообщение об ошибке
            const errorModal = new SimpleModal('errorModal');
            document.getElementById('errorMessage').textContent = 'Произошла ошибка при добавлении дополнительного номера';
            errorModal.show();
        });
    });
    
    // Полностью заменяем обработчик удаления на прямой подход
    console.log('Добавление прямых обработчиков на кнопки удаления');
    
    // Специальная функция для добавления обработчиков на кнопки удаления
    function addDeleteHandlers() {
        const deleteButtons = document.querySelectorAll('.delete-icon, .fa-trash-alt, [data-action="delete-number"]');
        debugLog(`Найдено ${deleteButtons.length} кнопок удаления для добавления обработчиков`);
        
        if (deleteButtons.length === 0) {
            // Если кнопок не найдено, выводим предупреждение
            alert('ВНИМАНИЕ: Кнопки удаления не найдены на странице!');
            debugLog('ОШИБКА: Кнопки удаления не найдены!');
            
            // Дополнительная проверка - ищем элементы в HTML, которые могут быть кнопками удаления
            const possibleDeleteButtons = Array.from(document.querySelectorAll('i')).filter(el => 
                el.className.includes('trash') || 
                el.className.includes('delete') || 
                el.getAttribute('title')?.toLowerCase().includes('удал')
            );
            
            debugLog(`Найдено ${possibleDeleteButtons.length} возможных кнопок удаления`);
            
            possibleDeleteButtons.forEach((btn, i) => {
                debugLog(`Возможная кнопка ${i+1}: class="${btn.className}", title="${btn.getAttribute('title') || 'нет'}"`);
                
                // Принудительно добавляем необходимые классы и атрибуты
                btn.classList.add('delete-icon');
                btn.setAttribute('data-action', 'delete-number');
                
                const tr = btn.closest('tr');
                if (tr) {
                    const id = tr.getAttribute('data-number-id');
                    debugLog(`ID из строки: ${id || 'не найден'}`);
                    if (id) btn.setAttribute('data-number-id', id);
                }
            });
            
            // Пробуем снова найти кнопки после корректировки
            const fixedButtons = document.querySelectorAll('.delete-icon, .fa-trash-alt, [data-action="delete-number"]');
            debugLog(`После корректировки найдено ${fixedButtons.length} кнопок удаления`);
            
            if (fixedButtons.length > 0) {
                deleteButtons = fixedButtons;
            }
        }
        
        deleteButtons.forEach((button, index) => {
            // Добавляем дополнительный атрибут для лучшего распознавания
            button.setAttribute('data-action', 'delete-number');
            
            // Делаем кнопку более заметной для отладки
            button.style.border = '2px solid red';
            button.style.padding = '3px';
            button.style.backgroundColor = 'lightyellow';
            
            // Выводим информацию о кнопке
            debugLog(`Кнопка ${index+1}: ID=${button.getAttribute('data-number-id') || 'нет'}, title="${button.getAttribute('title') || 'нет'}"`);
            
            // Удаляем старые обработчики, если они есть
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            // Добавляем новый обработчик
            newButton.addEventListener('click', function(event) {
                debugLog(`КЛИК по кнопке удаления ${index+1}`);
                alert(`Кнопка удаления нажата! ID: ${this.getAttribute('data-number-id')}`);
                
                event.preventDefault();
                event.stopPropagation(); // Останавливаем всплытие
                
                const numberId = this.getAttribute('data-number-id');
                const row = this.closest('tr');
                if (!row || !numberId) {
                    const errorMsg = `Не удалось получить ID номера или найти строку таблицы: ID=${numberId}, row=${row ? 'найдена' : 'НЕ найдена'}`;
                    debugLog('ОШИБКА: ' + errorMsg);
                    alert(errorMsg);
                    return;
                }
                
                const phoneNumber = row.querySelector('td:nth-child(2)')?.textContent || 'неизвестно';
                debugLog(`Удаление номера: ID=${numberId}, номер=${phoneNumber}`);
                
                // Заполняем поля в модальном окне
                const idInput = document.getElementById('deleteNumberId');
                const numberSpan = document.getElementById('deleteNumberSpan');
                
                if (!idInput || !numberSpan) {
                    const errorMsg = `Элементы модального окна не найдены: idInput=${idInput ? 'найден' : 'НЕ найден'}, numberSpan=${numberSpan ? 'найден' : 'НЕ найден'}`;
                    debugLog('ОШИБКА: ' + errorMsg);
                    alert(errorMsg);
                    return;
                }
                
                idInput.value = numberId;
                numberSpan.textContent = phoneNumber;
                
                // Пробуем открыть модальное окно разными способами
                debugLog('Пытаемся открыть модальное окно подтверждения');
                
                try {
                    if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        debugLog('Открываем через bootstrap.Modal');
                        const modalElement = document.getElementById('deleteConfirmModal');
                        const modal = new bootstrap.Modal(modalElement);
                        modal.show();
                    } else {
                        debugLog('bootstrap.Modal недоступен, пробуем через showModal');
                        showModal('deleteConfirmModal');
                    }
                    
                    // Также пробуем прямое управление стилями как запасной вариант
                    const modalElement = document.getElementById('deleteConfirmModal');
                    if (modalElement) {
                        debugLog('Дополнительное управление стилями модального окна');
                        modalElement.style.display = 'block';
                        modalElement.classList.add('show');
                        document.body.classList.add('modal-open');
                    }
                } catch (error) {
                    const errorMsg = `Ошибка при открытии модального окна: ${error.message}`;
                    debugLog('ОШИБКА: ' + errorMsg);
                    alert(errorMsg);
                    
                    // Крайний случай - используем нативный confirm
                    if (confirm(`Вы действительно хотите удалить номер ${phoneNumber}?`)) {
                        debugLog('Пользователь подтвердил удаление через нативный confirm');
                        deleteNumber(numberId);
                    }
                }
            });
        });
    }
    
    // Функция для выполнения удаления номера
    function deleteNumber(numberId) {
        // Добавляем вывод в консоль для отладки
        alert(`Попытка удаления номера с ID: ${numberId}`);
        console.group('Удаление номера');
        console.log('ID номера:', numberId);
            
            if (!numberId) {
            console.error('ID номера не указан');
            alert('ID номера не указан');
            console.groupEnd();
                return;
            }
            
        console.log('Отправляем запрос на сервер...');

        // Пробуем разные URL для удаления (на всякий случай)
        const urls = [
            '/admin/api/delete_number',
            '/api/delete_number',
            '/delete_number'
        ];
        
        let currentUrlIndex = 0;
        
        function tryNextUrl() {
            if (currentUrlIndex >= urls.length) {
                console.error('Все URL-адреса испробованы, удаление не удалось');
                alert('Не удалось удалить номер. Все варианты API испробованы.');
                console.groupEnd();
                return;
            }
            
            const url = urls[currentUrlIndex];
            console.log(`Попытка ${currentUrlIndex + 1}/${urls.length}: ${url}`);
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ number_id: numberId })
            })
            .then(response => {
                console.log(`Получен ответ от ${url}:`, response.status);
                
                if (!response.ok && currentUrlIndex < urls.length - 1) {
                    // Если ответ не успешный и есть еще URL для попытки
                    console.warn(`URL ${url} не сработал, переход к следующему`);
                    currentUrlIndex++;
                    tryNextUrl();
                    return null; // Прерываем текущую цепочку then
                }
                
                // Вывод текста ответа для отладки
                response.clone().text().then(text => {
                    console.log('Текст ответа:', text);
                });
                
                return response.json().catch(err => {
                    console.error('Ошибка парсинга JSON:', err);
                    return { success: false, message: 'Ошибка формата ответа сервера' };
                });
            })
            .then(data => {
                if (!data) return; // Пропускаем, если перешли к следующему URL
                
                console.log('Обработанный ответ от сервера:', data);
                
                if (data.success) {
                    console.log('Операция успешна, обновляем UI');
                    alert('Номер успешно удален');
                    
                    // Закрываем модальное окно
                    const modalElement = document.getElementById('deleteNumberModal');
            if (modalElement) {
                        try {
                            const modal = bootstrap.Modal.getInstance(modalElement);
                            if (modal) {
                                modal.hide();
                    } else {
                                console.warn('Не удалось получить экземпляр modal');
                                modalElement.classList.remove('show');
                                modalElement.style.display = 'none';
                                document.body.classList.remove('modal-open');
                                const backdrop = document.querySelector('.modal-backdrop');
                                if (backdrop) backdrop.remove();
                    }
                } catch (error) {
                            console.error('Ошибка при закрытии модального окна:', error);
                            // Принудительное закрытие
                            modalElement.classList.remove('show');
                            modalElement.style.display = 'none';
                            document.body.classList.remove('modal-open');
                            const backdrop = document.querySelector('.modal-backdrop');
                            if (backdrop) backdrop.remove();
                    }
                } else {
                        console.warn('Модальное окно не найдено');
                    }
                    
                    // Отладочная информация о DOM
                    console.group('Отладка DOM');
                    console.log('Все строки таблицы:', document.querySelectorAll('tr').length);
                    console.log('Строки с data-number-id:', document.querySelectorAll('tr[data-number-id]').length);
                    document.querySelectorAll('tr[data-number-id]').forEach((row, idx) => {
                        console.log(`Строка ${idx+1}, ID: ${row.getAttribute('data-number-id')}`);
                    });
                    console.groupEnd();
                    
                    // Удаляем строку из таблицы
                    const row = document.querySelector(`tr[data-number-id="${numberId}"]`);
                    if (row) {
                        console.log('Удаляем строку из таблицы');
                        row.remove();
                        
                        // Обновляем счетчик номеров
                        updateNumbersCount();
                        } else {
                        console.warn('Строка для удаления не найдена');
                    }
                    
                    // ВАЖНО: Принудительно перезагружаем страницу после успешного удаления
                    // Это гарантирует, что данные будут актуальны
                    console.log("Планируем перезагрузку страницы через 1 секунду");
                setTimeout(function() {
                        console.log("Перезагружаем страницу...");
                        window.location.reload();
    }, 1000);
                } else {
                    console.error('Ошибка в ответе:', data.message);
                    alert('Ошибка при удалении: ' + (data.message || 'неизвестная ошибка'));
                    
                    // Если есть еще URL для попытки
                    if (currentUrlIndex < urls.length - 1) {
                        if (confirm('Пробовать другой адрес API?')) {
                            currentUrlIndex++;
                            tryNextUrl();
                        }
                    }
                }
                
                console.groupEnd();
            })
            .catch(error => {
                console.error('Ошибка при запросе:', error);
                
                // Если есть еще URL для попытки
                if (currentUrlIndex < urls.length - 1) {
                    console.warn('Ошибка при использовании URL ' + url + ', переход к следующему');
                    currentUrlIndex++;
                    tryNextUrl();
                } else {
                    alert('Произошла ошибка: ' + error.message);
                    console.groupEnd();
                }
            });
        }
        
        // Начинаем с первого URL
        tryNextUrl();
    }

    // Рекурсивная функция для тестирования URL по очереди
    function testNextUrlForFree(urls, index, requestData, resultsDiv) {
        if (index >= urls.length) {
            resultsDiv.innerHTML += `❌ Все URL протестированы, ни один не сработал успешно.\n`;
            return;
        }
        
        const url = urls[index];
        resultsDiv.innerHTML += `🔄 Тест URL #${index + 1}: ${url}\n`;
        
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            resultsDiv.innerHTML += `📥 Ответ от ${url}: статус ${response.status}\n`;
            return response.json();
        })
        .then(data => {
            resultsDiv.innerHTML += `📄 Данные ответа: ${JSON.stringify(data)}\n`;
            
            if (data.success) {
                resultsDiv.innerHTML += `✅ УСПЕХ! URL ${url} успешно обработал запрос.\n`;
            } else {
                resultsDiv.innerHTML += `⚠️ Ошибка в ответе: ${data.message || 'Не указана'}\n`;
                // Пробуем следующий URL
                testNextUrlForFree(urls, index + 1, requestData, resultsDiv);
            }
        })
        .catch(error => {
            resultsDiv.innerHTML += `❌ Ошибка запроса: ${error.message}\n`;
            // Пробуем следующий URL
            testNextUrlForFree(urls, index + 1, requestData, resultsDiv);
        });
    }

    // Функция для тестирования перемещения номера в свободные
    function testMoveToFreeApi(numberId) {
        const resultsDiv = document.getElementById('diag-results');
        resultsDiv.innerHTML = `📋 Начинаем тестирование перемещения номера ID: ${numberId} в свободные\n`;
        
        // Создаем несколько вариантов данных для тестирования разных форматов API
        const requestDataVariants = [
            {
                number_id: numberId,
                new_department: 'свободные',
                is_free_numbers: true
            },
            {
                number_id: numberId,
                new_department: null,
                is_free_numbers: true
            },
            {
                number_id: numberId,
                new_department: 'свободные',
                to_free: true
            }
        ];
        
        // Определяем массив URL для тестирования
        const urls = [
            '/admin/api/move_number',
            '/api/move_number',
            '/admin/move_number'
        ];
        
        // Тестируем каждый вариант данных с каждым URL
        testMoveVariants(urls, requestDataVariants, 0, 0, resultsDiv);
    }

    // Рекурсивная функция для тестирования комбинаций URL и данных
    function testMoveVariants(urls, dataVariants, urlIndex, dataIndex, resultsDiv) {
        if (dataIndex >= dataVariants.length) {
            // Все варианты данных проверены для текущего URL, переходим к следующему URL
            testMoveVariants(urls, dataVariants, urlIndex + 1, 0, resultsDiv);
            return;
        }
        
        if (urlIndex >= urls.length) {
            // Все URL проверены
            resultsDiv.innerHTML += `❌ Все комбинации протестированы, ни одна не сработала успешно.\n`;
            return;
        }
        
        const url = urls[urlIndex];
        const requestData = dataVariants[dataIndex];
        
        resultsDiv.innerHTML += `🔄 Тест URL #${urlIndex + 1} (${url}) с вариантом данных #${dataIndex + 1}\n`;
        resultsDiv.innerHTML += `📤 Отправляемые данные: ${JSON.stringify(requestData)}\n`;
        
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            resultsDiv.innerHTML += `📥 Ответ от ${url}: статус ${response.status}\n`;
            return response.json();
        })
        .then(data => {
            resultsDiv.innerHTML += `📄 Данные ответа: ${JSON.stringify(data)}\n`;
            
            if (data.success) {
                resultsDiv.innerHTML += `✅ УСПЕХ! URL ${url} с вариантом #${dataIndex + 1} успешно обработал запрос.\n`;
            } else {
                resultsDiv.innerHTML += `⚠️ Ошибка в ответе: ${data.message || 'Не указана'}\n`;
                // Пробуем следующий вариант данных для текущего URL
                testMoveVariants(urls, dataVariants, urlIndex, dataIndex + 1, resultsDiv);
            }
        })
        .catch(error => {
            resultsDiv.innerHTML += `❌ Ошибка запроса: ${error.message}\n`;
            // Пробуем следующий вариант данных для текущего URL
            testMoveVariants(urls, dataVariants, urlIndex, dataIndex + 1, resultsDiv);
        });
    }

    // Функция для тестирования перемещения номера между отделами
    function testMoveBetweenDepts(numberId) {
        const resultsDiv = document.getElementById('diag-results');
        resultsDiv.innerHTML = `📋 Начинаем тестирование перемещения номера ID: ${numberId} между отделами\n`;
        
        // Запрашиваем список отделов для тестирования
        fetch('/admin/api/get_departments')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.departments && data.departments.length > 0) {
                    const departments = data.departments;
                    resultsDiv.innerHTML += `📋 Получено ${departments.length} отделов для тестирования\n`;
                    
                    // Берем первый отдел для теста
                    const testDept = departments[0].id || departments[0].name || departments[0];
                    
                    // Создаем данные для перемещения
                    const requestData = {
                        number_id: numberId,
                        new_department: testDept
                    };
                    
                    resultsDiv.innerHTML += `📤 Отправляемые данные: ${JSON.stringify(requestData)}\n`;
                    
                    // Определяем массив URL для тестирования
                    const urls = [
                        '/admin/api/move_number',
                        '/api/move_number',
                        '/admin/move_number'
                    ];
                    
                    // Тестируем перемещение
                    testNextUrlForMove(urls, 0, requestData, resultsDiv);
                } else {
                    resultsDiv.innerHTML += `❌ Не удалось получить список отделов: ${JSON.stringify(data)}\n`;
                }
            })
            .catch(error => {
                resultsDiv.innerHTML += `❌ Ошибка при получении списка отделов: ${error.message}\n`;
                
                // Используем фиктивный отдел для теста
                const requestData = {
                    number_id: numberId,
                    new_department: 'Тестовый отдел'
                };
                
                resultsDiv.innerHTML += `📤 Отправляемые данные (с фиктивным отделом): ${JSON.stringify(requestData)}\n`;
                
                // Определяем массив URL для тестирования
                const urls = [
                    '/admin/api/move_number',
                    '/api/move_number',
                    '/admin/move_number'
                ];
                
                // Тестируем перемещение
                testNextUrlForMove(urls, 0, requestData, resultsDiv);
            });
    }

    // Рекурсивная функция для тестирования URL для перемещения
    function testNextUrlForMove(urls, index, requestData, resultsDiv) {
        if (index >= urls.length) {
            resultsDiv.innerHTML += `❌ Все URL протестированы, ни один не сработал успешно.\n`;
            return;
        }
        
        const url = urls[index];
        resultsDiv.innerHTML += `🔄 Тест URL #${index + 1}: ${url}\n`;
        
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            resultsDiv.innerHTML += `📥 Ответ от ${url}: статус ${response.status}\n`;
            return response.json();
        })
        .then(data => {
            resultsDiv.innerHTML += `📄 Данные ответа: ${JSON.stringify(data)}\n`;
            
            if (data.success) {
                resultsDiv.innerHTML += `✅ УСПЕХ! URL ${url} успешно обработал запрос.\n`;
            } else {
                resultsDiv.innerHTML += `⚠️ Ошибка в ответе: ${data.message || 'Не указана'}\n`;
                // Пробуем следующий URL
                testNextUrlForMove(urls, index + 1, requestData, resultsDiv);
            }
        })
        .catch(error => {
            resultsDiv.innerHTML += `❌ Ошибка запроса: ${error.message}\n`;
            // Пробуем следующий URL
            testNextUrlForMove(urls, index + 1, requestData, resultsDiv);
        });
    }

    // Добавляем вызов функции для создания кнопки диагностики после загрузки DOM
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(addDiagnosticButton, 1500);
    });

    // === Новый обработчик для showFreeNumbersBtn с логированием ===
    const freeBtn = document.getElementById('showFreeNumbersBtn');
    console.log('[Диагностика] freeBtn:', freeBtn);
    if (!freeBtn) {
        alert('[Свободные номера] Кнопка showFreeNumbersBtn не найдена в DOM!');
        console.error('[Свободные номера] Кнопка showFreeNumbersBtn не найдена в DOM!');
        return;
    }
    freeBtn.addEventListener('click', function(e) {
        alert('Клик по кнопке "Свободные номера"!');
        e.preventDefault();
        if (typeof loadFreeNumbers === 'function') {
            console.log('[Свободные номера] Вызываем loadFreeNumbers()');
            loadFreeNumbers();
        } else {
            console.error('[Свободные номера] Функция loadFreeNumbers не определена!');
        }
        var modalEl = document.getElementById('freeNumbersModal');
        if (!modalEl) {
            console.error('[Свободные номера] Модальное окно freeNumbersModal не найдено!');
            alert('Модальное окно "Свободные номера" не найдено!');
            return;
        }
        if (window.bootstrap && bootstrap.Modal) {
            console.log('[Свободные номера] Открываем через bootstrap.Modal');
            var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        } else if (typeof showModal === 'function') {
            console.log('[Свободные номера] Открываем через showModal');
            showModal('freeNumbersModal');
        } else {
            console.log('[Свободные номера] Открываем через прямое управление стилями');
            modalEl.style.display = 'block';
            modalEl.classList.add('show');
            document.body.classList.add('modal-open');
        }
    });

    // ... существующий код ...
    console.log('phone-numbers.js стартовал');

    // ... существующий код ...
});

// ... существующий код ...

// Функция для перемещения номера между отделами
function moveNumber(numberId, newDepartment) {
// Функция для управления фокусом в модальном окне
function manageModalFocus(modalElement) {
    const focusableElements = modalElement.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstFocusableElement = focusableElements[0];
    const lastFocusableElement = focusableElements[focusableElements.length - 1];
    let previousActiveElement = document.activeElement;

    // Функция для обработки клавиши Tab
    function handleTabKey(e) {
        if (e.key === 'Tab') {
            if (e.shiftKey) {
                if (document.activeElement === firstFocusableElement) {
                    e.preventDefault();
                    lastFocusableElement.focus();
                }
            } else {
                if (document.activeElement === lastFocusableElement) {
                    e.preventDefault();
                    firstFocusableElement.focus();
                }
            }
        }
    }

    // Функция для обработки клавиши Escape
    function handleEscapeKey(e) {
        if (e.key === 'Escape') {
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
            }
        }
    }

    // Добавляем обработчики событий
    modalElement.addEventListener('keydown', handleTabKey);
    modalElement.addEventListener('keydown', handleEscapeKey);

    // Фокусируемся на первом элементе при открытии
    firstFocusableElement.focus();

    // Возвращаем функцию для очистки обработчиков
    return function cleanup() {
        modalElement.removeEventListener('keydown', handleTabKey);
        modalElement.removeEventListener('keydown', handleEscapeKey);
        previousActiveElement.focus();
    };
}

// ... существующий код ...

// Обработчики для модальных окон
document.addEventListener('DOMContentLoaded', function() {
    // Обработчик для кнопки назначения номера
    document.getElementById('confirmAssignBtn')?.addEventListener('click', function() {
        const numberId = document.getElementById('assignNumberSelect').value;
        const department = document.getElementById('assignDepartmentSelect').value;
        
        if (!numberId || !department) {
            showErrorModal('Пожалуйста, выберите номер и отдел');
            return;
        }
        
        // Отправляем запрос на сервер
        fetch('/admin/api/assign_number', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                number_id: numberId,
                department: department
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                hideModal('assignNumberModal');
                showSuccessModal(data.message || 'Номер успешно назначен');
                refreshPhoneNumbersData();
            } else {
                showErrorModal(data.message || 'Ошибка при назначении номера');
            }
        })
        .catch(error => {
            console.error('Ошибка при назначении номера:', error);
            showErrorModal('Ошибка при назначении номера');
        });
    });

    // Обработчик для кнопки перемещения номера
    document.getElementById('confirmMoveBtn')?.addEventListener('click', function() {
        const numberId = document.getElementById('moveNumberId').value;
        const newDepartment = document.getElementById('moveDepartmentSelect').value;
        
        if (!numberId || !newDepartment) {
            showErrorModal('Пожалуйста, выберите новый отдел');
            return;
        }
        
        // Отправляем запрос на сервер
        fetch('/admin/api/move_number', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
            number_id: numberId,
                new_department: newDepartment
            })
        })
        .then(response => response.json())
            .then(data => {
                if (data.success) {
                    hideModal('moveNumberModal');
                showSuccessModal(data.message || 'Номер успешно перемещен');
                refreshPhoneNumbersData();
                } else {
                    showErrorModal(data.message || 'Ошибка при перемещении номера');
                }
            })
            .catch(error => {
            console.error('Ошибка при перемещении номера:', error);
            showErrorModal('Ошибка при перемещении номера');
            });
    });
    
    // Обработчик для кнопки подтверждения удаления
    document.getElementById('confirmDeleteBtn')?.addEventListener('click', function() {
        const numberId = document.getElementById('deleteNumberId').value;
        
        if (!numberId) {
            showErrorModal('ID номера не указан');
            return;
        }
        
        // Отправляем запрос на сервер
        fetch('/admin/api/delete_number', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                number_id: numberId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                hideModal('deleteNumberModal');
                showSuccessModal(data.message || 'Номер успешно удален');
                refreshPhoneNumbersData();
            } else {
                showErrorModal(data.message || 'Ошибка при удалении номера');
            }
        })
        .catch(error => {
            console.error('Ошибка при удалении номера:', error);
            showErrorModal('Ошибка при удалении номера');
        });
    });

    // Обработчики для кнопок открытия модальных окон
    document.querySelectorAll('[data-action="assign-number"]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const numberId = this.dataset.numberId;
            
            // Заполняем поля в модальном окне
            document.getElementById('assignNumberSelect').value = numberId;
            
            // Показываем модальное окно
            showModal('assignNumberModal');
        });
    });

    document.querySelectorAll('[data-action="move-number"]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const numberId = this.dataset.numberId;
            
            // Заполняем поля в модальном окне
            document.getElementById('moveNumberId').value = numberId;
            
            // Показываем модальное окно
            showModal('moveNumberModal');
        });
    });

    document.querySelectorAll('[data-action="delete-number"]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const numberId = this.dataset.numberId;
            const phoneNumber = this.dataset.phoneNumber;
            
            // Заполняем поля в модальном окне
            document.getElementById('deleteNumberId').value = numberId;
            document.getElementById('deleteNumberSpan').textContent = phoneNumber;
            
            // Показываем модальное окно
            showModal('deleteNumberModal');
        });
    });
});

// ... существующий код ...

function updateNumbersCount() {
    const visibleRows = document.querySelectorAll('#numbers-entries tr:not([style*="display: none"])');
    const countElement = document.querySelector('.entry-count');
    if (countElement) {
        countElement.textContent = `Всего номеров: ${visibleRows.length}`;
    }
}

// Делаем функцию deleteNumber доступной глобально
window.deleteNumber = deleteNumber;

window.deleteNumberDirect = function(numberId) {
    console.group('Прямое удаление номера');
    console.log('ID номера:', numberId);
    
    if (!numberId) {
        console.error('ID номера не указан');
        alert('ID номера не указан');
        console.groupEnd();
        return;
    }

    console.log('Отправляем запрос на сервер...');

    // Массив URL для тестирования
    const urls = [
        '/admin/api/delete_number',
        '/api/delete_number',
        '/delete_number',
        '/admin/delete_number'
    ];
    
    let currentUrlIndex = 0;
    
    function tryNextUrl() {
        if (currentUrlIndex >= urls.length) {
            console.error('Все URL-адреса испробованы, удаление не удалось');
            alert('Не удалось удалить номер. Все варианты API испробованы.');
            console.groupEnd();
            return;
        }
        
        const url = urls[currentUrlIndex];
        console.log(`Попытка ${currentUrlIndex + 1}/${urls.length}: ${url}`);
        
        fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
            body: JSON.stringify({ number_id: numberId })
        })
        .then(response => {
            console.log(`Получен ответ от ${url}:`, response.status);
            
            if (!response.ok && currentUrlIndex < urls.length - 1) {
                // Если ответ не успешный и есть еще URL для попытки
                console.warn(`URL ${url} не сработал, переход к следующему`);
                currentUrlIndex++;
                tryNextUrl();
                return null; // Прерываем текущую цепочку then
            }
            
            // Вывод текста ответа для отладки
            response.clone().text().then(text => {
                console.log('Текст ответа:', text);
            });
            
            return response.json().catch(err => {
                console.error('Ошибка парсинга JSON:', err);
                return { success: false, message: 'Ошибка формата ответа сервера' };
            });
        })
        .then(data => {
            if (!data) return; // Пропускаем, если перешли к следующему URL
            
            console.log('Обработанный ответ от сервера:', data);
            
            if (data.success) {
                console.log('Операция успешна, перезагружаем страницу');
                alert(`Номер успешно удален через ${url}`);
                location.reload();
            } else {
                console.error('Ошибка в ответе:', data.message);
                
                // Если есть еще URL для попытки
                if (currentUrlIndex < urls.length - 1) {
                    console.log('Пробуем следующий URL...');
                    currentUrlIndex++;
                    tryNextUrl();
                } else {
                    alert('Ошибка при удалении: ' + (data.message || 'неизвестная ошибка'));
                }
            }
        })
        .catch(error => {
            console.error('Ошибка при запросе:', error);
            
            // Если есть еще URL для попытки
            if (currentUrlIndex < urls.length - 1) {
                console.warn('Ошибка при использовании URL ' + url + ', переход к следующему');
                currentUrlIndex++;
                tryNextUrl();
            } else {
                alert('Произошла ошибка: ' + error.message);
                console.groupEnd();
            }
        });
    }
    // Начинаем с первого URL
    tryNextUrl();
}

function sortEmployeesInDepartments() {
    const departmentSections = document.querySelectorAll('.department-section');
    
    departmentSections.forEach(section => {
        const tbody = section.querySelector('tbody');
        if (!tbody) return;
        
        const rows = Array.from(tbody.querySelectorAll('tr.employee-row'));
        if (rows.length <= 1) return;
        
        // Сортируем строки: сначала руководители отдела (по должности), потом заместители, потом обычные сотрудники
        rows.sort((a, b) => {
            const aPosition = a.cells[3].textContent.trim();
            const bPosition = b.cells[3].textContent.trim();
            const aIsManager = aPosition === 'Руководитель отдела';
            const bIsManager = bPosition === 'Руководитель отдела';
            if (aIsManager && !bIsManager) return -1;
            if (!aIsManager && bIsManager) return 1;
            const aIsDeputy = a.classList.contains('deputy-row');
            const bIsDeputy = b.classList.contains('deputy-row');
            if (aIsDeputy && !bIsDeputy) return -1;
            if (!aIsDeputy && bIsDeputy) return 1;
            // Если оба имеют одинаковую роль, сортируем по имени
            const aName = a.cells[2].textContent;
            const bName = b.cells[2].textContent;
            return aName.localeCompare(bName);
        });
        
        // Очищаем tbody и добавляем отсортированные строки
        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
    });
}
}

// ... существующий код ...