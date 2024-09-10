import os
import discord
from discord.ext import commands
import asyncio
import requests
from datetime import datetime
import colorama
from colorama import Fore, Style
import json
import sys
import random

colorama.init(autoreset=True)
os.system('title Stocker')

def print_with_timestamp(message, color=Fore.WHITE):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{color}[{current_time}] {message}{Style.RESET_ALL}")

def fancy_print(message, color=Fore.WHITE):
    styles = [Style.BRIGHT, Style.DIM, Style.NORMAL]
    style = random.choice(styles)
    print(f"{color}{style}{message}{Style.RESET_ALL}")

def print_initial_messages():
    fancy_print("Starting Stocker Bot...", Fore.MAGENTA)
    fancy_print("Loading configuration...", Fore.CYAN)
    fancy_print("Setting up environment...", Fore.YELLOW)

print_initial_messages()

def fix_config(config_data):
    if not all(key in config_data for key in ["ToReply", "webhook", "servers"]):
        raise ValueError("Config JSON missing required keys")
    for server_id, server_info in config_data["servers"].items():
        if "name" not in server_info:
            guild_name = discord.utils.get(bot.guilds, id=int(server_id)).name
            server_info["name"] = guild_name
    return config_data

try:
    with open("config.json", "r", encoding="utf-8") as config_file:
        data = json.load(config_file)
        data = fix_config(data)
except (json.JSONDecodeError, ValueError) as e:
    print_with_timestamp(f"Error loading config.json: {e}", Fore.RED)
    sys.exit(1)
except discord.errors.HTTPException as e:
    print_with_timestamp(f"Error accessing Discord server: {e}", Fore.RED)
    sys.exit(1)

REPLY_MESSAGE = data['ToReply']
WEBHOOK_URL = data['webhook']

REPLY_IN_DMS = input(f"{Fore.CYAN}Do you want to reply to DMs? (yes/no): {Style.RESET_ALL}").strip().lower() == 'yes'

stock_counter = 0
tokens_count = 0
servers_count = len(data['servers'])
channels_count = sum(len(server_info["channels"]) for server_info in data['servers'].values())
channel_delays = {}
channel_counters = {}
server_messages = {}
default_message = ""

fancy_print(f"Number of servers: {servers_count}", Fore.GREEN)
fancy_print(f"Number of channels: {channels_count}", Fore.GREEN)

custom_messages = input(f"{Fore.CYAN}Do you want to use different stock messages for each server? (yes/no): {Style.RESET_ALL}").strip().lower() == 'yes'

if custom_messages:
    for guild_id, server_info in data['servers'].items():
        server_name = server_info["name"]
        message_file_path = input(f"{Fore.CYAN}Enter the path for the stock message file for guild {server_name} (ID: {guild_id}): {Style.RESET_ALL}").strip()
        try:
            with open(message_file_path, 'r', encoding='utf-8') as message_file:
                server_messages[guild_id] = message_file.read().strip()
        except FileNotFoundError:
            print_with_timestamp(f"Error: Message file {message_file_path} not found for guild {server_name} (ID: {guild_id})", Fore.RED)
            sys.exit(1)
else:
    default_message_file = input(f"{Fore.CYAN}Enter the path for the default stock message file: {Style.RESET_ALL}").strip()
    try:
        with open(default_message_file, 'r', encoding='utf-8') as message_file:
            default_message = message_file.read().strip()
    except FileNotFoundError:
        print_with_timestamp(f"Error: Default message file {default_message_file} not found", Fore.RED)
        sys.exit(1)

for guild_id, server_info in data['servers'].items():
    server_name = server_info["name"]
    for channel_name in server_info['channels']:
        delay = input(f"{Fore.CYAN}Delay for channel {channel_name} in {server_name} (ID: {guild_id}) (in seconds): {Style.RESET_ALL}").strip()
        channel_delays[channel_name] = int(delay)
        channel_counters[channel_name] = 0

async def send_stock_message(bot, guild_id, channel_name, message, delay):
    global stock_counter
    while True:
        guild = bot.get_guild(int(guild_id))
        if guild is None:
            print_with_timestamp(f'Guild not found: {guild_id}', Fore.RED)
            return

        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel is None:
            print_with_timestamp(f'Channel not found: {channel_name} in guild: {guild.name}', Fore.RED)
            return

        try:
            await channel.send(message)
            stock_counter += 1
            channel_counters[channel_name] += 1
            print_with_timestamp(f"[+] Stock sent, channel: {channel.name}, guild: {guild.name}. Total stocks sent: {stock_counter}. Stocks sent to {channel_name}: {channel_counters[channel_name]:02d}", Fore.GREEN)

            webhook_data = {
                "content": None,
                "embeds": [
                    {
                        "title": "Stock Sent",
                        "description": f"Message successfully sent to channel: **{channel.name}** in guild: **{guild.name}**",
                        "color": 3066993,
                        "timestamp": datetime.now().isoformat(),
                        "footer": {
                            "text": "Stock Bot Notification",
                        },
                    }
                ]
            }
            response = requests.post(WEBHOOK_URL, json=webhook_data)

            if response.status_code == 204:
                print_with_timestamp(f"Webhook notification sent successfully.", Fore.BLUE)
            else:
                print_with_timestamp(f"Failed to send webhook notification. Status code: {response.status_code}", Fore.RED)
        except discord.errors.HTTPException as e:
            print_with_timestamp(f"Failed to send message: {e}", Fore.RED)

        await asyncio.sleep(delay)

async def stocker(token, servers):
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.dm_messages = True

    bot = commands.Bot(command_prefix=".", self_bot=True, intents=intents)

    @bot.event
    async def on_ready():
        fancy_print(f"Bot logged in as {bot.user}", Fore.CYAN)
        tasks = []
        for guild_id, server_info in servers.items():
            message = server_messages.get(guild_id, default_message)
            for channel_name in server_info['channels']:
                delay = channel_delays[channel_name]
                tasks.append(send_stock_message(bot, guild_id, channel_name, message, delay))
        await asyncio.gather(*tasks)

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        if isinstance(message.channel, discord.DMChannel) and REPLY_IN_DMS:
            await message.channel.send(REPLY_MESSAGE)
            print_with_timestamp(f"Replied to DM from {message.author}", Fore.YELLOW)

    try:
        await bot.start(token, bot=False)
    except discord.errors.LoginFailure:
        print_with_timestamp(f"Token Invalid: {token}", Fore.RED)
        pass

async def main():
    global tokens_count
    tokens = []

    try:
        with open("tokens.txt", "r") as token_file:
            tokens = token_file.read().splitlines()
    except FileNotFoundError:
        print_with_timestamp("Error: tokens.txt file not found", Fore.RED)
        sys.exit(1)

    if not tokens:
        print_with_timestamp("Error: No tokens found in tokens.txt", Fore.RED)
        sys.exit(1)

    tokens_count = len(tokens)
    fancy_print(f"Number of tokens: {tokens_count}", Fore.GREEN)

    tasks = []

    for token in tokens:
        tasks.append(stocker(token, data["servers"]))

    await asyncio.gather(*tasks)

asyncio.run(main())
