import json
import opensimplex
import os
import numpy as np
import cv2

def classify_biome(elevation: float, moisture: float) -> str:
    if elevation < -0.3: return "water"
    if elevation > 1.0: return "peaks"
    if elevation > 0.5: return "mountain"
    if moisture < -0.2: return "desert"
    if moisture > 0.3: return "forest"
    return "plains"

BIOME_COLORS_HEX = {
    "water":    0x1B7E9C,
    "mountain": 0x827B73,
    "peaks":    0xDDE6E2,
    "desert":   0xECD786,
    "forest":   0x088837,
    "plains":   0x3FCD32,
}

def generate_biome_grid(seed: int, cols: int = 17, rows: int = 17, scale: float = 0.15):
    opensimplex.seed(seed)

    center_x, center_y = cols / 2, rows / 2
    max_dist = max(center_x, center_y)

    grid = []
    for j in range(rows):
        row = []
        for i in range(cols):
            elevation = opensimplex.noise2(i * scale, j * scale)
            moisture = opensimplex.noise2(i * scale + 1000, j * scale + 1000)

            # Bias elevation upward near the center so it's less likely to be water
            dist = ((i - center_x) ** 2 + (j - center_y) ** 2) ** 0.5
            land_bias = 0.5 * (1 - min(dist / max_dist, 1))
            elevation += land_bias

            biome = classify_biome(elevation, moisture)
            row.append({"biome": biome, "color": BIOME_COLORS_HEX[biome]})
        grid.append(row)
    return grid

SPAWN_BIAS_RADIUS = 8
SPAWN_BIAS_STRENGTH = 0.5

def _spawn_bias(x: int, y: int) -> float:
    dist = (x ** 2 + y ** 2) ** 0.5
    if dist >= SPAWN_BIAS_RADIUS:
        return 0.0
    return SPAWN_BIAS_STRENGTH * (1 - dist / SPAWN_BIAS_RADIUS)

def generate_cell(seed: int, x: int, y: int, scale: float = 0.15) -> dict:
    opensimplex.seed(seed)
    elevation = opensimplex.noise2(x * scale, y * scale)
    moisture = opensimplex.noise2(x * scale + 1000, y * scale + 1000)
    elevation += _spawn_bias(x, y)

    biome = classify_biome(elevation, moisture)
    return {"biome": biome, "color": BIOME_COLORS_HEX[biome]}

class World:
    def __init__(self, seed: int, scale: float = 0.15):
        self.seed = seed
        self.scale = scale
        self.cells: dict[tuple[int, int], dict] = {}

    def get_cell(self, x: int, y: int) -> dict:
        key = (x, y)
        if key not in self.cells:
            self.cells[key] = generate_cell(self.seed, x, y, self.scale)
        return self.cells[key]

    def set_cell(self, x: int, y: int, biome: str) -> None:
        self.cells[(x, y)] = {"biome": biome, "color": BIOME_COLORS_HEX[biome]}

    def get_view_window(self, center_x: int, center_y: int, cols: int = 11, rows: int = 7):
        """
        Row 0 (top of the window) is the HIGHEST y — i.e. moving "up" (y+1)
        reveals new cells at the top and the window shifts down, matching
        the convention used for axis labels / other-player placement
        elsewhere (y = viewer_y + half_rows - row).
        """
        half_cols = cols // 2
        half_rows = rows // 2
        window = []
        for row_idx in range(rows):
            dy = half_rows - row_idx  # row 0 -> +half_rows (north), last row -> -half_rows (south)
            row = []
            for col_idx in range(cols):
                dx = col_idx - half_cols  # col 0 -> -half_cols (west), last col -> +half_cols (east)
                row.append(self.get_cell(center_x + dx, center_y + dy))
            window.append(row)
        return window

    def explored_count(self) -> int:
        return len(self.cells)

    def to_json(self) -> dict:
        return {f"{x},{y}": cell for (x, y), cell in self.cells.items()}

    @classmethod
    def from_json(cls, seed: int, data: dict, scale: float = 0.15) -> "World":
        world = cls(seed, scale)
        for key, cell in data.items():
            x_str, y_str = key.split(",")
            world.cells[(int(x_str), int(y_str))] = cell
        return world

def save_grid(grid, path: str) -> None:
    with open(path, "w") as f:
        json.dump(grid, f, indent=2)

def load_grid(path: str):
    with open(path, "r") as f:
        return json.load(f)

def set_cell(grid, row: int, col: int, biome: str) -> None:
    grid[row][col] = {"biome": biome, "color": BIOME_COLORS_HEX[biome]}

def print_grid(grid) -> None:
    for row in grid:
        print(" ".join(cell["biome"][0].upper() for cell in row))

def biome_counts(grid) -> dict:
    counts = {}
    for row in grid:
        for cell in row:
            counts[cell["biome"]] = counts.get(cell["biome"], 0) + 1
    return counts

WORLDS_DIR = "worlds"

def world_path(server_id: int) -> str:
    return os.path.join(WORLDS_DIR, f"{server_id}.json")

def save_world(world: "World", server_id: int) -> None:
    os.makedirs(WORLDS_DIR, exist_ok=True)
    with open(world_path(server_id), "w") as f:
        json.dump(world.to_json(), f)

def load_world(server_id: int, seed: int, scale: float = 0.15) -> "World":
    path = world_path(server_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        return World.from_json(seed, data, scale)
    return World(seed, scale)

def render_static_biome_grid(world: "World", center_x: int = 0, center_y: int = 0, output_path: str = "biome_grid.png", cols: int = 17, rows: int = 17, cell_size: int = 32) -> str:
    width = cols * cell_size
    height = rows * cell_size

    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (0, 0, 0)

    window = world.get_view_window(center_x, center_y, cols, rows)
    for row_index, row in enumerate(window):
        for col_index, cell in enumerate(row):
            x0 = col_index * cell_size
            y0 = row_index * cell_size
            x1 = x0 + cell_size - 1
            y1 = y0 + cell_size - 1
            color = cell["color"]
            b = (color >> 0) & 0xFF
            g = (color >> 8) & 0xFF
            r = (color >> 16) & 0xFF
            cv2.rectangle(image, (x0, y0), (x1, y1), (b, g, r), -1)

    cv2.imwrite(output_path, image)
    return output_path

if __name__ == "__main__":
    seed = 1550894780395823276
    size = 19  # odd number is easiest for a centered world
    world = World(seed, 0.15)

    rows = []
    for y in range(-(size // 2), (size // 2) + 1):
        row = []
        for x in range(-(size // 2), (size // 2) + 1):
            row.append(world.get_cell(x, y))
        rows.append(row)

    with open("_world.json", "w") as f:
        json.dump(rows, f)

    output = render_static_biome_grid(world, 0, 0, "biome_grid.png", cols=17, rows=17, cell_size=32)
    print(f"Updated image: {output}")