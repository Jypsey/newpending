from pyrogram import Client, filters
import asyncio
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

app = Client("userbot", api_id=API_ID, api_hash=API_HASH)

# Persistent chat ID store
CHAT_ID_FILE = "chat_id_store.txt"


def save_chat_id(chat_id):
    with open(CHAT_ID_FILE, "w") as f:
        f.write(str(chat_id))


def load_chat_id():
    try:
        with open(CHAT_ID_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


@app.on_message(filters.me & filters.text)
async def handle_message(client, message):
    if message.text.startswith("/setchat"):
        try:
            chat_id = int(message.text.split(" ", 1)[1])
            save_chat_id(chat_id)
            await message.reply(f"Chat ID (group/channel) set to: {chat_id}")
        except (IndexError, ValueError):
            await message.reply("Invalid format! Use: `/setchat <chat_id>`")

    elif message.text == "/approveall":
        chat_id = load_chat_id()
        if not chat_id:
            await message.reply("Chat ID is not set. Use `/setchat <chat_id>` first.")
            return

        await message.reply("Approving all pending join requests...")
        try:
            start_time = time.time()
            batch_size = 500  # Adjust the batch size
            approved_count = 0
            declined_count = 0

            while True:
                requests = []
                async for request in client.get_chat_join_requests(chat_id, limit=batch_size):
                    requests.append(request)

                if not requests:
                    break

                # Define a task to approve each request concurrently
                async def approve_request(request):
                    nonlocal approved_count, declined_count
                    try:
                        # Approve the request
                        await client.approve_chat_join_request(chat_id, request.user.id)
                        print(f"Approved {request.user.first_name}'s request.")
                        approved_count += 1
                    except Exception as e:
                        # Check for the 'USER_CHANNELS_TOO_MUCH' error and disapprove the request
                        if 'USER_CHANNELS_TOO_MUCH' in str(e):
                            try:
                                await client.decline_chat_join_request(chat_id, request.user.id)
                                print(f"Disapproved {request.user.first_name}'s request due to too many channels.")
                                declined_count += 1
                            except Exception as disapprove_error:
                                print(f"Error disapproving {request.user.first_name}: {disapprove_error}")
                        else:
                            print(f"Skipping {request.user.first_name}: {e}")

                # Use asyncio.gather to process requests in parallel
                await asyncio.gather(*(approve_request(req) for req in requests))

                # Log progress
                print(f"Batch processed: Approved {approved_count} requests, Declined {declined_count} requests.")
                await asyncio.sleep(2)  # Rate limiting pause between batches

            # Log how long it took to process
            end_time = time.time()
            elapsed_time = end_time - start_time
            await message.reply(f"Processed all requests in {elapsed_time:.2f} seconds. Approved: {approved_count}, Declined: {declined_count}.")

        except Exception as e:
            await message.reply(f"Error: {e}")


if __name__ == "__main__":
    print("Userbot is running...")
    app.run()
