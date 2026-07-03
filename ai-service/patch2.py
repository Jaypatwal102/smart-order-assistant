import re

with open('app/nodes/processors.py', 'r') as f:
    content = f.read()

pattern3 = re.compile(r'    try:\n        url = f"http://localhost:8000/orders/\{order_id\}"\n        resp = requests.get\(url, timeout=5\)\n        \n        if resp.status_code == 404:\n            return \{\n                "order_id": None, \n                "bot_response": f"Sorry, no order was found with ID \'\{order_id\}\'\. Please try again\.",\n                "refund_reason": refund_reason\n            \}\n        elif resp.status_code != 200:\n            return \{\n                "order_id": None, \n                "bot_response": "Error validating your order\. Please try again later\.",\n                "refund_reason": refund_reason\n            \}\n            \n        order_data = resp.json\(\)\n        \n        if str\(order_data.get\("uid"\)\)\.lower\(\) != str\(uid\)\.lower\(\):\n            return \{\n                "order_id": None, \n                "bot_response": f"Sorry, order \'\{order_id\}\' is not associated with your account\.", \n                "intent": "completed", \n                "sub_intents": \[\],\n                "refund_reason": refund_reason\n            \}\n            \n        # Read the refund policy')

repl3 = '''    try:
        enrich_res = fetch_enriched_order(order_id, uid)
        if enrich_res["error"]:
            return {
                "order_id": None, 
                "bot_response": enrich_res["error"], 
                "intent": enrich_res.get("intent", "unknown"), 
                "sub_intents": [],
                "refund_reason": refund_reason
            }
        order_data = enrich_res["order_data"]
            
        # Read the refund policy'''

content, count3 = pattern3.subn(repl3, content)
print(f'Replaced block 3: {count3}')

if count3 > 0:
    with open('app/nodes/processors.py', 'w') as f:
        f.write(content)
