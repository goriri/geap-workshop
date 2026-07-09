import os
import logging
from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP
import sqlalchemy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("warehouse_mcp")

# Initialize FastMCP
mcp = FastMCP("warehouse_db", host="0.0.0.0")

# DB Connection settings
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "")
DB_NAME = os.environ.get("DB_NAME", "warehouse")
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Build the connection engine
def get_engine() -> sqlalchemy.engine.Engine:
    if INSTANCE_CONNECTION_NAME:
        # Connect via Cloud SQL Unix socket
        db_url = sqlalchemy.engine.url.URL.create(
            drivername="postgresql+pg8000",
            username=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            query={"unix_sock": f"/cloudsql/{INSTANCE_CONNECTION_NAME}/.s.PGSQL.5432"}
        )
    else:
        # Connect via TCP/IP
        db_url = sqlalchemy.engine.url.URL.create(
            drivername="postgresql+pg8000",
            username=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )
    return sqlalchemy.create_engine(db_url)

# Helper function to run query
def execute_query(query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text(query), params or {})
        # Commit if it's an update/insert
        conn.commit()
        if result.returns_rows:
            return [dict(row._mapping) for row in result]
        return []

@mcp.tool()
def list_inventory() -> str:
    """Lists all products currently in stock in the warehouse inventory, showing product ID, name, description, quantity, and price."""
    logger.info("Listing inventory")
    try:
        rows = execute_query("SELECT product_id, name, description, quantity, price FROM inventory ORDER BY product_id")
        if not rows:
            return "Inventory is empty."
        output = ["Warehouse Inventory:"]
        for row in rows:
            output.append(
                f"- ID: {row['product_id']} | {row['name']} | Qty: {row['quantity']} | Price: ${row['price']:.2f}\n"
                f"  Description: {row['description']}"
            )
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Error listing inventory: {e}")
        return f"Error listing inventory: {str(e)}"

@mcp.tool()
def get_product_stock(product_id: int) -> str:
    """Gets the stock level and details for a specific product ID."""
    logger.info(f"Getting stock for product ID: {product_id}")
    try:
        rows = execute_query(
            "SELECT product_id, name, quantity, price FROM inventory WHERE product_id = :product_id",
            {"product_id": product_id}
        )
        if not rows:
            return f"Product with ID {product_id} not found."
        row = rows[0]
        return f"Product: {row['name']} (ID: {row['product_id']}) | Current Stock: {row['quantity']} units | Price: ${row['price']:.2f}"
    except Exception as e:
        logger.error(f"Error getting stock: {e}")
        return f"Error getting stock: {str(e)}"

@mcp.tool()
def update_stock(product_id: int, quantity: int) -> str:
    """Updates the stock level of a specific product ID to a new quantity."""
    logger.info(f"Updating stock for product ID {product_id} to quantity {quantity}")
    try:
        # Check product exists
        exists = execute_query("SELECT name FROM inventory WHERE product_id = :product_id", {"product_id": product_id})
        if not exists:
            return f"Product with ID {product_id} not found in inventory."
        
        execute_query(
            "UPDATE inventory SET quantity = :quantity WHERE product_id = :product_id",
            {"product_id": product_id, "quantity": quantity}
        )
        return f"Successfully updated product '{exists[0]['name']}' (ID: {product_id}) stock to {quantity} units."
    except Exception as e:
        logger.error(f"Error updating stock: {e}")
        return f"Error updating stock: {str(e)}"

@mcp.tool()
def create_order(product_id: int, quantity: int, customer_name: str) -> str:
    """Creates a customer order for a product and automatically decrements the warehouse stock if inventory is available."""
    logger.info(f"Creating order for product ID {product_id}, qty {quantity}, customer '{customer_name}'")
    try:
        # Check stock
        rows = execute_query(
            "SELECT name, quantity FROM inventory WHERE product_id = :product_id",
            {"product_id": product_id}
        )
        if not rows:
            return f"Product with ID {product_id} not found."
        
        product = rows[0]
        if product["quantity"] < quantity:
            return (
                f"Insufficient stock for product '{product['name']}' (ID: {product_id}). "
                f"Requested: {quantity}, Available: {product['quantity']}."
            )
        
        # Insert order
        execute_query(
            "INSERT INTO orders (product_id, quantity, customer_name, status) "
            "VALUES (:product_id, :quantity, :customer_name, 'PENDING')",
            {"product_id": product_id, "quantity": quantity, "customer_name": customer_name}
        )
        
        # Decrement inventory stock
        new_qty = product["quantity"] - quantity
        execute_query(
            "UPDATE inventory SET quantity = :quantity WHERE product_id = :product_id",
            {"product_id": product_id, "quantity": new_qty}
        )
        
        return (
            f"Order successfully created for '{customer_name}'! "
            f"Ordered {quantity} units of '{product['name']}' (ID: {product_id}). "
            f"New stock level: {new_qty} units."
        )
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return f"Error creating order: {str(e)}"

# Start the Starlette Streamable HTTP app when run directly
if __name__ == "__main__":
    import uvicorn
    # Starlette app serving Streamable HTTP
    app = mcp.streamable_http_app()
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting MCP Streamable HTTP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
