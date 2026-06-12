from typing import Any

from rasa_sdk import Action, Tracker
from rasa_sdk.events import AllSlotsReset
from rasa_sdk.executor import CollectingDispatcher


class ActionSubmitShippingUpdate(Action):
    def name(self) -> str:
        return "action_submit_shipping_update"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        order_id = tracker.get_slot("order_id")
        new_address = tracker.get_slot("new_address")

        if not order_id or not new_address:
            dispatcher.utter_message(
                text="I need both the order ID and new address before updating."
            )
            return []

        # Call the FastAPI order-update endpoint here when it is available.
        dispatcher.utter_message(
            text=(
                f"Received your request to update order {order_id} "
                f"with the new address: {new_address}."
            )
        )

        return [AllSlotsReset()]


class ActionCancelShippingUpdate(Action):
    def name(self) -> str:
        return "action_cancel_shipping_update"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        dispatcher.utter_message(response="utter_cancel")
        return [AllSlotsReset()]
