const STORAGE_KEY = "todos";
const THEME_KEY = "theme";

const form = document.querySelector("#todo-form");
const input = document.querySelector("#todo-input");
const list = document.querySelector("#todo-list");
const empty = document.querySelector("#empty");
const themeToggle = document.querySelector("#theme-toggle");

function loadTodos() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveTodos(todos) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
}

function render(todos) {
  list.replaceChildren();
  empty.hidden = todos.length > 0;

  for (const todo of todos) {
    const item = document.createElement("li");
    item.className = "item";

    const text = document.createElement("span");
    text.className = "item-text";
    text.textContent = todo.text;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-button";
    remove.textContent = "Удалить";
    remove.addEventListener("click", () => {
      const next = loadTodos().filter((entry) => entry.id !== todo.id);
      saveTodos(next);
      render(next);
    });

    item.append(text, remove);
    list.append(item);
  }
}

function applyTheme(theme) {
  const next = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  themeToggle.textContent = next === "dark" ? "Светлая" : "Тёмная";
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) {
    return;
  }

  const todos = loadTodos();
  todos.push({ id: crypto.randomUUID(), text });
  saveTodos(todos);
  input.value = "";
  render(todos);
});

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
});

applyTheme(localStorage.getItem(THEME_KEY));
render(loadTodos());
