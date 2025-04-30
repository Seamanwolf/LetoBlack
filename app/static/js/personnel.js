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