import io
import discord
from discord import app_commands
from discord.ext import commands
import cv2
import numpy as np

class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Start game session!")
    async def play(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        grid = np.zeros((3500, 5500, 4), dtype=np.uint8)
        color = (255, 255, 255, 32)

        for i in range(13):
            for j in range(7):
                cv2.rectangle(grid, (10+i*500, 10+j*500), ((i+1)*500-10, (j+1)*500-10), color, -1)

        success, buffer = cv2.imencode(".png", grid)
        file = discord.File(io.BytesIO(buffer), filename="image.png")
        await interaction.followup.send(file=file)

async def setup(bot):
    await bot.add_cog(Player(bot))
