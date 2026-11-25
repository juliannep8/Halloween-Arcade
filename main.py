import pygame
import random
import heapq
import math
import sys
import asyncio

pygame.init()

GRID_SIZE = 21
CELL_SIZE = 28
HUD_HEIGHT = 70
WIDTH = GRID_SIZE * CELL_SIZE
HEIGHT = GRID_SIZE * CELL_SIZE + HUD_HEIGHT

COLOR_SKY = (15, 23, 42)
COLOR_FLOOR = (46, 125, 50) 
COLOR_WALL = (27, 94, 32)   
COLOR_HOUSE = (121, 85, 72)  
COLOR_HOUSE_ROOF = (93, 64, 55) 
COLOR_PLAYER = (220, 38, 38) 
COLOR_ENEMY = (148, 163, 184)  
COLOR_CANDY = (250, 204, 21)
COLOR_PATH = (56, 189, 248)  
COLOR_TEXT = (248, 250, 252)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Neighborhood Horror")
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 16, bold=True)
small_font = pygame.font.SysFont("arial", 13)


def generate_neighborhood_maze(size):
    maze = [[1] * size for _ in range(size)]
    stack = [(1, 1)]
    maze[1][1] = 0

    #DFS
    while stack:
        cx, cy = stack[-1]
        neighbors = []
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            nx, ny = cx + dx, cy + dy
            if 0 < nx < size - 1 and 0 < ny < size - 1 and maze[ny][nx] == 1:
                neighbors.append((nx, ny))

        if neighbors:
            nx, ny = random.choice(neighbors)
            maze[cy + (ny - cy) // 2][cx + (nx - cx) // 2] = 0
            maze[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()

    #Houses
    houses = []
    attempts = 0
    while len(houses) < 4 and attempts < 100:
        attempts += 1
        
        hx = random.randint(3, size - 6)
        hy = random.randint(3, size - 6)

        overlap = False
        for (ex, ey) in houses:
            if abs(hx - ex) < 5 and abs(hy - ey) < 5:
                overlap = True
                break
        if overlap:
            continue

        houses.append((hx, hy))

        for ry in range(hy - 1, hy + 4):
            for rx in range(hx - 1, hx + 4):
                if 0 < rx < size - 1 and 0 < ry < size - 1:
                    maze[ry][rx] = 0

        for ry in range(hy, hy + 3):
            for rx in range(hx, hx + 3):
                maze[ry][rx] = 2

    maze[1][1] = 0
    maze[size - 2][size - 2] = 0
    return maze, houses


def manhattan_distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def euclidean_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def get_astar_path(maze, start, target):
    if start == target:
        return [start]

    frontier = []
    heapq.heappush(frontier, (0, start))
    came_from = {start: None}
    cost_so_far = {start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == target:
            break

        cx, cy = current
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and maze[ny][nx] == 0:
                next_node = (nx, ny)
                new_cost = cost_so_far[current] + 1
                if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                    cost_so_far[next_node] = new_cost
                    priority = new_cost + manhattan_distance(target, next_node)
                    heapq.heappush(frontier, (priority, next_node))
                    came_from[next_node] = current

    if target not in came_from:
        return []

    path = []
    curr = target
    while curr is not None:
        path.append(curr)
        curr = came_from[curr]
    path.reverse()
    return path

def spawn_candies(maze, count, forbidden_positions):
    valid_cells = [
        (x, y)
        for y in range(GRID_SIZE)
        for x in range(GRID_SIZE)
        if maze[y][x] == 0 and (x, y) not in forbidden_positions
    ]
    return set(random.sample(valid_cells, min(count, len(valid_cells))))

def reset_game():
    maze, houses = generate_neighborhood_maze(GRID_SIZE)
    player_start = (1, 1)
    enemy_start = (GRID_SIZE - 2, GRID_SIZE - 2)
    candies = spawn_candies(maze, 15, {player_start, enemy_start})
    return {
        "maze": maze,
        "houses": houses,
        "player_start": list(player_start),
        "player_pos": list(player_start),
        "enemy_pos": list(enemy_start),
        "candies": candies,
        "player_score": 0,
        "enemy_score": 0,
        "stun_until": 0,
        "enemy_state": "COLLECT_CANDY", #fsM
        "enemy_target": None,
        "enemy_path": [],
        "debug_mode": True,
        "game_over": False,
        "winner": ""
    }

async def main():
    state = reset_game()

    PLAYER_MOVE_COOLDOWN = 130  
    ENEMY_MOVE_COOLDOWN = 180 
    STUN_DURATION = 3000  
    AGGRO_RADIUS = 5.0 

    last_player_move = 0
    last_enemy_move = 0

    
    running = True
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_h:  # Debug
                    state["debug_mode"] = not state["debug_mode"]
                elif event.key == pygame.K_r:  # Restart 
                    state = reset_game()

        if not state["game_over"]:
            is_stunned = now < state["stun_until"]
            if not is_stunned and (now - last_player_move > PLAYER_MOVE_COOLDOWN):
                keys = pygame.key.get_pressed()
                dx, dy = 0, 0
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    dy = -1
                elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    dy = 1
                elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    dx = -1
                elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    dx = 1

                if dx != 0 or dy != 0:
                    nx = state["player_pos"][0] + dx
                    ny = state["player_pos"][1] + dy
                    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and state["maze"][ny][nx] == 0:
                        state["player_pos"] = [nx, ny]
                        last_player_move = now

                        # candy
                        pt = tuple(state["player_pos"])
                        if pt in state["candies"]:
                            state["candies"].remove(pt)
                            state["player_score"] += 1

            if now - last_enemy_move > ENEMY_MOVE_COOLDOWN:
                p_tuple = tuple(state["player_pos"])
                e_tuple = tuple(state["enemy_pos"])
                dist_to_player = euclidean_distance(e_tuple, p_tuple)

                if dist_to_player <= AGGRO_RADIUS and not is_stunned:
                    state["enemy_state"] = "CHASE_PLAYER"
                    state["enemy_target"] = p_tuple
                elif len(state["candies"]) > 0:
                    state["enemy_state"] = "COLLECT_CANDY"
                    closest_candy = min(
                        state["candies"],
                        key=lambda c: manhattan_distance(e_tuple, c)
                    )
                    state["enemy_target"] = closest_candy
                else:
                    state["enemy_state"] = "PATROL"
                    state["enemy_target"] = (GRID_SIZE - 2, GRID_SIZE - 2)

                if state["enemy_target"] is not None:
                    state["enemy_path"] = get_astar_path(
                        state["maze"], e_tuple, state["enemy_target"]
                    )


                if len(state["enemy_path"]) > 1:
                    state["enemy_pos"] = list(state["enemy_path"][1])
                    last_enemy_move = now

                    et = tuple(state["enemy_pos"])
                    if et in state["candies"]:
                        state["candies"].remove(et)
                        state["enemy_score"] += 1


            if state["player_pos"] == state["enemy_pos"] and not is_stunned:
                state["player_pos"] = list(state["player_start"])
                state["stun_until"] = now + STUN_DURATION
                state["enemy_state"] = "COLLECT_CANDY"

            # w/L
            if len(state["candies"]) == 0:
                state["game_over"] = True
                if state["player_score"] > state["enemy_score"]:
                    state["winner"] = "Player Wins!"
                elif state["enemy_score"] > state["player_score"]:
                    state["winner"] = "Enemy Wins!"
                else:
                    state["winner"] = "It's a Tie!"

        screen.fill(COLOR_SKY)

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                rect = pygame.Rect(
                    col * CELL_SIZE, HUD_HEIGHT + row * CELL_SIZE, CELL_SIZE, CELL_SIZE
                )
                tile = state["maze"][row][col]
                if tile == 0:
                    pygame.draw.rect(screen, COLOR_FLOOR, rect)
                elif tile == 1:
                    pygame.draw.rect(screen, COLOR_WALL, rect)
                elif tile == 2:
                    pygame.draw.rect(screen, COLOR_HOUSE, rect)

        for (hx, hy) in state["houses"]:
            house_rect = pygame.Rect(
                hx * CELL_SIZE, HUD_HEIGHT + hy * CELL_SIZE, CELL_SIZE * 3, CELL_SIZE * 3
            )
            pygame.draw.rect(screen, COLOR_HOUSE_ROOF, house_rect, width=3)

        for (cx, cy) in state["candies"]: #15
            center = (
                cx * CELL_SIZE + CELL_SIZE // 2,
                HUD_HEIGHT + cy * CELL_SIZE + CELL_SIZE // 2
            )
            pygame.draw.circle(screen, COLOR_CANDY, center, CELL_SIZE // 4)

        if state["debug_mode"]:
            enemy_center = (
                state["enemy_pos"][0] * CELL_SIZE + CELL_SIZE // 2,
                HUD_HEIGHT + state["enemy_pos"][1] * CELL_SIZE + CELL_SIZE // 2
            )
            pygame.draw.circle(
                screen, COLOR_ENEMY, enemy_center, int(AGGRO_RADIUS * CELL_SIZE), width=1
            )

            for step in state["enemy_path"]:
                if list(step) != state["enemy_pos"]:
                    px = step[0] * CELL_SIZE + CELL_SIZE // 2
                    py = HUD_HEIGHT + step[1] * CELL_SIZE + CELL_SIZE // 2
                    pygame.draw.circle(screen, COLOR_PATH, (px, py), CELL_SIZE // 6)

        p_rect = pygame.Rect(
            state["player_pos"][0] * CELL_SIZE + 4,
            HUD_HEIGHT + state["player_pos"][1] * CELL_SIZE + 4,
            CELL_SIZE - 8,
            CELL_SIZE - 8
        )
        pygame.draw.rect(screen, COLOR_PLAYER, p_rect, border_radius=4)

        e_rect = pygame.Rect(
            state["enemy_pos"][0] * CELL_SIZE + 4,
            HUD_HEIGHT + state["enemy_pos"][1] * CELL_SIZE + 4,
            CELL_SIZE - 8,
            CELL_SIZE - 8
        )
        pygame.draw.rect(screen, COLOR_ENEMY, e_rect, border_radius=4)

        score_txt = font.render(
            f"Player (Red): {state['player_score']}   |   Enemy (Grey): {state['enemy_score']}   |   Candies Left: {len(state['candies'])}",
            True,
            COLOR_TEXT
        )
        screen.blit(score_txt, (12, 10))

        if now < state["stun_until"]:
            rem = (state["stun_until"] - now) / 1000.0
            status_str = f"CAUGHT! Respawned at start. Cooldown: {rem:.1f}s"
        elif state["game_over"]:
            status_str = f"GAME OVER — {state['winner']} Press [R] to Restart."
        else:
            status_str = f"Enemy FSM: {state['enemy_state']} | Target: {state['enemy_target']} | [H] Debug [R] Reset"

        status_txt = small_font.render(status_str, True, COLOR_PATH)
        screen.blit(status_txt, (12, 40))

        pygame.display.flip()
        clock.tick(30)
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    asyncio.run(main())
