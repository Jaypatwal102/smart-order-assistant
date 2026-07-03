import re

with open('app/nodes/processors.py', 'r') as f:
    content = f.read()

pattern1 = re.compile(r'    try:\n        url = f"http://localhost:8000/orders/\{order_id\}"\n        resp = requests.get\(url, timeout=5\)\n        \n        if resp.status_code == 404:\n            return \{"order_id": None, "bot_response": f"Sorry, no order was found with ID \'\{order_id\}\'\. Please try again\."\}\n        elif resp.status_code != 200:\n            return \{"order_id": None, "bot_response": "Error validating your order\. Please try again later\."\}\n            \n        order_data = resp.json\(\)\n        \n        if str\(order_data.get\("uid"\)\)\.lower\(\) != str\(uid\)\.lower\(\):\n            return \{"order_id": None, "bot_response": f"Sorry, order \'\{order_id\}\' is not associated with your account\.", "intent": "completed", "sub_intents": \[\]\}\n            \n        product_name = order_data.get\("product_name"\)\n        status = order_data.get\("status", ""\)')

repl1 = '''    try:
        enrich_res = fetch_enriched_order(order_id, uid)
        if enrich_res["error"]:
            return {"order_id": None, "bot_response": enrich_res["error"], "intent": enrich_res.get("intent", "unknown"), "sub_intents": []}
        order_data = enrich_res["order_data"]
        product_name = order_data.get("product_name")
        status = order_data.get("status", "")'''

content, count1 = pattern1.subn(repl1, content)
print(f'Replaced block 1/2: {count1}')

# There is a third block for process_refund
pattern3 = re.compile(r'    try:\n        url = f"http://localhost:8000/orders/\{order_id\}"\n        resp = requests.get\(url, timeout=5\)\n        \n        if resp.status_code == 404:\n            return \{"order_id": None, "bot_response": f"Sorry, no order was found with ID \'\{order_id\}\'\. Please try again\."\}\n        elif resp.status_code != 200:\n            return \{"order_id": None, "bot_response": "Error validating your order\. Please try again later\."\}\n            \n        order_data = resp.json\(\)\n        \n        if str\(order_data.get\("uid"\)\)\.lower\(\) != str\(uid\)\.lower\(\):\n            return \{"order_id": None, "bot_response": f"Sorry, order \'\{order_id\}\' is not associated with your account\.", "intent": "completed", "sub_intents": \[\]\}\n            \n        ordered_at_raw = order_data.get\("ordered_at"\)\n        delivered_at_raw = order_data.get\("delivered_at"\)')

repl3 = '''    try:
        enrich_res = fetch_enriched_order(order_id, uid)
        if enrich_res["error"]:
            return {"order_id": None, "bot_response": enrich_res["error"], "intent": enrich_res.get("intent", "unknown"), "sub_intents": []}
        order_data = enrich_res["order_data"]
        
        ordered_at_raw = order_data.get("ordered_at")
        delivered_at_raw = order_data.get("delivered_at")'''

content, count3 = pattern3.subn(repl3, content)
print(f'Replaced block 3: {count3}')

with open('app/nodes/processors.py', 'w') as f:
    f.write(content)
