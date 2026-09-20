import io
import discord
import random
from discord import app_commands
from discord.ext import commands
import cv2
import numpy as np
import asyncio
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont
from collections import defaultdict
import queue
import threading
from biome_grid import World, load_world, save_world

proc = subprocess.Popen(
    ["./database/set_export.go.exe"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

_proc_lock = asyncio.Lock()
_stdout_queue: "queue.Queue[str]" = queue.Queue()

def _stdout_reader():
    """Runs forever in a background thread, pushing each line the Go process
    writes to stdout onto a queue. This is what lets us apply a timeout —
    readline() itself can't be interrupted once it's blocked."""
    for line in proc.stdout:
        _stdout_queue.put(line)
    # If we get here, the process's stdout closed (it exited/crashed).
    _stdout_queue.put(None)

_reader_thread = threading.Thread(target=_stdout_reader, daemon=True)
_reader_thread.start()

def _read_response(command: dict, timeout: float = 5.0) -> str:
    payload = json.dumps(command)
    proc.stdin.write(payload + "\n")
    proc.stdin.flush()

    try:
        line = _stdout_queue.get(timeout=timeout)
    except queue.Empty:
        raise TimeoutError(f"No response from database process for command: {command.get('command')}")

    if line is None:
        raise RuntimeError("Database process stdout closed unexpectedly (process may have crashed)")

    return line.strip()

async def _send_to_proc(command: dict) -> str:
    loop = asyncio.get_running_loop()
    async with _proc_lock:
        return await loop.run_in_executor(None, _read_response, command)

# database functions --------------------------

async def fetch_players(server_id: int) -> list:
    try:
        response = await _send_to_proc({"command": "fetch_players", "server_id": server_id})
        data = json.loads(response)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(e)
        return []

async def fetch_player(server_id: int, player_id: int) -> dict:
    try:
        response = await _send_to_proc({"command": "fetch_player", "server_id": server_id, "member_id": player_id})
        data = json.loads(response)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(e)
        return {}

async def add_player(server_id: int, player_id: int, pos_x: int, pos_y: int, display_name: str, color: int) -> None:
    await _send_to_proc({
        "command": "insert_player",
        "server_id": server_id,
        "member_id": player_id,
        "position_x": pos_x,
        "position_y": pos_y,
        "display_name": display_name,
        "color": color,
    })

# image helpers --------------------------------

def hex_to_rgb(hex_color: int, alpha: bool = True) -> tuple:
    """Convert a hex color (0xRRGGBB) to an RGB tuple."""
    r = (hex_color >> 16) & 0xFF
    g = (hex_color >> 8) & 0xFF
    b = hex_color & 0xFF
    return (r, g, b, 255) if alpha else (r, g, b)

def choose_text_color(rgb : tuple) -> tuple:
    r, g, b = rgb

    # Perceived brightness
    brightness = (r * 299 + g * 587 + b * 114) / 1000

    # Slightly biased toward white for teal/blue colors
    return (255, 255, 255) if brightness < 140 else (0, 0, 0)

def draw_all_text(image: np.ndarray, texts: list, font) -> np.ndarray:
    """
    Draw a batch of text overlays in a single PIL round-trip.
    texts: list of (text, position, color, alignment) tuples.
    """
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA), mode="RGBA")
    draw = ImageDraw.Draw(pil_image)
    for text, position, color, alignment in texts:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        if alignment == "center":
            position = (position[0] - text_width // 2, position[1])
        elif alignment == "right":
            position = (position[0] - text_width, position[1])
        draw.text(position, text, font=font, fill=color, align=alignment, stroke_width=12, stroke_fill=choose_text_color(color[0:3]))
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGRA)

def load_custom_font(font_path: str, size: int):
    return ImageFont.truetype(font_path, size)

