// Функция обновления данных сотрудника
async function updateEmployee() {
    const form = document.getElementById('editEmployeeForm');
    const formData = new FormData(form);
    
    // Преобразуем FormData в объект
    const data = {};
    formData.forEach((value, key) => {
        data[key] = value;
    });
    
    try {
        const response = await fetch('/admin/api/update_employee', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Данные сотрудника успешно обновлены', 'success');
            // Закрываем модальное окно
            const modal = bootstrap.Modal.getInstance(document.getElementById('editEmployeeModal'));
            modal.hide();
            // Перезагружаем страницу для отображения обновленных данных
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            showNotification(result.message || 'Ошибка при обновлении данных сотрудника', 'danger');
        }
    } catch (error) {
        console.error('Ошибка при обновлении данных сотрудника:', error);
        showNotification('Ошибка при обновлении данных сотрудника', 'danger');
    }
} 

function loadEmployeeHistory(employeeId) {
    console.log('Загрузка истории изменений для сотрудника:', employeeId);
    
    // Проверяем, что jQuery загружен
    if (typeof $ === 'undefined') {
        console.error('jQuery не загружен! Невозможно выполнить запрос истории.');
        return;
    }
    
    // Используем правильный маршрут для получения истории с префиксом /admin
    const apiUrl = `/admin/employee_history/${employeeId}`;
    console.log('URL запроса истории:', apiUrl);
    
    // Добавляем случайный параметр для предотвращения кэширования
    const timestamp = new Date().getTime();
    const noCacheUrl = apiUrl + '?_=' + timestamp;
    console.log('URL запроса с антикэшем:', noCacheUrl);
    
    $.ajax({
        url: noCacheUrl,
        type: 'GET',
        cache: false,
        success: function(response) {
            console.log('Получен ответ от сервера истории:', response);
            if (response.success) {
                const tbody = $('#historyTable tbody');
                tbody.empty();
                
                if (response.history && response.history.length > 0) {
                    console.log('Получено ' + response.history.length + ' записей истории');
                    response.history.forEach(function(record) {
                        console.log('Обработка записи истории:', record);
                        const row = $('<tr>');
                        row.append($('<td>').text(record.changed_at));
                        row.append($('<td>').text(record.field_name));
                        row.append($('<td>').text(record.old_value || '-'));
                        row.append($('<td>').text(record.new_value || '-'));
                        row.append($('<td>').text(record.changed_by_name || 'Система'));
                        tbody.append(row);
                    });
                } else {
                    console.log('История изменений пуста');
                    tbody.html('<tr><td colspan="5" class="text-center">История изменений отсутствует</td></tr>');
                }
            } else {
                console.error('Ошибка при загрузке истории:', response.message);
                $('#historyTable tbody').html('<tr><td colspan="5" class="text-center text-danger">Ошибка при загрузке истории</td></tr>');
            }
        },
        error: function(xhr, status, error) {
            console.error('Ошибка при загрузке истории:', error);
            console.error('Статус запроса:', status);
            console.error('XHR:', xhr.responseText);
            $('#historyTable tbody').html('<tr><td colspan="5" class="text-center text-danger">Ошибка при загрузке истории</td></tr>');
        }
    });
}

// Обновляем функцию showEditModal, чтобы загружать историю при открытии модального окна
function showEditModal(employeeId) {
    console.log('Открытие модального окна для сотрудника:', employeeId);
    
    // Загружаем данные сотрудника
    loadEmployeeDataForEdit(employeeId);
    
    // Загружаем историю изменений
    loadEmployeeHistory(employeeId);
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('editEmployeeModal'));
    modal.show();
}

// Обработчик для сворачивания/разворачивания истории - больше не нужен здесь, перенесен в HTML
$(document).ready(function() {
    // Обработчик для кнопки редактирования
    $(document).on('click', '.edit-employee-btn', function() {
        const employeeId = $(this).data('employee-id');
        console.log('Нажата кнопка редактирования для сотрудника:', employeeId);
        showEditModal(employeeId);
    });
    
    // ... existing code ...
});

function filterEmployees() {
    console.log('Начало фильтрации сотрудников');
    const searchText = $('#searchInput').val().toLowerCase();
    const departmentSelect = $('#departmentFilter');
    const selectedDepartment = departmentSelect.val();
    
    // Сначала скрываем все строки
    $('.department-section tbody tr').each(function() {
        const row = $(this);
        const fullName = row.find('td:nth-child(3)').text().toLowerCase();
        const position = row.find('td:nth-child(4)').text().toLowerCase();
        const phone = row.find('td:nth-child(5)').text().toLowerCase();
        const email = row.find('td:nth-child(6)').text().toLowerCase();
        
        const matchesSearch = fullName.includes(searchText) || 
                            position.includes(searchText) || 
                            phone.includes(searchText) || 
                            email.includes(searchText);
        
        const departmentSection = row.closest('.department-section');
        const departmentName = departmentSection.find('.department-header span').first().text().toLowerCase();
        
        const matchesDepartment = selectedDepartment === 'all' || 
                                departmentName === selectedDepartment.toLowerCase();
        
        if (matchesSearch && matchesDepartment) {
            row.removeClass('d-none');
        } else {
            row.addClass('d-none');
        }
    });
    
    // Затем обновляем видимость отделов
    $('.department-section').each(function() {
        const section = $(this);
        const visibleRows = section.find('tbody tr:not(.d-none)').length;
        
        console.log(`Отдел: ${section.find('.department-header span').first().text()}, видимых строк: ${visibleRows}`);
        
        if (visibleRows > 0) {
            section.removeClass('d-none');
        } else {
            section.addClass('d-none');
        }
    });
    
    console.log('Фильтрация завершена');
}

// Обработчик изменения поискового запроса
$('#searchInput').on('input', function() {
    filterEmployees();
});

// Обработчик изменения выбора отдела
$('#departmentFilter').on('change', function() {
    filterEmployees();
});

function fireEmployee(employeeId, employeeName) {
    const fireDate = $('#fireDate').val();
    
    if (!fireDate) {
        showNotification('Пожалуйста, выберите дату увольнения', 'danger');
        return;
    }
    
    $.ajax({
        url: '/admin/api/fire_employee',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            id: employeeId,
            fire_date: fireDate
        }),
        success: function(response) {
            if (response.success) {
                showNotification(`Сотрудник ${employeeName} успешно уволен`, 'success');
                setTimeout(() => {
                    location.reload();
                }, 1000);
            } else {
                showNotification(response.message, 'danger');
            }
        },
        error: function(xhr, status, error) {
            showNotification('Ошибка при увольнении сотрудника', 'danger');
        }
    });
}

// Функция для отображения уведомлений
function showNotification(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        console.error('Контейнер для уведомлений не найден');
        alert(message);
        return;
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = document.createElement('i');
    icon.className = `toast-icon ${type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle'}`;
    
    const content = document.createElement('div');
    content.className = 'toast-content';
    
    const title = document.createElement('div');
    title.className = 'toast-title';
    title.textContent = type === 'success' ? 'Успешно' : 'Ошибка';
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'toast-message';
    messageDiv.textContent = message;
    
    content.appendChild(title);
    content.appendChild(messageDiv);
    
    toast.appendChild(icon);
    toast.appendChild(content);
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('hide');
        setTimeout(() => {
            container.removeChild(toast);
        }, 300);
    }, 3000);
} 