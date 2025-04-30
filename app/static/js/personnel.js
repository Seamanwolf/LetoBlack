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