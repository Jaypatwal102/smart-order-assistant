OFFER_CLASSIFICATION_PROMPT = """Analyze the user's message in response to an offer.
Offer Type: {offer_type}
Recommended alternative products: {products_str}

Classify the user's decision into one of these categories:
- 'accept_alternative': The user wants to exchange the item for one of the recommended alternative products.
- 'accept_same': The user wants to proceed with a replacement for the SAME product they originally ordered.
- 'check_recommendation': The user wants to check out, view, or look at the recommended alternative products or agrees to check them out.
- 'decline': The user declines the alternatives/retention offer (e.g., they still want the refund, or they say no/cancel).
- 'unknown': If it's not clear or they asked something else.

If they chose or mentioned a specific alternative product from the recommended list, identify it and return its exact name in 'chosen_product'.

Examples:
1. User: "yes, I'd like the Daily Cleanser" -> decision='accept_alternative', chosen_product='Daily Cleanser'
2. User: "replace with same product" -> decision='accept_same', chosen_product=null
3. User: "Sure, let me check the Hydrating Face Wash" -> decision='check_recommendation', chosen_product='Hydrating Face Wash'
4. User: "no thanks, just refund it" -> decision='decline', chosen_product=null
5. User: "no" -> decision='decline', chosen_product=null
6. User: "Refund" -> decision='decline', chosen_product=null
"""
