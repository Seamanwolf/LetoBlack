# filter_utils.py

import time
from playwright.sync_api import sync_playwright


ATS_URL = "https://leto.megapbx.ru/#/"
ATS_LOGIN = "admin@leto.megapbx.ru"
ATS_PASSWORD = "AaSs2023@"

ATS_LOGIN_SELECTOR = "input.input.autocomplete[type='text']"
ATS_PASSWORD_SELECTOR = "input.input.password.autocomplete[type='password']"
ATS_LOGIN_BUTTON_SELECTOR = "button.itl-button.mr-x2.primary"
ATS_HISTORY_SELECTOR = "[data-qa='history']"

# Сопоставляем категории сайта => коды
CATEGORY_TO_CODE = {
    "Вторички": "В",
    "Загородная коммерция": "ЗК"
}

def normalize_sim_number(sim_number: str) -> str:
    """
    Приводит номер к формату без ведущих +7 или 8.
    Пример:
      +79001234567 => 9001234567
      89001234567  => 9001234567
      79001234567  => 9001234567
    Если не получается — вернём пустую строку.
    """
    digits = ''.join(ch for ch in sim_number if ch.isdigit())
    # digits может быть '79001234567' (11 цифр)
    if len(digits) == 11:
        if digits[0] in ('7', '8'):
            return digits[1:]  # отрезаем первую цифру => 9001234567
        else:
            return digits  # на всякий случай
    elif len(digits) == 10:
        # иногда могут быть 10 цифр без 7
        return digits
    return ''  # ошибка

