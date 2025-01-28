from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.messages import InviteToChannelRequest
from telethon.tl.functions.messages import ApproveRequest
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables (API credentials)
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Define the bot client
from telethon import TelegramClient, events

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Store phone number and channel ID information
user_data = {}

# /start command handler
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond(
        "Welcome! Please enter your phone number (in international format) to authenticate.",
        buttons=[("Start Authentication", "auth_start")]
    )


# Handle the phone number collection
@bot.on(events.CallbackQuery(data='auth_start'))
async def auth_start(event):
    await event.respond(
        "Please enter your phone number (in international format, e.g., +123456789)."
    )


# Collect phone number and log in
@bot.on(events.NewMessage)
async def phone_number(event):
    if event.text.startswith('+'):
        phone_number = event.text
        try:
            # Start a session using the provided phone number
            client = TelegramClient(f"sessions/{phone_number}", API_ID, API_HASH)
            await client.connect()

            # Send verification code if needed
            if not await client.is_user_authorized():
                await client.send_code_request(phone_number)
                await event.respond("A verification code has been sent to your phone. Please enter it.")

                # Wait for the code input
                await event.client.wait_for(events.NewMessage(from_users=event.sender_id))
                
                code = event.text
                await client.sign_in(phone_number, code)

            user_data[event.sender_id] = {"phone_number": phone_number, "client": client}
            await event.respond(f"Successfully authenticated! Now, please provide the Channel ID.")
        except Exception as e:
            await event.respond(f"Error: {str(e)}")


# Collect channel ID
@bot.on(events.NewMessage(pattern=r'\d+'))
async def channel_id(event):
    user_id = event.sender_id
    if user_id in user_data and user_data[user_id].get("phone_number"):
        chat_id = int(event.text)

        try:
            # Get the chat object to validate the channel ID
            chat = await user_data[user_id]["client"].get_entity(chat_id)

            # Save channel ID
            user_data[user_id]["chat_id"] = chat.id

            # Ask the user to press the "Start" button to begin processing requests
            await event.respond(f"Channel ID set successfully! Press 'Start' to begin approving requests.",
                                buttons=[("Start", "start_requests")])

        except Exception as e:
            await event.respond(f"Invalid channel ID. Please provide a valid numeric channel ID.")


# Handle the start button to approve join requests
@bot.on(events.CallbackQuery(data='start_requests'))
async def start_requests(event):
    user_id = event.sender_id
    if user_id not in user_data or 'chat_id' not in user_data[user_id]:
        await event.respond("You must first authenticate and provide a channel ID.")
        return

    chat_id = user_data[user_id]["chat_id"]
    client = user_data[user_id]["client"]

    await event.respond("Starting to approve join requests...")

    # Start approving join requests in batches
    batch_size = 500  # Increased batch size to fetch more join requests at once
    approved_count = 0
    declined_count = 0

    try:
        while True:
            # Fetch requests in bulk
            requests = await client.get_chat_join_requests(chat_id, limit=batch_size)

            if not requests:
                break

            # Use async tasks to approve requests concurrently
            async def approve_request(request):
                nonlocal approved_count, declined_count
                try:
                    # Approve the request
                    await client.approve_chat_join_request(chat_id, request.user.id)
                    approved_count += 1
                    print(f"Approved {request.user.first_name}'s request.")
                except Exception as e:
                    # Handle exceptions (e.g., USER_CHANNELS_TOO_MUCH)
                    if "USER_CHANNELS_TOO_MUCH" in str(e):
                        try:
                            await client.decline_chat_join_request(chat_id, request.user.id)
                            declined_count += 1
                            print(f"Disapproved {request.user.first_name}'s request due to too many channels.")
                        except Exception as disapprove_error:
                            print(f"Error disapproving {request.user.first_name}: {disapprove_error}")
                    else:
                        print(f"Skipping {request.user.first_name}: {e}")

            # Use asyncio.gather to handle multiple requests concurrently (parallel)
            await asyncio.gather(*(approve_request(req) for req in requests))

            # Optional: Adjust sleep time based on your bot's rate limits (can be reduced)
            await asyncio.sleep(1)

        await event.respond(f"Finished processing requests. Approved: {approved_count}, Declined: {declined_count}")

    except Exception as e:
        await event.respond(f"Error occurred: {e}")


# Run the bot
if __name__ == "__main__":
    print("Bot is running...")
    bot.run_until_disconnected()
