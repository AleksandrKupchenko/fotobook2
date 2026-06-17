import json
from channels.generic.websocket import AsyncWebsocketConsumer


class OrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Подключение к WebSocket.
        Добавляем клиента в группу 'printers' — это общая группа для печатников.
        """
        user = self.scope.get("user")
        username = getattr(user, "username", "Anonymous")

        await self.channel_layer.group_add("printers", self.channel_name)
        await self.accept()

        print(f"[WS CONNECT ✅] {self.channel_name} подключён (user={username})")

    async def disconnect(self, close_code):
        """
        Отключение клиента от группы printers.
        """
        await self.channel_layer.group_discard("printers", self.channel_name)
        print(f"[WS DISCONNECT] {self.channel_name} отключён от группы printers")

    async def receive(self, text_data):
        """
        Получение сообщений от клиента.
        Просто пересылаем их обратно всем участникам группы printers.
        """
        try:
            data = json.loads(text_data)
            message = data.get("message", "")
        except json.JSONDecodeError:
            message = text_data

        print(f"[WS RECEIVE] от клиента: {message}")

        await self.channel_layer.group_send(
            "printers",
            {
                "type": "order_message",
                "message": message
            }
        )

    async def order_message(self, event):
        """
        Обработка события 'order_message' (эха сообщений от клиентов).
        """
        print(f"[WS ORDER_MESSAGE] получено событие: {event}")

        try:
            msg = json.dumps({
                "type": "message",
                "message": event.get("message", "")
            })
            print(f"[WS SEND -> CLIENT] {msg}")
            await self.send(text_data=msg)
            print(f"[WS SEND ✅] сообщение отправлено клиенту.")
        except Exception as e:
            print(f"[WS SEND ❌] ошибка при отправке: {e}")

    async def send_new_order(self, event):
        """
        Обработка события нового заказа, полученного через Redis group_send.
        Это вызывается из views.product_options.
        """
        print(f"[WS NEW_ORDER EVENT] {event}")

        # Добавляем product_type и book_type
        data = {
            "type": "new_order",
            "order_id": event.get("order_id"),
            "client": event.get("client"),
            "product_type": event.get("product_type"),  # 'hard', 'soft', 'print'
            "book_type": event.get("book_type"),        # 'Классическая', 'Премиум', 'Мини'
            "spreads": event.get("spreads", 0),
            "comment": event.get("comment", ""),
        }

        try:
            msg = json.dumps(data)
            print(f"[WS SEND -> CLIENT] {msg}")  # ✅ лог перед отправкой
            await self.send(text_data=msg)
            print(f"[WS SEND NEW_ORDER ✅] заказ #{data['order_id']} -> клиент {data['client']}")
        except Exception as e:
            print(f"[WS SEND NEW_ORDER ❌] ошибка при отправке: {e}")
