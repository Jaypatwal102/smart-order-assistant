from typing import Any
import requests

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.events import AllSlotsReset
from rasa_sdk.executor import CollectingDispatcher

FASTAPI_URL = "http://localhost:8000"


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

        # Call the FastAPI order-update endpoint
        updated = False
        error_msg = None
        try:
            url = f"{FASTAPI_URL}/orders/{order_id}/address"
            response = requests.put(url, json={"new_address": new_address}, timeout=5)
            if response.status_code == 200:
                updated = True
                api_response = response.json()
                dispatcher.utter_message(text=api_response.get("message"))
            else:
                error_msg = f"Server returned status code {response.status_code}."
        except requests.RequestException as e:
            error_msg = str(e)

        if not updated:
            # Fallback to local mock response if server is unreachable
            dispatcher.utter_message(
                text=(
                    f"Received your request to update order {order_id} "
                    f"with the new address: {new_address} (Mocked Update)."
                )
            )
            if error_msg:
                print(f"FastAPI Update Error: {error_msg}. Using local fallback.")

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


class ValidateShippingAddressUpdateForm(FormValidationAction):
    def name(self) -> str:
        return "validate_shipping_address_update_form"

    def validate_product_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> dict[str, Any]:
        """Validates the product_name slot by checking user's orders list."""
        product_name = slot_value
        user_id = tracker.get_slot("user_id") or tracker.sender_id

        # 1. Fetch user orders from FastAPI
        orders = []
        try:
            url = f"{FASTAPI_URL}/orders"
            response = requests.get(url, params={"user_id": user_id}, timeout=5)
            if response.status_code == 200:
                orders = response.json()
        except requests.RequestException:
            print("FastAPI server unreachable. Falling back to local mock list.")

        # 2. Local mock list if server is unreachable
        if not orders:
            if user_id == "user_1":
                orders = [
                    {"order_id": "ORD11111", "user_id": "user_1", "status": "pending", "product_name": "moisturizer"},
                    {"order_id": "ORD12345", "user_id": "user_1", "status": "dispatched", "product_name": "serum"},
                    {"order_id": "ORD56789", "user_id": "user_1", "status": "out for delivery", "product_name": "toner"},
                    {"order_id": "ORD88888", "user_id": "user_1", "status": "delivered", "product_name": "sunscreen"}
                ]
            elif user_id == "user_2":
                orders = [
                    {"order_id": "ORD22222", "user_id": "user_2", "status": "pending", "product_name": "cleanser"}
                ]
            elif user_id in ["default", "guest", "admin"]:
                orders = [
                    {"order_id": "ORD_MOCK_1", "user_id": user_id, "status": "pending", "product_name": "moisturizer"},
                    {"order_id": "ORD_MOCK_2", "user_id": user_id, "status": "dispatched", "product_name": "serum"}
                ]

        # 3. Find matching product in user's orders
        matched_order = None
        p_name_lower = product_name.lower()
        for order in orders:
            if order.get("product_name") and p_name_lower in order.get("product_name").lower():
                matched_order = order
                break

        # 4. If no product matches
        if not matched_order:
            dispatcher.utter_message(
                text=f"Sorry, no product with the name '{product_name}' was found in your orders."
            )
            return {"product_name": None}

        # 5. Check order status constraints
        status = matched_order.get("status")
        order_id = matched_order.get("order_id")
        matched_product_name = matched_order.get("product_name")
        restricted_statuses = ["dispatched", "out for delivery", "delivered"]
        if status in restricted_statuses:
            dispatcher.utter_message(
                text=(
                    f"Sorry, the shipping address for order '{order_id}' ({matched_product_name}) "
                    f"cannot be changed because its current status is '{status}'."
                )
            )
            return {"product_name": None}

        # 6. Store matches programmatically so prompt templates can use them,
        # Rasa will automatically proceed to ask product_confirmed next
        return {
            "product_name": matched_product_name,
            "order_id": order_id
        }

    def validate_product_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> dict[str, Any]:
        """Handles confirmation logic for the product name."""
        if slot_value is True:
            # User confirmed, proceed to address slot
            return {"product_confirmed": True}
        else:
            # User denied, prompt again for product name and reset slots
            dispatcher.utter_message(
                text="Okay, please let me know the correct product name."
            )
            return {
                "product_name": None,
                "order_id": None,
                "product_confirmed": None
            }
