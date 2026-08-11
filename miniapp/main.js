// Клиентская логика Telegram Mini App. Скрипт читает форму, формирует JSON и
// передаёт его основному боту через официальный объект window.Telegram.WebApp.

// Сохраняем ссылки на часто используемые узлы, чтобы не искать их в DOM повторно.
const form = document.getElementById("recipe-form");
const statusBadge = document.getElementById("status");
const submitBtn = document.getElementById("submit-btn");

// Optional chaining (?.) позволяет открыть страницу в обычном браузере:
// если Telegram API отсутствует, переменная станет undefined без ошибки.
const tg = window.Telegram?.WebApp;

if (tg) {
  // ready скрывает системный loader Telegram, expand разворачивает окно по высоте.
  tg.ready();
  tg.expand();
}

function setStatus(text, isError = false) {
  // Второй аргумент необязателен: обычное состояние используется по умолчанию.
  statusBadge.textContent = text;
  statusBadge.style.background = isError ? "#fee2e2" : "#e2e8f0";
  statusBadge.style.color = isError ? "#b91c1c" : "#0f172a";
}

function collectExtras() {
  // querySelectorAll возвращает NodeList; Array.from даёт обычный массив,
  // после чего map извлекает только значения отмеченных checkbox.
  return Array.from(document.querySelectorAll("input[name='extras']:checked")).map(
    (checkbox) => checkbox.value
  );
}

form.addEventListener("submit", (event) => {
  // Отменяем стандартную перезагрузку страницы при отправке HTML-формы.
  event.preventDefault();

  const ingredients = document.getElementById("ingredients").value.trim();
  const diet = document.getElementById("diet").value;
  const goal = document.getElementById("goal").value.trim();
  const extras = collectExtras();

  if (!ingredients) {
    setStatus("Нужно заполнить продукты", true);
    return;
  }

  // Имена ключей согласованы с _compose_prompt в handlers/webapp_data.py.
  const payload = {
    source: "miniapp",
    ingredients,
    diet,
    goal,
    extras,
    submitted_at: new Date().toISOString(),
  };

  setStatus("Отправляю…");
  submitBtn.disabled = true;

  const serialized = JSON.stringify(payload);

  if (tg) {
    // sendData создаёт Telegram-сообщение типа web_app_data; после этого форму
    // можно закрыть. В браузере выполняется безопасный демонстрационный fallback.
    tg.sendData(serialized);
    tg.close();
  } else {
    console.log("Mini app payload:", serialized);
    alert("Данные отправлены (эмуляция)");
  }

  setStatus("Готов");
  submitBtn.disabled = false;
  form.reset();
});