def update_ats_filter(category: str, employee_name: str, department: str, sim_number: str):
    """
    Открывает Playwright, логинится в ATS, находит фильтр, 
    ставит SIM в чекбокс. 
    category: 'Вторички' или 'Загородная коммерция' => 'В'/'ЗК'
    employee_name: (для логов)
    department: (добавляется в строку фильтра)
    sim_number: '89001234567', '79001234567'...
    """

    def log(message: str):
        print(message)  # Сохраняем вывод в консоль

    # Начало логики
    log("🚀 Начало настройки фильтра (update_ats_filter)")
    print("[update_ats_filter] Запуск функции update_ats_filter")
    # 1) Определяем код из CATEGORY_TO_CODE
    filter_code = CATEGORY_TO_CODE.get(category, None)
    if not filter_code:
        raise ValueError(f"[update_ats_filter] ❌ Не найден код фильтра для категории: {category}")
    log(f"✅ Определен код фильтра: {filter_code} для категории: {category}") 
    print(f"[update_ats_filter] Определен код фильтра: {filter_code} для категории: {category}")

    # 2) Приводим sim_number к виду 9001234567
    log("📞 Форматирование sim_number -> normalized_sim")
    normalized_sim = normalize_sim_number(sim_number)
    if not normalized_sim:
        raise ValueError(f"[update_ats_filter] ❌ Неверный формат номера SIM: '{sim_number}'")

    target_filter_text = f"Авито Про {department} ({filter_code})"
    log(f"🔧 Сформирован target_filter_text: '{target_filter_text}'")
    print(f"[update_ats_filter] target_filter_text сформирован: '{target_filter_text}'")
    log(f"ℹ️ Параметры: category={category}, code={filter_code}, " f"employee={employee_name}, dept={department}, sim={sim_number} => normalized={normalized_sim}")
    print(f"[update_ats_filter] Логирование входных параметров: category={category}, code={filter_code}, employee={employee_name}, dept={department}, sim={sim_number} => normalized={normalized_sim}")

    with sync_playwright() as p:
        log("🌐 Запуск браузера Chromium в headless-режиме...")
        print("[update_ats_filter] Запуск браузера")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 3) Логинимся
        log("👤 Переход на страницу ATS...")
        print("[update_ats_filter] Переход на страницу ATS")
        page.goto(ATS_URL)
        log("⌨️ Ввод логина и пароля...")
        print("[update_ats_filter] Клик по полю логина")
        page.click(ATS_LOGIN_SELECTOR)
        print("[update_ats_filter] Ввод логина")
        page.type(ATS_LOGIN_SELECTOR, ATS_LOGIN, delay=100)
        print("[update_ats_filter] Клик по полю пароля")
        page.click(ATS_PASSWORD_SELECTOR)
        print("[update_ats_filter] Ввод пароля")
        page.type(ATS_PASSWORD_SELECTOR, ATS_PASSWORD, delay=100)
        log("🔓 Нажатие кнопки входа...")
        print("[update_ats_filter] Клик по кнопке входа")
        page.click(ATS_LOGIN_BUTTON_SELECTOR)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        log("✅ Авторизация выполнена")
        print("[update_ats_filter] Логин выполнен")

        # 4) Переходим в "Историю"
        log("📋 Переходим в раздел 'История'...")
        print("[update_ats_filter] Переход в раздел 'История'")
        page.click(ATS_HISTORY_SELECTOR)
        page.wait_for_timeout(1000)

        # 5) Открываем фильтры
        if page.is_visible("button:has-text('Фильтры')"):
            log("🔍 Открываем панель фильтров...")
            print("[update_ats_filter] Клик по кнопке 'Фильтры'")
            page.click("button:has-text('Фильтры')")
            page.wait_for_timeout(500)
        else:
            log("❗ Кнопка 'Фильтры' не найдена (невидима)")
            print("[update_ats_filter] Кнопка 'Фильтры' не видна")

        # 6) "Все номера"
        log("📱 Кликаем по 'Все номера'")
        print("[update_ats_filter] Клик по элементу 'Все номера'")
        page.click("span.label-wrapper:has(span.label:text('Все номера'))")
        page.wait_for_timeout(500)

        # 7) Печатаем target_filter_text
        log(f"⌨️ Вводим текст фильтра: {target_filter_text}")
        print(f"[update_ats_filter] Ввод текста фильтра: {target_filter_text}")
        page.keyboard.type(target_filter_text, delay=100)
        page.wait_for_timeout(500)

        # 8) Находим элемент фильтра
        log(f"🔎 Поиск элемента фильтра с текстом: '{target_filter_text}'")
        print(f"[update_ats_filter] Поиск элемента фильтра с текстом: {target_filter_text}")
        filter_elements = page.locator(f"text={target_filter_text}").element_handles()
        if not filter_elements:
            raise ValueError(f"[update_ats_filter] ❌ Фильтр '{target_filter_text}' не найден.")

        target_element = None
        for handle in filter_elements:
            text_content = handle.inner_text().strip()
            log(f"🔎 Найден элемент с текстом: '{text_content}'")
            print(f"[update_ats_filter] Найден элемент с текстом: '{text_content}'")
            if text_content == target_filter_text:
                target_element = handle
                log("✅ Элемент полностью совпал с target_filter_text")
                print("[update_ats_filter] Элемент точно совпадает с target_filter_text")
                break
        if not target_element:
            target_element = filter_elements[0]
            log("❗ Точное совпадение не найдено, выбираем первый элемент")
            print("[update_ats_filter] Точное совпадение не найдено, выбран первый элемент")

        li_element = target_element.evaluate_handle("node => node.closest('li.item')")
        if not li_element:
            raise ValueError("[update_ats_filter] ❌ Не удалось найти <li> для выбранного фильтра.")
        log("✅ Найден родительский элемент <li> для фильтра")
        print("[update_ats_filter] Найден родительский элемент <li> для фильтра")

        # 8.1) Используем Locator для значка настроек
        log("⚙️ Ищем значок настроек фильтра...")
        print("[update_ats_filter] Поиск значка настроек для фильтра")
        settings_icon_locator = page.locator("div.itl-setup div.svg-settings-24.table-clickable")
        settings_icon_locator.first.wait_for(state="visible")
        log("✅ Значок настроек найден, кликаем по нему")
        print("[update_ats_filter] Значок настроек найден, выполняется клик")

        # Прокручиваем элемент в видимость, если он не виден
        settings_icon_locator.first.scroll_into_view_if_needed()

        # Кликаем по элементу
        settings_icon_locator.first.click()

        # 9) Настройка SIM в фильтре
        log("⌛ Ожидаем появления поля поиска в настройках фильтра")
        print("[update_ats_filter] Ожидание появления поля поиска в настройках фильтра")
        page.wait_for_selector("input.search")
        log("🔎 Клик по полю поиска для SIM")
        print("[update_ats_filter] Клик по полю поиска")
        page.click("input.search")
        log(f"⌨️ Вводим normalized_sim: {normalized_sim}")
        print(f"[update_ats_filter] Ввод normalized_sim: {normalized_sim}")
        page.type("input.search", normalized_sim, delay=100)
        page.wait_for_timeout(500)

        # 10) Поиск чекбокса по SIM
        log("🔎 Ищем li.item для установки чекбокса")
        print("[update_ats_filter] Поиск элемента li.item для установки чекбокса")
        li_items = page.query_selector_all("li.item")
        target_li = None
        for li in li_items:
            li_text = li.inner_text().lower()
            log(f"⏩ Проверка li.item с текстом: {li_text}")
            print(f"[update_ats_filter] Проверка li.item с текстом: {li_text}")
            if "номер" not in li_text and "регион" not in li_text:
                target_li = li
                log("✅ Найден элемент для чекбокса")
                print("[update_ats_filter] Найден подходящий элемент для чекбокса")
                break

        if not target_li:
            raise ValueError("[update_ats_filter] ❌ Не найден элемент в списке для данного SIM.")

        li_classes = target_li.get_attribute("class") or ""
        if "active" in li_classes:
            log("⚠️ Чекбокс уже установлен (на уровне <li>), настройка не требуется")
            print("[update_ats_filter] Чекбокс уже отмечен (на уровне <li>), настройка фильтра не требуется.")
        else:
            checkbox_input = target_li.query_selector("input[type='checkbox']")
            if checkbox_input:
                input_classes = checkbox_input.get_attribute("class") or ""
                if "checked" in input_classes:
                    log("⚠️ Чекбокс уже отмечен (на уровне <input>), настройка не требуется")
                    print("[update_ats_filter] Чекбокс уже отмечен (на уровне <input>), настройка фильтра не требуется.")
                else:
                    checkbox_label = target_li.query_selector("label.itl-checkbox")
                    if checkbox_label:
                        log("✅ Кликаем по label чекбокса для установки SIM")
                        print("[update_ats_filter] Клик по label чекбокса для установки SIM")
                        checkbox_label.click(force=True)
                        page.wait_for_timeout(500)
                        log(f"✅ Чекбокс установлен для SIM: {normalized_sim}")
                        print("[update_ats_filter] Чекбокс установлен для SIM:", normalized_sim)
                    else:
                        raise ValueError("[update_ats_filter] ❌ Не удалось найти label чекбокса.")
            else:
                raise ValueError("[update_ats_filter] ❌ Не удалось найти checkbox_input в target_li")

        # 11) Сохранение изменений
        log("💾 Сохранение изменений")
        print("[update_ats_filter] Клик по кнопке 'Сохранить'")
        page.click("button:has-text('Сохранить')")
        page.wait_for_timeout(500)

        browser.close()
        log(f"✅ Фильтр успешно настроен для {employee_name} (SIM: {normalized_sim})")
        print(f"[update_ats_filter] Фильтр '{target_filter_text}' обновлен для сотрудника {employee_name}, sim={normalized_sim}.")
