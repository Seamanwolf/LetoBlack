document.addEventListener('DOMContentLoaded', function() {
    // Загрузка активной вкладки из localStorage
    const activeTab = localStorage.getItem('activeOrganizationTab') || 'positions';
    const tab = document.querySelector(`#organizationTabs a[href="#${activeTab}"]`);
    if (tab) {
        const tabInstance = new bootstrap.Tab(tab);
        tabInstance.show();
    }

    // Сохранение активной вкладки при переключении
    document.querySelectorAll('#organizationTabs a').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const target = e.target.getAttribute('href').substring(1);
            localStorage.setItem('activeOrganizationTab', target);
        });
    });

    // Инициализация модальных окон
    const positionModal = new bootstrap.Modal(document.getElementById('addPositionModal'));
    const departmentModal = new bootstrap.Modal(document.getElementById('addDepartmentModal'));
    const locationModal = new bootstrap.Modal(document.getElementById('addLocationModal'));
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));

    // Загрузка данных при открытии страницы
    loadPositions();
    loadDepartments();
    loadLocations();

    // Обработчики событий для должностей
    document.querySelector('[data-bs-target="#addPositionModal"]').addEventListener('click', () => {
        document.getElementById('positionModalTitle').textContent = 'Добавить должность';
        document.getElementById('positionForm').reset();
    });

    document.getElementById('savePosition').addEventListener('click', async () => {
        const form = document.getElementById('positionForm');
        const formData = new FormData(form);
        const id = formData.get('id');
        
        try {
            const response = await fetch(`/admin/settings/positions${id ? `/${id}` : ''}`, {
                method: id ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(Object.fromEntries(formData))
            });
            
            if (response.ok) {
                positionModal.hide();
                loadPositions();
                showNotification('Должность успешно сохранена', 'success');
            } else {
                const error = await response.json();
                showNotification(error.message || 'Ошибка при сохранении должности', 'error');
            }
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при сохранении должности', 'error');
        }
    });

    // Обработчики событий для отделов
    document.querySelector('[data-bs-target="#addDepartmentModal"]').addEventListener('click', () => {
        document.getElementById('departmentModalTitle').textContent = 'Добавить отдел';
        document.getElementById('departmentForm').reset();
        loadLocationsForSelect();
        loadEmployeesForSelect();
    });

    document.getElementById('saveDepartment').addEventListener('click', async () => {
        const form = document.getElementById('departmentForm');
        const formData = new FormData(form);
        const id = formData.get('id');
        
        try {
            const response = await fetch(`/admin/settings/departments${id ? `/${id}` : ''}`, {
                method: id ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(Object.fromEntries(formData))
            });
            
            if (response.ok) {
                departmentModal.hide();
                loadDepartments();
                showNotification('Отдел успешно сохранен', 'success');
            } else {
                const error = await response.json();
                showNotification(error.message || 'Ошибка при сохранении отдела', 'error');
            }
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при сохранении отдела', 'error');
        }
    });

    // Обработчики событий для локаций
    document.querySelector('[data-bs-target="#addLocationModal"]').addEventListener('click', () => {
        document.getElementById('locationModalTitle').textContent = 'Добавить локацию';
        document.getElementById('locationForm').reset();
    });

    document.getElementById('saveLocation').addEventListener('click', async () => {
        const form = document.getElementById('locationForm');
        const formData = new FormData(form);
        const id = formData.get('id');
        
        try {
            const response = await fetch(`/admin/settings/locations${id ? `/${id}` : ''}`, {
                method: id ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(Object.fromEntries(formData))
            });
            
            if (response.ok) {
                locationModal.hide();
                loadLocations();
                showNotification('Локация успешно сохранена', 'success');
            } else {
                const error = await response.json();
                showNotification(error.message || 'Ошибка при сохранении локации', 'error');
            }
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при сохранении локации', 'error');
        }
    });

    // Обработчик подтверждения удаления
    let deleteCallback = null;
    
    document.getElementById('confirmDelete').addEventListener('click', () => {
        if (deleteCallback) {
            deleteCallback();
            deleteModal.hide();
        }
    });

    // Функции загрузки данных
    async function loadPositions() {
        try {
            const response = await fetch('/admin/settings/positions');
            const positions = await response.json();
            
            const tbody = document.getElementById('positionsTableBody');
            tbody.innerHTML = positions.map(position => `
                <tr>
                    <td>${position.name}</td>
                    <td>${position.description || ''}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="editPosition(${position.id})">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deletePosition(${position.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке должностей', 'error');
        }
    }

    async function loadDepartments() {
        try {
            const response = await fetch('/admin/settings/departments');
            const departments = await response.json();
            
            const tbody = document.getElementById('departmentsTableBody');
            tbody.innerHTML = departments.map(department => `
                <tr>
                    <td>${department.name}</td>
                    <td>${department.location ? department.location.name : ''}</td>
                    <td>${department.leader ? department.leader.full_name : ''}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="editDepartment(${department.id})">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteDepartment(${department.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке отделов', 'error');
        }
    }

    async function loadLocations() {
        try {
            const response = await fetch('/admin/settings/locations');
            const locations = await response.json();
            
            const tbody = document.getElementById('locationsTableBody');
            tbody.innerHTML = locations.map(location => `
                <tr>
                    <td>${location.name}</td>
                    <td>${location.address}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="editLocation(${location.id})">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteLocation(${location.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке локаций', 'error');
        }
    }

    async function loadLocationsForSelect() {
        try {
            const response = await fetch('/admin/settings/locations');
            const locations = await response.json();
            
            const select = document.getElementById('departmentLocation');
            select.innerHTML = '<option value="">Выберите локацию</option>' + 
                locations.map(location => `
                    <option value="${location.id}">${location.name}</option>
                `).join('');
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке локаций', 'error');
        }
    }

    async function loadEmployeesForSelect() {
        try {
            const response = await fetch('/admin/settings/employees');
            const employees = await response.json();
            
            const select = document.getElementById('departmentLeader');
            select.innerHTML = '<option value="">Выберите руководителя</option>' + 
                employees.map(employee => `
                    <option value="${employee.id}">${employee.full_name}</option>
                `).join('');
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке сотрудников', 'error');
        }
    }

    // Функции редактирования
    window.editPosition = async (id) => {
        try {
            const response = await fetch(`/admin/settings/positions/${id}`);
            const position = await response.json();
            
            document.getElementById('positionModalTitle').textContent = 'Редактировать должность';
            document.getElementById('positionId').value = position.id;
            document.getElementById('positionName').value = position.name;
            document.getElementById('positionDescription').value = position.description || '';
            
            positionModal.show();
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке данных должности', 'error');
        }
    };

    window.editDepartment = async (id) => {
        try {
            const response = await fetch(`/admin/settings/departments/${id}`);
            const department = await response.json();
            
            await Promise.all([
                loadLocationsForSelect(),
                loadEmployeesForSelect()
            ]);
            
            document.getElementById('departmentModalTitle').textContent = 'Редактировать отдел';
            document.getElementById('departmentId').value = department.id;
            document.getElementById('departmentName').value = department.name;
            document.getElementById('departmentLocation').value = department.location_id || '';
            document.getElementById('departmentLeader').value = department.leader_id || '';
            document.getElementById('departmentDescription').value = department.description || '';
            
            departmentModal.show();
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке данных отдела', 'error');
        }
    };

    window.editLocation = async (id) => {
        try {
            const response = await fetch(`/admin/settings/locations/${id}`);
            const location = await response.json();
            
            document.getElementById('locationModalTitle').textContent = 'Редактировать локацию';
            document.getElementById('locationId').value = location.id;
            document.getElementById('locationName').value = location.name;
            document.getElementById('locationAddress').value = location.address;
            
            locationModal.show();
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при загрузке данных локации', 'error');
        }
    };

    // Функции удаления
    window.deletePosition = (id) => {
        deleteCallback = async () => {
            try {
                const response = await fetch(`/admin/settings/positions/${id}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    loadPositions();
                    showNotification('Должность успешно удалена', 'success');
                } else {
                    const error = await response.json();
                    showNotification(error.message || 'Ошибка при удалении должности', 'error');
                }
            } catch (error) {
                console.error('Ошибка:', error);
                showNotification('Ошибка при удалении должности', 'error');
            }
        };
        deleteModal.show();
    };

    window.deleteDepartment = (id) => {
        deleteCallback = async () => {
            try {
                const response = await fetch(`/admin/settings/departments/${id}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    loadDepartments();
                    showNotification('Отдел успешно удален', 'success');
                } else {
                    const error = await response.json();
                    showNotification(error.message || 'Ошибка при удалении отдела', 'error');
                }
            } catch (error) {
                console.error('Ошибка:', error);
                showNotification('Ошибка при удалении отдела', 'error');
            }
        };
        deleteModal.show();
    };

    window.deleteLocation = (id) => {
        deleteCallback = async () => {
            try {
                const response = await fetch(`/admin/settings/locations/${id}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    loadLocations();
                    showNotification('Локация успешно удалена', 'success');
                } else {
                    const error = await response.json();
                    showNotification(error.message || 'Ошибка при удалении локации', 'error');
                }
            } catch (error) {
                console.error('Ошибка:', error);
                showNotification('Ошибка при удалении локации', 'error');
            }
        };
        deleteModal.show();
    };
}); 