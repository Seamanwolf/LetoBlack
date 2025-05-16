// Функция для сохранения состояния отделов в localStorage
function saveDepartmentState(departmentId, isExpanded) {
    let departmentStates = JSON.parse(localStorage.getItem('departmentStates') || '{}');
    departmentStates[departmentId] = isExpanded;
    localStorage.setItem('departmentStates', JSON.stringify(departmentStates));
}

// Функция для загрузки состояния отделов из localStorage
function loadDepartmentStates() {
    return JSON.parse(localStorage.getItem('departmentStates') || '{}');
}

// Функция для сворачивания/разворачивания отдела с анимацией
function toggleDepartment(element, shouldExpand) {
    const section = element.closest('.department-section');
    const content = section.querySelector('.department-content');
    const icon = section.querySelector('.toggle-department');
    const departmentId = section.getAttribute('data-department-id');
    
    if (shouldExpand === undefined) {
        // Если параметр не передан, переключаем текущее состояние
        shouldExpand = content.style.display === 'none';
    }
    
    if (shouldExpand) {
        // Разворачиваем отдел
        content.style.display = 'block';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    } else {
        // Сворачиваем отдел
        content.style.display = 'none';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    }
    
    // Сохраняем состояние в localStorage
    saveDepartmentState(departmentId, shouldExpand);
}

// Функция для сворачивания всех отделов
function collapseAllDepartments() {
    document.querySelectorAll('.department-section').forEach(section => {
        const toggleIcon = section.querySelector('.toggle-department');
        toggleDepartment(toggleIcon, false);
    });
}

// Функция для разворачивания всех отделов
function expandAllDepartments() {
    document.querySelectorAll('.department-section').forEach(section => {
        const toggleIcon = section.querySelector('.toggle-department');
        toggleDepartment(toggleIcon, true);
    });
}

// Функция для восстановления состояния отделов при загрузке страницы
function restoreDepartmentStates() {
    const departmentStates = loadDepartmentStates();
    document.querySelectorAll('.department-section').forEach(section => {
        const departmentId = section.getAttribute('data-department-id');
        const isExpanded = departmentStates[departmentId];
        
        // Если есть сохраненное состояние, применяем его
        if (isExpanded !== undefined) {
            const toggleIcon = section.querySelector('.toggle-department');
            toggleDepartment(toggleIcon, isExpanded);
        }
    });
}

// Инициализация функций при загрузке документа
$(document).ready(function() {
    // Добавляем обработчики для кнопок сворачивания/разворачивания всех отделов
    document.getElementById('collapseAllBtn').addEventListener('click', collapseAllDepartments);
    document.getElementById('expandAllBtn').addEventListener('click', expandAllDepartments);
    
    // Восстанавливаем состояние отделов при загрузке страницы
    restoreDepartmentStates();
}); 