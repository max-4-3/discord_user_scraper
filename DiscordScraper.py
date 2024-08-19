from asyncio import run, sleep
from random import uniform
from aiohttp import ClientSession
from datetime import datetime
from typing import Final
from fake_useragent import UserAgent
from os import getcwd, path
from time import perf_counter


class DiscordScraper:
    TOKEN: Final[str] = None
    HEADERS: Final[dict] = None
    ASSET_BASE: Final[str] = "https://cdn.discordapp.com"
    ASSET_BASE_TWO: Final[str] = "https://media.discordapp.net"
    PARAMS = {"with_mutual_friends": "true", "with_mutual_friends_count": "false", "with_mutual_guilds": "true"}

    def __init__(self):
        self.set_token()
        self.set_headers()

    def set_token(self) -> None:
        while not self.TOKEN:
            token = input("Enter Your Discord Token:\n").strip()
            if not token:
                self.error("Token Not Given!")
            elif token.isnumeric():
                self.error("Token Can't be numeric!")
            elif len(token.split(".")) != 3:
                self.error(f"{token} is not valid discord token!")
            else:
                self.TOKEN = token

    def set_headers(self) -> None:
        if not self.HEADERS:
            self.HEADERS = {
                "Authorization": self.TOKEN,
                "User-Agent": UserAgent().random
            }

    async def gather_friends(self, session: ClientSession) -> list | None:
        url = "https://discord.com/api/v9/users/@me/channels"
        async with session.get(url, headers=self.HEADERS) as response:
            if response.status != 200:
                self.error(f"Unable to get users (friends or DM channels): {response.status}")
                return None
            j = await response.json()
            r_value = []
            for users in j:
                for user in users.get("recipients", [{}]):
                    if not user.get("bot", False):
                        r_value.append(user)
            return r_value

    async def scrap_user(self, session: ClientSession, user_id: int | str) -> dict | None:
        url = f"https://discord.com/api/v9/users/{user_id}/profile"
        async with session.get(url, headers=self.HEADERS, params=self.PARAMS) as response:
            if response.status == 429:
                retry_after = await response.json()
                retry_after = retry_after.get("retry_after", uniform(2, 4)) * 2
                self.error(f"Hit rate limit on user {user_id}, Retrying After: {retry_after}")
                await sleep(retry_after)
                return await self.scrap_user(session, user_id)

            if response.status != 200:
                self.error(f"Unable to get user: {response.status}")
                return None
            
            return await response.json()

    async def scrap_users(self, session: ClientSession, user_list: list[dict]) -> list[dict] | None:
        if not user_list:
            self.error("User List is Zero!")
            return None

        scraped_users = []
        users_len = len(user_list)

        for idx, user in enumerate(user_list, start=1):
            user_id = user.get("id")
            user_name = user.get("global_name", user.get("username"))
            self.info(f"Scrapping user {user_name if user_name else user_id} [{idx}/{users_len}]...")
            full_user = await self.scrap_user(session, user_id)
            if not full_user:
                self.error(f"Unable to Scrap user: {user_name if user_name else user_id}")
                continue
            self.success(f"Succefully Scrapped User : {user_name if user_name else user_id} [{users_len - idx} remaining]")
            scraped_users.append(full_user)
        await sleep(uniform(1, 2))

        return scraped_users

    async def parse_users(self, scraped_users: list[dict]) -> list | None:
        if not scraped_users:
            self.error("User List is Zero!")
            return None

        parsed_users = []
        users_len = len(scraped_users)

        for idx, user in enumerate(scraped_users, start=1):
            user_id = user.get("user", {}).get("id")
            user_name = user.get("user", {}).get("username")
            user_full_name = user.get("user", {}).get("global_name", f"No Global Name for {user_name}!")

            self.info(f"Scrapping {user_name} [{user_id}] [{idx}/{users_len}]...")
            user_bio = user.get("user", {}).get("bio", "No bio!")
            user_pronouns = user.get("user_profile", {}).get("pronouns", "No pronouns")

            user_mutual_friends = self.get_mutual_friends(user)
            user_mutual_guilds = self.get_mutual_guilds(user)

            user_legacy = user.get("legacy_username", "No Legacy Username")

            user_avatar = self.get_asset_url("avatars", user.get("user").get("avatar"), user_id)
            user_banner = self.get_asset_url("banners", user.get("user").get("banner"), user_id)

            user_connected_accounts = self.get_connected_accounts(user)

            user_nitro_since = self.get_nitro_since(user)
            user_nitro = self.get_nitro_type(user)

            main_info = f'''
-------------------------{user_name}-------------------------
Name: {user_name}
ID: {user_id}
Full Name: {user_full_name}
Pronouns: {user_pronouns}
Bio: {user_bio}
Nitro: {user_nitro}
Nitro Since: {user_nitro_since}
Avatar: {user_avatar}
Banner: {user_banner}
Legacy Username: {user_legacy}
-------------------------Mutual Friends-------------------------
Total Mutual Friends: {len(user_mutual_friends) if isinstance(user_mutual_friends, list) else 0}
Mutual Friends:
----------------------
{'\n----------------------\n'.join(user_mutual_friends).expandtabs(4) if isinstance(user_mutual_friends, list) else "None"}

-------------------------Mutual Guilds-------------------------
Total Mutual Guilds: {len(user_mutual_guilds) if isinstance(user_mutual_guilds, list) else 0}
Mutual Guilds:
----------------------
{'\n----------------------\n'.join(user_mutual_guilds).expandtabs(4) if isinstance(user_mutual_guilds, list) else "None"}

-------------------------Connected Accounts-------------------------
Total Connected Accounts: {len(user_connected_accounts) if isinstance(user_connected_accounts, list) else 0}
Connected Accounts:
----------------------
{'\n----------------------\n'.join(user_connected_accounts).expandtabs(4) if isinstance(user_connected_accounts, list) else "None"}

-parsed by maxim__4_7 <3
'''
            parsed_users.append(main_info)
            self.success("Successfully Scrapped!")

        self.success(f"Successfully Scraped {len(parsed_users)} out of {len(scraped_users)} users.")
        return parsed_users

    def get_mutual_friends(self, user: dict) -> list:
        mutual_friends = user.get("mutual_friends", [])
        if mutual_friends:
            return [f"\tID: {m_friend.get('id')}\n\tName: {m_friend.get('global_name', m_friend.get('username', 'No Name'))}" for m_friend in mutual_friends]
        return ["No Mutual Friends"]

    def get_mutual_guilds(self, user: dict) -> list:
        mutual_guilds = user.get("mutual_guilds", [])
        if mutual_guilds:
            return [f"\tID: {m_guild.get("id")}" for m_guild in mutual_guilds]
        return ["No Mutual Guilds"]

    def get_asset_url(self, asset_type: str, asset_id: str, user_id: str) -> str:
        if asset_id:
            fmt = ".gif" if asset_id.startswith("a_") else ".png"
            size = 2048
            return f"{self.ASSET_BASE}/{asset_type}/{user_id}/{asset_id}{fmt}?size={size}"
        return f"No {asset_type.capitalize()}"

    def get_connected_accounts(self, user: dict) -> list:
        connected_accounts = user.get("connected_accounts", [])
        if connected_accounts:
            return [f"\tPlatform: {u_ca.get('type').upper()}\n\tName: {u_ca.get('name')}" for u_ca in connected_accounts]
        return ["No Connected Accounts"]

    def get_nitro_since(self, user: dict) -> str:
        premium_since = user.get("premium_since")
        if premium_since:
            try:
                return datetime.fromisoformat(premium_since).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return "Not A Nitro Holder"

    def get_nitro_type(self, user: dict) -> str:
        premium_type = user.get("premium_type", 0)
        if premium_type == 1:
            return "Nitro Classic"
        elif premium_type == 2:
            return "Nitro"
        return "User Doesn't Have Any Nitro!"

    async def run(self) -> None:
        start = perf_counter()
        async with ClientSession() as session:
            friend_list = await self.gather_friends(session)
            if not friend_list:
                return
            user_list = await self.scrap_users(session, friend_list)
            if not user_list:
                return
            parsed_list = await self.parse_users(user_list)
            if not parsed_list:
                return
            output = "\n".join(parsed_list)
            file_path = path.join(getcwd(), 'ScrapedUsers.txt')
            self.info(f"writing parsed users info to: \"{file_path}\"...")
            with open(file_path, 'w', encoding="utf-8", errors="ignore") as file:
                file.write(output)
            end = perf_counter()
            self.success(f"Succesfully Sceaped Users in {end - start:.2f}s")

    @staticmethod
    def error(s: str) -> None:
        print(f"[-] {s.capitalize()}")

    @staticmethod
    def success(s: str) -> None:
        print(f"[+] {s.capitalize()}")

    @staticmethod
    def info(s: str) -> None:
        print(f"[?] {s.capitalize()}")


if __name__ == "__main__":
    scraper = DiscordScraper()
    try:
        run(scraper.run())
    except KeyboardInterrupt:
        print("Exiting Scraper...")
        exit(0)