# Button controls to move the player
class MoveButton(discord.ui.Button):
    def __init__(self, cog: "Player", label: str, direction: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.cog = cog
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        all_players = await fetch_players(interaction.guild.id)
        player_data = next(
            (p for p in all_players if isinstance(p, dict) and p.get("member_id") == interaction.user.id),
            None,
        )
        if not player_data:
            await interaction.followup.send("You are not registered in the game.", ephemeral=True)
            return

        if self.direction == "up":
            player_data["position_y"] += 1
        elif self.direction == "down":
            player_data["position_y"] -= 1
        elif self.direction == "left":
            player_data["position_x"] -= 1
        elif self.direction == "right":
            player_data["position_x"] += 1

        loop = asyncio.get_running_loop()
        world = self.cog._get_world(interaction.guild.id)

        update_task = asyncio.create_task(_send_to_proc({
            "command": "update_player",
            "server_id": interaction.guild.id,
            "member_id": interaction.user.id,
            "position_x": player_data["position_x"],
            "position_y": player_data["position_y"],
            "display_name": player_data.get("display_name", ""),
            "color": player_data.get("color", 0),
        }))
        build_task = loop.run_in_executor(None, self.cog._build_image, player_data, all_players, world)

        _, buffer = await asyncio.gather(update_task, build_task)
        save_world(world, interaction.guild.id)  # persist any newly-generated cells from this move

        file = discord.File(io.BytesIO(buffer), filename="image.png")
        await interaction.edit_original_response(attachments=[file], view=MoveView(self.cog))

class MoveView(discord.ui.View):
    def __init__(self, cog: "Player"):
        super().__init__()
        self.add_item(MoveButton(cog, "⬅️", "left"))
        self.add_item(MoveButton(cog, "⬆️", "up"))
        self.add_item(MoveButton(cog, "⬇️", "down"))
        self.add_item(MoveButton(cog, "➡️", "right"))

from biome_grid import World, load_world, save_world

class Player(commands.Cog):
    GRID_COLS = 11   # matches World.get_view_window's default cols
    GRID_ROWS = 7    # matches World.get_view_window's default rows
    CELL_SIZE = 250
    OFFSET = 150

    def __init__(self, bot):
        self.bot = bot
        self.font_path = "fonts/INCONSOLATA-BOLD.TTF"
        self.font001 = load_custom_font(self.font_path, 100)
        self.font_name = load_custom_font(self.font_path, 30)
        self._world_cache: dict[int, World] = {}  # in-memory cache, avoids reloading JSON every render

    def _get_world(self, server_id: int) -> World:
        if server_id not in self._world_cache:
            # seed off the server_id so each server gets its own stable world
            self._world_cache[server_id] = load_world(server_id, seed=server_id)
        return self._world_cache[server_id]

    def _cell_left(self, i: int) -> int:
        return self.OFFSET + i * self.CELL_SIZE

    def _cell_top(self, j: int) -> int:
        return self.OFFSET + j * self.CELL_SIZE

    def _cell_center(self, i: int, j: int) -> tuple:
        return (self._cell_left(i) + (self.CELL_SIZE) // 2,
                self._cell_top(j) + (self.CELL_SIZE) // 2)

    def _grid_index_for(self, pos_x, pos_y, viewer_x, viewer_y):
        i = (pos_x - viewer_x) + self.GRID_COLS // 2
        j = (viewer_y - pos_y) + self.GRID_ROWS // 2
        if 0 <= i < self.GRID_COLS and 0 <= j < self.GRID_ROWS:
            return i, j
        return None

    def _build_image(self, viewer_data: dict, all_players: list, world: World) -> np.ndarray:
        """CPU-heavy image build — runs off the event loop via run_in_executor."""
        viewer_x = viewer_data.get("position_x", 0)
        viewer_y = viewer_data.get("position_y", 0)

        # terrain: pull the visible window from the world, generating any
        # never-before-seen cells, and draw each one with its biome color
        window = world.get_view_window(viewer_x, viewer_y, cols=self.GRID_COLS, rows=self.GRID_ROWS)

        grid = np.zeros((self.GRID_ROWS * self.CELL_SIZE + self.OFFSET,
                          self.GRID_COLS * self.CELL_SIZE + self.OFFSET, 4), dtype=np.uint8)

        for j in range(self.GRID_ROWS):
            for i in range(self.GRID_COLS):
                cell = window[j][i]
                r = (cell["color"] >> 16) & 0xFF
                g = (cell["color"] >> 8) & 0xFF
                b = cell["color"] & 0xFF
                color = (b, g, r, 255)  # BGRA
                cv2.rectangle(
                    grid,
                    (self._cell_left(i), self._cell_top(j)),
                    (self._cell_left(i) + self.CELL_SIZE, self._cell_top(j) + self.CELL_SIZE),
                    color,
                    -1,
                )

        # axis labels
        texts = []
        for i in range(self.GRID_COLS):
            x = viewer_x + i - self.GRID_COLS // 2
            cx, _ = self._cell_center(i, 0)
            texts.append((str(x), (cx, self.OFFSET / 5), (255, 255, 255, 255), "center"))
        for j in range(self.GRID_ROWS):
            y = viewer_y + self.GRID_ROWS // 2 - j
            _, cy = self._cell_center(0, j)
            texts.append((str(y), (self.OFFSET / 2, cy), (255, 255, 255, 255), "center"))

        # other players
        for p in all_players:
            if not isinstance(p, dict) or p.get("member_id") == viewer_data.get("member_id"):
                continue
            idx = self._grid_index_for(p.get("position_x", 0), p.get("position_y", 0), viewer_x, viewer_y)
            if idx is None:
                continue
            cx, cy = self._cell_center(*idx)
            cv2.circle(grid, (cx, cy), 75, hex_to_rgb(p.get("color", 0)), -1)
            texts.append((p.get("display_name", "Unknown"), (cx, cy - 175),
                          hex_to_rgb(p.get("color", 0), alpha=False)[::-1], "center"))

        # viewer's own icon, always centered
        cx, cy = self._cell_center(self.GRID_COLS // 2, self.GRID_ROWS // 2)
        cv2.circle(grid, (cx, cy), 100, hex_to_rgb(viewer_data.get("color", 0)), -1)
        texts.append((viewer_data.get("display_name", "Unknown"), (cx, cy - 200),
                      hex_to_rgb(viewer_data.get("color", 0), alpha=False)[::-1], "center"))

        grid = draw_all_text(grid, texts, self.font001)
        success, buffer = cv2.imencode(".png", grid)
        return buffer

    @app_commands.command(name="play", description="Start game session!")
    async def play(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        players = await fetch_players(interaction.guild.id)
        player_ids = {p.get("member_id") for p in players if isinstance(p, dict)}

        if interaction.user.id not in player_ids:
            await add_player(interaction.guild.id, interaction.user.id,
                              random.randint(-3, 3), random.randint(-3, 3),
                              interaction.user.display_name, random.randint(0x000000, 0xFFFFFF))
            players = await fetch_players(interaction.guild.id)

        viewer_data = await fetch_player(interaction.guild.id, interaction.user.id)

        if viewer_data["display_name"] != interaction.user.display_name:
            viewer_data["display_name"] = interaction.user.display_name
            await _send_to_proc({
                "command": "update_player",
                "server_id": interaction.guild.id,
                "member_id": interaction.user.id,
                "position_x": viewer_data.get("position_x", 0),
                "position_y": viewer_data.get("position_y", 0),
                "display_name": interaction.user.display_name,
                "color": viewer_data.get("color", 0),
            })

        world = self._get_world(interaction.guild.id)
        loop = asyncio.get_running_loop()
        buffer = await loop.run_in_executor(None, self._build_image, viewer_data, players, world)
        save_world(world, interaction.guild.id)  # persist any newly-generated cells

        file = discord.File(io.BytesIO(buffer), filename="image.png")
        await interaction.edit_original_response(attachments=[file], view=MoveView(self))

async def setup(bot):
    await bot.add_cog(Player(bot))