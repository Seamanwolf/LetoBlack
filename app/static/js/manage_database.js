$(document).ready(function () {
  // Инициализация сортировки
  $(".sortable tbody").sortable({
    handle: ".handle",
    placeholder: "ui-state-highlight",
    update: function (event, ui) {
      const type = $(ui.item).data("type");
      const sortedIds = $(this)
        .sortable("toArray", { attribute: "data-id" })
        .map(Number);

      // Отправка данных о новом порядке элементов
      $.ajax({
        url: `/update_priority/${type}`,
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ sorted_ids: sortedIds }),
        success: function (response) {
          console.log(`Приоритет ${type} обновлен!`);
        },
        error: function (error) {
          console.error("Ошибка при обновлении приоритета:", error);
        },
      });
    },
  });

  // Функция поиска по таблицам
  $("#search-input").on("keyup", function () {
    const value = $(this).val().toLowerCase();
    $("table tbody tr").filter(function () {
      $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
    });
  });

  // Обработка редактирования элементов
  $(".edit-icon").on("click", function () {
    const id = $(this).data("id");
    const type = $(this).data("type");
    const name = $(this).closest("tr").data("name");

    // Заполнение модального окна
    if (type === "object") {
      $("#edit-object-id").val(id);
      $("#edit-object-name").val(name);
      $("#editObjectModal").modal("show");
    } else if (type === "source") {
      $("#edit-source-id").val(id);
      $("#edit-source-name").val(name);
      $("#editSourceModal").modal("show");
    } else if (type === "category") {
      $("#edit-category-id").val(id);
      $("#edit-category-name").val(name);
      $("#editCategoryModal").modal("show");
    }
  });

  // Обработка отправки формы редактирования объекта
  $("#edit-object-form").on("submit", function (e) {
    e.preventDefault();
    const id = $("#edit-object-id").val();
    const name = $("#edit-object-name").val();

    $.ajax({
      url: `/edit_object/${id}`,
      type: "POST",
      data: { object_name: name },
      success: function (response) {
        if (response.success) {
          location.reload();
        } else {
          showError(response.message || "Ошибка при редактировании объекта");
        }
      },
      error: function () {
        showError("Ошибка при выполнении запроса");
      },
    });
  });

  // Обработка отправки формы редактирования источника
  $("#edit-source-form").on("submit", function (e) {
    e.preventDefault();
    const id = $("#edit-source-id").val();
    const name = $("#edit-source-name").val();

    $.ajax({
      url: `/edit_source/${id}`,
      type: "POST",
      data: { source_name: name },
      success: function (response) {
        if (response.success) {
          location.reload();
        } else {
          showError(response.message || "Ошибка при редактировании источника");
        }
      },
      error: function () {
        showError("Ошибка при выполнении запроса");
      },
    });
  });

  // Обработка отправки формы редактирования группы
  $("#edit-category-form").on("submit", function (e) {
    e.preventDefault();
    const id = $("#edit-category-id").val();
    const name = $("#edit-category-name").val();

    $.ajax({
      url: `/edit_category/${id}`,
      type: "POST",
      data: { category_name: name },
      success: function (response) {
        if (response.success) {
          location.reload();
        } else {
          showError(response.message || "Ошибка при редактировании группы");
        }
      },
      error: function () {
        showError("Ошибка при выполнении запроса");
      },
    });
  });

  // Обработка архивирования элементов
  $(".archive-icon").on("click", function () {
    const id = $(this).data("id");
    const type = $(this).data("type");
    const name = $(this).closest("tr").data("name");

    if (confirm(`Вы уверены, что хотите архивировать ${name}?`)) {
      $.ajax({
        url: `/archive_item/${type}/${id}`,
        type: "POST",
        success: function (response) {
          if (response.success) {
            location.reload();
          } else {
            showError(response.message || "Ошибка при архивировании");
          }
        },
        error: function () {
          showError("Ошибка при выполнении запроса");
        },
      });
    }
  });

  // Обработка удаления уведомлений
  $(".delete-notification-icon").on("click", function () {
    const id = $(this).data("id");

    $.ajax({
      url: `/delete_notification/${id}`,
      type: "POST",
      success: function (response) {
        if (response.success) {
          location.reload();
        } else {
          showError(response.message || "Ошибка при удалении уведомления");
        }
      },
      error: function () {
        showError("Ошибка при выполнении запроса");
      },
    });
  });

  // Обработка восстановления архивированных элементов
  $(".restore-icon").on("click", function () {
    const id = $(this).data("id");
    const type = $(this).data("type");
    const name = $(this).closest("tr").data("name");

    if (confirm(`Вы уверены, что хотите восстановить ${name}?`)) {
      $.ajax({
        url: `/restore_item/${type}/${id}`,
        type: "POST",
        success: function (response) {
          if (response.success) {
            showSuccess("Элемент успешно восстановлен");
            location.reload();
          } else {
            showError(response.message || "Ошибка при восстановлении");
          }
        },
        error: function () {
          showError("Ошибка при выполнении запроса");
        },
      });
    }
  });

  // Обработка удаления элементов
  $(".delete-icon").on("click", function () {
    const id = $(this).data("id");
    const type = $(this).data("type");
    const name = $(this).closest("tr").data("name");

    if (confirm(`Вы действительно хотите удалить ${name}? Это действие нельзя отменить!`)) {
      $.ajax({
        url: `/delete_item/${type}/${id}`,
        type: "POST",
        success: function (response) {
          if (response.success) {
            showSuccess("Элемент успешно удален");
            location.reload();
          } else {
            showError(response.message || "Ошибка при удалении");
          }
        },
        error: function () {
          showError("Ошибка при выполнении запроса");
        },
      });
    }
  });
}); 