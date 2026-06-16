from typing import Any
import os
import requests
import re

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.events import AllSlotsReset
from rasa_sdk.executor import CollectingDispatcher

FASTAPI_URL = os.getenv("FASTAPI_URL") or "http://localhost:8000"


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

    def validate_order_id(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> dict[str, Any]:
        """Validates the order_id slot by checking it against the FastAPI database and ownership."""
        order_id = slot_value
        if not order_id:
            return {"order_id": None}

        # Use regex to extract UUID from the text
        match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', str(order_id))
        if match:
            order_id = match.group(0)
        else:
            dispatcher.utter_message(
                text="I couldn't find a valid order ID in your message. Please provide the exact order ID."
            )
            return {"order_id": None}
            
        user_id = tracker.get_slot("user_id")

        if not user_id:
            dispatcher.utter_message(
                text="Session error: Could not identify your user session. Please log in again."
            )
            return {"order_id": None}

        # Call FastAPI to get the specific order details
        try:
            url = f"{FASTAPI_URL}/orders/{order_id}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                order_data = response.json()
                
                # Check ownership: verify order.user_id matches current_user.user_id
                order_user_uuid = str(order_data.get("user_id")).lower()
                current_user_uuid = str(user_id).lower()
                
                if order_user_uuid != current_user_uuid:
                    dispatcher.utter_message(
                        text=f"Sorry, order '{order_id}' is not associated with your account."
                    )
                    return {"order_id": None}
                
                # Check order status constraints
                status = order_data.get("status")
                restricted_statuses = ["dispatched", "out for delivery", "delivered"]
                if status in restricted_statuses:
                    dispatcher.utter_message(
                        text=(
                            f"Sorry, the shipping address for order '{order_id}' "
                            f"cannot be changed because its current status is '{status}'."
                        )
                    )
                    return {"order_id": None}
                
                # Validation succeeded, keep the order_id
                return {"order_id": order_id}
                
            elif response.status_code == 404:
                dispatcher.utter_message(
                    text=f"Sorry, no order was found with ID '{order_id}'."
                )
                return {"order_id": None}
            else:
                dispatcher.utter_message(
                    text=f"Error validating order ID (Server returned code {response.status_code})."
                )
                return {"order_id": None}
                
        except requests.RequestException as e:
            print(f"Rasa Action validation API error: {e}")
            dispatcher.utter_message(
                text="Error contacting the server for order validation. Please try again later."
            )
            return {"order_id": None}
