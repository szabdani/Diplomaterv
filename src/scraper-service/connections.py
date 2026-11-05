import os
import time
import pika
import pika.exceptions
import pymongo
from pathlib import Path
from dotenv import load_dotenv

# Resolve paths: <repo_root>
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=REPO_ROOT / ".env")

# Auto-detect execution environment
IS_DOCKER = os.path.exists("/.dockerenv") or os.getenv("RUNNING_IN_DOCKER") == "true"
DEFAULT_DB_HOST = "mongodb" if IS_DOCKER else "localhost"
DEFAULT_RABBITMQ_HOST = "rabbitmq" if IS_DOCKER else "localhost"

def get_mongo_connection():
    """
    Initializes and returns the MongoDB client and the raw_payloads collection.
    """
    MONGO_USER = os.getenv("MONGO_USER")
    MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
    MONGO_HOST = os.getenv("MONGO_HOST", DEFAULT_DB_HOST)
    MONGO_PORT = os.getenv("MONGO_PORT", "27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "football_raw_db")
    MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "raw_payloads")

    MONGO_URI = os.getenv(
        "MONGO_URI",
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/?authSource=admin"
    )

    # Connect to MongoDB (raw-db)
    mongo_client = pymongo.MongoClient(MONGO_URI)
    raw_db = mongo_client[MONGO_DB_NAME]
    raw_collection = raw_db[MONGO_COLLECTION_NAME]

    return mongo_client, raw_collection

def get_rabbitmq_connection():
    """
    Initializes and returns the RabbitMQ connection, channel, and queue name.
    Includes a retry loop to wait for the broker to boot inside Docker Compose.
    """
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", DEFAULT_RABBITMQ_HOST)
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "data_processing_queue")

    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    rabbit_params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )

    rabbit_conn = None
    max_retries = 10
    for attempt in range(max_retries):
        try:
            print(f"[CONNECT] ({attempt+1}/{max_retries}) Attempting to connect to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}...")
            rabbit_conn = pika.BlockingConnection(rabbit_params)
            break  # Connection successful, exit the loop
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[UNAVAILABLE] Attempt {attempt + 1}/{max_retries}: RabbitMQ connection failed: {e}")
            time.sleep(5)  # Wait before retrying

    if not rabbit_conn:
        raise Exception("[ERROR] Failed to connect to RabbitMQ after maximum retries.")

    channel = rabbit_conn.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    return rabbit_conn, channel, RABBITMQ_QUEUE