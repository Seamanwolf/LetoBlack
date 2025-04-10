#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.utils import register_module

def register_all_modules():
    """
    Регистрирует все основные модули системы
    """
    modules = [
        {
            'name': 'Дашборд', 
            'description': 'Главная страница системы',
            'url_path': '/dashboard',
            'icon': 'fa-home',
            'order': 1
        },
        {
            'name': 'Дашборд оператора',
            'description': 'Рабочая панель оператора',
            'url_path': '/operator_dashboard',
            'icon': 'fa-headset',
            'order': 2
        },
        {
            'name': 'Дашборд руководителя',
            'description': 'Панель руководителя с отчетами',
            'url_path': '/leader_dashboard',
            'icon': 'fa-chart-bar',
            'order': 3
        },
        {
            'name': 'Дашборд пользователя',
            'description': 'Базовая панель для пользователей',
            'url_path': '/user_dashboard',
            'icon': 'fa-user-circle',
            'order': 4
        },
        {
            'name': 'Новости',
            'description': 'Управление новостями',
            'url_path': '/news',
            'icon': 'fa-newspaper',
            'order': 5
        },
        {
            'name': 'Рейтинг',
            'description': 'Рейтинг брокеров',
            'url_path': '/rating',
            'icon': 'fa-chart-line',
            'order': 6
        },
        {
            'name': 'Персонал',
            'description': 'Управление сотрудниками',
            'url_path': '/personnel',
            'icon': 'fa-users',
            'order': 7
        },
        {
            'name': 'Персонал дашборд',
            'description': 'Статистика по персоналу',
            'url_path': '/personnel_dashboard',
            'icon': 'fa-user-tie',
            'order': 8
        },
        {
            'name': 'Колл-центр',
            'description': 'Управление колл-центром',
            'url_path': '/vats',
            'icon': 'fa-phone',
            'order': 9
        },
        {
            'name': 'Настройки',
            'description': 'Настройки системы',
            'url_path': '/admin/settings',
            'icon': 'fa-cog',
            'order': 10
        },
        {
            'name': 'ВАТС',
            'description': 'Виртуальная АТС',
            'url_path': '/vats_admin',
            'icon': 'fa-phone-alt',
            'order': 11
        },
        {
            'name': 'АВИТО-ПРО',
            'description': 'Интеграция с Авито Про',
            'url_path': '/avito_pro',
            'icon': 'fa-bullhorn',
            'order': 12
        },
        {
            'name': 'IT-Tech',
            'description': 'IT поддержка и техническое обслуживание',
            'url_path': '/it_support',
            'icon': 'fa-laptop-code',
            'order': 13
        },
        {
            'name': 'Хелпдеск',
            'description': 'Система технической поддержки',
            'url_path': '/helpdesk',
            'icon': 'fa-hands-helping',
            'order': 14
        }
    ]
    
    for module in modules:
        module_id = register_module(
            name=module['name'],
            description=module['description'],
            url_path=module['url_path'],
            icon=module['icon'],
            order=module['order']
        )
        print(f"Зарегистрирован модуль: {module['name']} (ID: {module_id})")
    
    print("Обновление модулей завершено!")

if __name__ == "__main__":
    register_all_modules()

# Регистрация всех модулей системы
register_module(
    name="Панель администратора",
    description="Административная панель управления системой",
    url_path="admin.index",
    icon="fas fa-cog",
    order=100
)

print("Зарегистрирован модуль: Панель администратора")

register_module(
    name="Панель HR",
    description="Управление заявками, кандидатами и воронкой",
    url_path="hr.dashboard",
    icon="fas fa-users",
    order=200
)

print("Зарегистрирован модуль: Панель HR")

register_module(
    name="Панель рекрутера",
    description="Управление вакансиями и кандидатами",
    url_path="recruiter.dashboard",
    icon="fas fa-user-tie",
    order=300
)

print("Зарегистрирован модуль: Панель рекрутера")

register_module(
    name="Панель ресепшн",
    description="Управление посетителями и встречами",
    url_path="reception.dashboard",
    icon="fas fa-concierge-bell",
    order=400
)

print("Зарегистрирован модуль: Панель ресепшн")

register_module(
    name="Новости",
    description="Управление новостями компании",
    url_path="news.index",
    icon="far fa-newspaper",
    order=500
)

print("Зарегистрирован модуль: Новости")

register_module(
    name="Персонал",
    description="Управление сотрудниками, командами и отделами",
    url_path="admin.personnel",
    icon="fas fa-id-card",
    order=600
)

print("Зарегистрирован модуль: Персонал")

register_module(
    name="Настройки",
    description="Системные настройки и конфигурация",
    url_path="admin.settings",
    icon="fas fa-cogs",
    order=700
)

print("Зарегистрирован модуль: Настройки")

# Добавляем новые модули
register_module(
    name="ВАТС",
    description="Управление виртуальной АТС и телефонией",
    url_path="vats.index",
    icon="fas fa-phone-alt",
    order=800
)

print("Зарегистрирован модуль: ВАТС")

register_module(
    name="АВИТО-ПРО",
    description="Интеграция и управление сервисами Авито",
    url_path="avito_pro.index",
    icon="fas fa-store",
    order=900
)

print("Зарегистрирован модуль: АВИТО-ПРО")

register_module(
    name="IT-Tech",
    description="Управление IT инфраструктурой и оборудованием",
    url_path="it_tech.index",
    icon="fas fa-laptop-code",
    order=1000
)

print("Зарегистрирован модуль: IT-Tech")

register_module(
    name="Хелпдеск",
    description="Система обработки заявок и поддержки пользователей",
    url_path="helpdesk.index",
    icon="fas fa-headset",
    order=1100
)

print("Зарегистрирован модуль: Хелпдеск")

print("\nВсе модули успешно обновлены!") 