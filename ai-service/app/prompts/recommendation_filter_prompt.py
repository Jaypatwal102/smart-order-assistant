RECOMMENDATION_FILTER_PROMPT = """Analyze if a recommended alternative product is a reasonable replacement or exchange for the original product.
A replacement must be of the same general type of product (e.g., face wash to cleanser is reasonable; earbuds to keyboard, mouse, washing machine, or power bank is NOT reasonable).

Original Product: {original_product}
Recommended Alternative: {alternative_product}

Output a JSON with:
- reasonable: boolean (true if the alternative is a valid replacement of the same product type/category, false if it is a completely different type of product)

Only output the JSON.
"""
