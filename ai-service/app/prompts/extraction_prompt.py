EXTRACTION_PROMPT = """Extract any customer entities from the user message.
Specifically look for:
- order_id: A 36-character UUID string (e.g., '12345678-1234-1234-1234-123456789012')
- new_address: A new shipping/delivery address description.
- refund_reason: The reason the user wants a refund (if any).
- replacement_reason: The reason the user wants a replacement (if any).

If any entity is not present, return null for it.
"""
