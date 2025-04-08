// Определение переменной analytics, чтобы избежать ошибки ReferenceError
var analytics = {
    // Пустой объект для имитации аналитики
    track: function() {
        console.log('Analytics tracking:', arguments);
    },
    // Другие методы, которые могут использоваться
    identify: function() {
        console.log('Analytics identify:', arguments);
    },
    page: function() {
        console.log('Analytics page:', arguments);
    }
};

// Остальной код core.js
console.log('Core.js загружен'); 