import os
import random
import time
import uuid
from azure.storage.queue import QueueClient, BinaryBase64EncodePolicy

CONNECTION_STRING = os.environ["STORAGE_CONNECTION_STRING"]
QUEUES = ["myqueue", "myqueue-oneagent"]

SAMPLE_MESSAGES = [
    "Order received: order_id={id}, item=Widget, qty={qty}",
    "User login: user_id={id}, region=UK",
    "Payment processed: payment_id={id}, amount=£{amount}",
    "Shipment dispatched: shipment_id={id}, destination=London",
    "Inventory update: product_id={id}, stock={qty}",
]

def generate_message() -> str:
    template = random.choice(SAMPLE_MESSAGES)
    return template.format(
        id=str(uuid.uuid4())[:8],
        qty=random.randint(1, 100),
        amount=round(random.uniform(5.0, 500.0), 2),
    )

def send_messages(queue_name: str, count: int = 5) -> None:
    client = QueueClient.from_connection_string(
        CONNECTION_STRING,
        queue_name,
        message_encode_policy=BinaryBase64EncodePolicy(),
    )
    print(f"\nSending {count} messages to '{queue_name}'...")
    for i in range(count):
        message = f"[{queue_name.upper()}] {generate_message()}"
        client.send_message(message.encode("utf-8"))
        print(f"  [{i + 1}] {message}")

if __name__ == "__main__":
    print("Sending messages every 5 seconds. Press Ctrl+C to stop.\n")
    try:
        while True:
            for queue in QUEUES:
                send_messages(queue, count=1)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopped.")
