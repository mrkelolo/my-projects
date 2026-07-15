import os
import random
import sys

import pygame

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
BACKGROUND_IMAGE = os.path.join(BASE_PATH, "background.jpg")
MINER_IMAGE = os.path.join(BASE_PATH, "miner.png")

GRAVITY = 0.5
JUMP_STRENGTH = -10
PIPE_SPEED = 3
PIPE_GAP = 180
PIPE_SPACING = 1600
PIPE_WIDTH = 80
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 500

pygame.init()
pygame.display.set_caption("Flappy Miner")

if not os.path.exists(BACKGROUND_IMAGE) or not os.path.exists(MINER_IMAGE):
    print("Missing background.jpg or miner.png in the same folder as flappy_miner.py")
    pygame.quit()
    sys.exit(1)

background = pygame.image.load(BACKGROUND_IMAGE)
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
width, height = screen.get_size()
background = pygame.transform.scale(background, (width, height)).convert()

miner_surface = pygame.image.load(MINER_IMAGE).convert_alpha()
miner_width = max(24, width // 8)
miner_height = max(24, height // 10)
miner_surface = pygame.transform.smoothscale(miner_surface, (miner_width, miner_height))
miner_rect = miner_surface.get_rect(center=(width // 4, height // 2))

font = pygame.font.SysFont(None, 36)
clock = pygame.time.Clock()

pipes = []
score = 0
velocity_y = 0
running = True
is_game_over = False
last_pipe_time = pygame.time.get_ticks()


def create_pipe():
    gap_y = random.randint(120, height - 120 - PIPE_GAP)
    top_pipe = pygame.Rect(width, 0, PIPE_WIDTH, gap_y)
    bottom_pipe = pygame.Rect(width, gap_y + PIPE_GAP, PIPE_WIDTH, height - gap_y - PIPE_GAP)
    return top_pipe, bottom_pipe


def reset_game():
    global pipes, score, velocity_y, is_game_over, miner_rect, last_pipe_time
    pipes = []
    score = 0
    velocity_y = 0
    is_game_over = False
    miner_rect.center = (width // 4, height // 2)
    last_pipe_time = pygame.time.get_ticks()


def draw_text(text, color, x, y):
    surface = font.render(text, True, color)
    screen.blit(surface, (x, y))


while running:
    dt = clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE or event.key == pygame.K_UP:
                if not is_game_over:
                    velocity_y = JUMP_STRENGTH
                else:
                    reset_game()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if not is_game_over:
                    velocity_y = JUMP_STRENGTH
                else:
                    reset_game()

    if not is_game_over:
        current_time = pygame.time.get_ticks()
        if current_time - last_pipe_time > PIPE_SPACING:
            pipes.extend(create_pipe())
            last_pipe_time = current_time

        velocity_y += GRAVITY
        miner_rect.y += int(velocity_y)

        if miner_rect.top < 0:
            miner_rect.top = 0
            velocity_y = 0
        if miner_rect.bottom > height:
            miner_rect.bottom = height
            is_game_over = True

        for pipe in pipes:
            pipe.x -= PIPE_SPEED

        pipes = [pipe for pipe in pipes if pipe.right > 0]

        for pipe in pipes:
            if miner_rect.colliderect(pipe):
                is_game_over = True
                break

        for pipe in pipes:
            if pipe.centerx == miner_rect.centerx:
                score += 0.5
        score_display = int(score)
    else:
        score_display = int(score)

    screen.blit(background, (0, 0))

    for pipe in pipes:
        pygame.draw.rect(screen, (60, 60, 60), pipe)
        pygame.draw.rect(screen, (40, 40, 40), pipe.inflate(-8, -8))

    screen.blit(miner_surface, miner_rect)
    draw_text(f"Score: {score_display}", (255, 255, 255), 10, 10)

    if is_game_over:
        draw_text("Game Over", (255, 60, 60), width // 2 - 80, height // 2 - 30)
        draw_text("Press SPACE or click to restart", (255, 255, 255), width // 2 - 170, height // 2 + 10)

    pygame.display.flip()

pygame.quit()
