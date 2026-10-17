from __future__ import annotations

from typing import Optional

from support_copilot.models import Entities, Order


class OrderStore:
    def __init__(self, orders: list[Order]):
        self._by_id = {order.id.upper(): order for order in orders}
        self._by_email: dict[str, list[Order]] = {}
        for order in orders:
            self._by_email.setdefault(order.email.lower(), []).append(order)

    def lookup(self, entities: Entities) -> Optional[Order]:
        if entities.order_id:
            found = self._by_id.get(entities.order_id.upper())
            if found:
                return found
        if entities.email:
            matches = self._by_email.get(entities.email.lower(), [])
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                return sorted(matches, key=lambda row: row.ordered_at, reverse=True)[0]
        if entities.serial:
            for order in self._by_id.values():
                if order.serial and order.serial.upper() == entities.serial.upper():
                    return order
        return None
