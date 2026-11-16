"""Интеграция «сверху вниз»: слой представления проверяется с заглушкой логики."""

from unittest.mock import Mock, patch

from carider.accounts import errors as accounts_errors
from carider.dispatch import errors as dispatch_errors
from carider.errors import CariderError
from carider.orders import errors as orders_errors

from .frozen import DEST, NOW, PHONE, PRICE, FrozenApiTestCase

# Контракт API (ЛР №6): код ответа и code для каждого исключения UC-01.
CONTRACT = {
    accounts_errors.ClientNotFoundError: (401, "UNAUTHORIZED"),
    accounts_errors.ClientBlockedError: (403, "CLIENT_BLOCKED"),
    orders_errors.InvalidDestinationError: (400, "INVALID_DESTINATION"),
    orders_errors.DestinationNotFoundError: (404, "DESTINATION_NOT_FOUND"),
    orders_errors.RoutingServiceError: (503, "SERVICE_UNAVAILABLE"),
    orders_errors.PriceChangedError: (409, "PRICE_CHANGED"),
    orders_errors.OrderNotFoundError: (404, "ORDER_NOT_FOUND"),
    orders_errors.OrderStateError: (409, "ORDER_STATE"),
    orders_errors.DriverBusyError: (409, "DRIVER_BUSY"),
    dispatch_errors.NoDriversError: (409, "NO_DRIVERS"),
}


def all_subclasses(cls):
    """Все наследники класса, включая внуков."""
    found = set()
    for child in cls.__subclasses__():
        found.add(child)
        found |= all_subclasses(child)
    return found


class CreateOrderViewStubTest(FrozenApiTestCase):
    """POST /api/orders/ без настоящего create_order(): логику заменяет заглушка."""

    def test_every_exception_becomes_its_contract_code(self):
        """Полиморфизм: каждое исключение UC-01 → свой код и code по контракту."""
        for error_class, (status, code) in CONTRACT.items():
            with self.subTest(error=error_class.__name__):
                target = "carider.orders.views.services.create_order"
                with patch(target, side_effect=error_class()):
                    response = self.post_order()
                self.assertEqual(response.status_code, status)
                body = response.get_json()["error"]
                self.assertEqual(body["code"], code)
                self.assertEqual(body["message"], error_class.message)

    def test_contract_lists_all_exception_classes(self):
        """Новое исключение без строки в контракте API ломает этот тест."""
        self.assertEqual(all_subclasses(CariderError), set(CONTRACT))

    def test_view_passes_cleaned_data_to_service(self):
        """Представление вызывает create_order() один раз с очищенными данными."""
        fake = Mock(id=7, status_label="Создан", created_at=NOW)
        with patch("carider.orders.views.services.create_order") as stub:
            stub.return_value = fake
            response = self.post_order()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["order_id"], 7)
        stub.assert_called_once()
        expected = {"destination": DEST, "phone": PHONE, "price_tg": PRICE}
        self.assertEqual(stub.call_args.kwargs, expected)

    def test_bad_format_never_reaches_service(self):
        """Формат проверяет представление: при неверных данных логика не вызывается."""
        with patch("carider.orders.views.services.create_order") as stub:
            wrong_phone = self.post_order(phone="8701")
            not_json = self.client.post(
                "/api/orders/", data="не json", content_type="application/json"
            )
        self.assertEqual(wrong_phone.status_code, 400)
        self.assertEqual(not_json.status_code, 400)
        stub.assert_not_called()


class OtherViewsStubTest(FrozenApiTestCase):
    """Остальные операции API с заглушкой слоя логики."""

    def test_cancel_view_returns_penalty_flag(self):
        """POST /api/orders/{id}/cancel/: ответ строится из результата сервиса."""
        fake = Mock(status_label="Отменён", penalty=True)
        with patch("carider.orders.views.services.cancel_order") as stub:
            stub.return_value = fake
            response = self.client.post("/api/orders/5/cancel/")
        self.assertEqual(response.get_json(), {"status": "Отменён", "penalty": True})
        stub.assert_called_once()
        self.assertEqual(stub.call_args.args[1], 5)

    def test_driver_view_maps_none_to_202_and_error_to_409(self):
        """GET /api/orders/{id}/driver/: None → 202, NoDriversError → 409."""
        target = "carider.dispatch.views.services.find_driver"
        with patch(target, return_value=None):
            self.assertEqual(self.client.get("/api/orders/3/driver/").status_code, 202)
        with patch(target, side_effect=dispatch_errors.NoDriversError()):
            self.assertEqual(self.client.get("/api/orders/3/driver/").status_code, 409)
