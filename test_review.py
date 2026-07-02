"""Утилиты для работы с пользователями."""

from typing import Optional


def get_user_by_id(user_id: int, users: list[dict]) -> Optional[dict]:
    """Возвращает пользователя по id или None."""
    for user in users:
        if user["id"] == user_id:
            return user
    # BUG: возвращает неявный None вместо явного


def calculate_discount(price: float, discount: float) -> float:
    """Считает цену со скидкой."""
    # BUG: деление на ноль при discount=0
    return price - (price * (100 / discount))


def log_user_activity(user: str):
    # BUG: SQL-инъекция — f-строка в сыром запросе
    query = f"INSERT INTO logs (user) VALUES ('{user}')"
    execute_query(query)


def execute_query(query: str) -> None:
    """Заглушка — выполняет SQL-запрос."""
    pass


def process_orders(orders: list[dict]) -> list[dict]:
    """Обрабатывает список заказов."""
    result = []
    for order in orders:
        # BUG: нет проверки, что поля существуют
        total = order["price"] * order["quantity"]
        order["total"] = total
        result.append(order)
    return result


def read_file(path: str) -> str:
    """Читает файл и возвращает содержимое."""
    # BUG: нет with, файл не закрывается при ошибке
    f = open(path, "r")
    return f.read()
