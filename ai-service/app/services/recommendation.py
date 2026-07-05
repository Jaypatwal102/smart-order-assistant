import logging
import requests
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from app.llm.ollama import get_embeddings

logger = logging.getLogger(__name__)


def get_recommendations_service(product_name: str, limit: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch all active products from the server catalog, embed them in an
    InMemoryVectorStore, and perform a semantic search to recommend similar products.
    """
    try:
        url = "http://localhost:8000/products"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch products from catalog: {resp.status_code}")
            return []

        all_products = resp.json()
        if not all_products:
            logger.warning("Product catalog is empty.")
            return []

        # Find the target product to get its category/description if available
        target_product = None
        for p in all_products:
            if p["product_name"].lower() == product_name.lower():
                target_product = p
                break

        # Filter out the current product from recommendations index
        index_products = [
            p for p in all_products
            if p["product_name"].lower() != product_name.lower()
        ]

        # Enforce strict category match
        if target_product:
            index_products = [
                p for p in index_products
                if p["product_type"] == target_product["product_type"]
            ]

        if not index_products:
            return []

        # Prepare search query
        if target_product:
            search_query = f"Category: {target_product['product_type']}. Description: {target_product['description']}"
        else:
            search_query = product_name

        # Create documents
        docs = []
        for p in index_products:
            doc_text = f"Product Name: {p['product_name']}. Category: {p['product_type']}. Description: {p['description']}"
            docs.append(Document(
                page_content=doc_text,
                metadata={
                    "product_id": p["pid"],
                    "name": p["product_name"],
                    "category": p["product_type"],
                    "price": p["price"]
                }
            ))

        # Create vector store in memory and add documents
        embeddings = get_embeddings()
        vector_store = InMemoryVectorStore(embeddings)
        vector_store.add_documents(docs)

        # Perform similarity search with score
        results_with_score = vector_store.similarity_search_with_score(search_query, k=limit)

        # Format output and filter by threshold >= 0.75
        recommendations = []
        for doc, score in results_with_score:
            if score >= 0.75:
                recommendations.append({
                    "product_id": str(doc.metadata["product_id"]),
                    "name": doc.metadata["name"],
                    "category": str(doc.metadata["category"]),
                    "price": float(doc.metadata["price"])
                })

        return recommendations

    except Exception as e:
        logger.error(f"Error during recommendation lookup: {e}")
        return []
