import os
import re
import sys
import sqlalchemy

def main():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    prefix_env = os.environ.get("GEAP_PREFIX")
    if not prefix_env:
        print("Error: GEAP_PREFIX environment variable is not set.")
        sys.exit(1)
    username = re.split(r"[^a-zA-Z0-9]", prefix_env)[0]
    instance_name = os.environ.get("DB_INSTANCE", f"{username}-warehouse-db")
    region = os.environ.get("DB_REGION", "us-central1")
    db_user = os.environ.get("DB_USER", "postgres")
    db_pass = os.environ.get("DB_PASS", "super-secret-password")
    db_name = os.environ.get("DB_NAME", "warehouse")

    if not project:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable is not set.")
        sys.exit(1)

    instance_connection_string = f"{project}:{region}:{instance_name}"
    db_host = os.environ.get("DB_HOST")
    db_port = os.environ.get("DB_PORT", "5432")

    if db_host:
        print(f"Connecting to Database via TCP/IP: {db_host}:{db_port}...")
        db_url = sqlalchemy.engine.url.URL.create(
            drivername="postgresql+pg8000",
            username=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
            database=db_name
        )
        engine = sqlalchemy.create_engine(db_url)
        connector = None
    else:
        print(f"Connecting to Cloud SQL via Python Connector: {instance_connection_string}...")
        # Initialize Cloud SQL Connector
        from google.cloud.sql.connector import Connector, IPTypes
        connector = Connector()

        def getconn():
            return connector.connect(
                instance_connection_string,
                "pg8000",
                user=db_user,
                password=db_pass,
                db=db_name,
                ip_type=IPTypes.PUBLIC
            )

        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
        )


    try:
        with engine.connect() as conn:
            # Drop tables to ensure a clean slate for the workshop
            print("Dropping existing tables for a clean slate...")
            conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS orders;"))
            conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS inventory;"))
            conn.commit()

            # 1. Create tables
            print("Creating tables...")
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS inventory (
                    product_id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    quantity INT NOT NULL DEFAULT 0,
                    price DECIMAL(10, 2) NOT NULL
                )
            """))

            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id SERIAL PRIMARY KEY,
                    product_id INT NOT NULL REFERENCES inventory(product_id),
                    quantity INT NOT NULL,
                    customer_name VARCHAR(100) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

            # 2. Seed tables if empty
            rows = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM inventory")).scalar()
            if rows == 0:
                print("Seeding inventory data...")
                conn.execute(sqlalchemy.text("""
                    INSERT INTO inventory (name, description, quantity, price) VALUES
                    ('Laser Screwdriver', 'Multitool device that emits a concentrated light beam.', 50, 29.99),
                    ('Quantum Compactor', 'Shrinks raw materials to a fraction of their volume.', 10, 850.00),
                    ('Antigravity Boots', 'Provides user with gravitational neutralization.', 5, 1200.00),
                    ('Plasma Torch', 'High-temperature cutting tool for industrial materials.', 25, 89.50),
                    ('Hoverboard Cart', 'Automated cargo deck that hovers above the floor.', 15, 450.00)
                """))
                conn.commit()
                print("Successfully seeded inventory data!")
            else:
                print(f"Inventory table already has {rows} products. Skipping seeding.")

        print("Cloud SQL Database setup complete!")
    except Exception as e:
        print(f"Error during DB setup: {e}")
        sys.exit(1)
    finally:
        if connector:
            connector.close()

if __name__ == "__main__":
    main()
