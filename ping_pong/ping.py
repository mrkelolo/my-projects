import pygame
import random

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Game window
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Ping Pong Game")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 74)
small_font = pygame.font.Font(None, 36)

# Paddle class
class Paddle(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((10, 100))
        self.image.fill(WHITE)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.speed = 6

    def move_up(self):
        if self.rect.top > 0:
            self.rect.y -= self.speed

    def move_down(self):
        if self.rect.bottom < SCREEN_HEIGHT:
            self.rect.y += self.speed

    def draw(self, surface):
        surface.blit(self.image, self.rect)

# Ball class
class Ball(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((10, 10))
        self.image.fill(WHITE)
        self.rect = self.image.get_rect()
        self.reset()
        self.speed_x = random.choice([-5, 5])
        self.speed_y = random.choice([-5, 5])

    def reset(self):
        self.rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.speed_x = random.choice([-5, 5])
        self.speed_y = random.choice([-3, 3])

    def update(self):
        self.rect.x += self.speed_x
        self.rect.y += self.speed_y

        # Bounce off top and bottom walls
        if self.rect.top <= 0 or self.rect.bottom >= SCREEN_HEIGHT:
            self.speed_y = -self.speed_y

        # Check if ball is out of bounds
        if self.rect.left <= 0 or self.rect.right >= SCREEN_WIDTH:
            return True  # Ball is out of bounds
        return False

    def draw(self, surface):
        surface.blit(self.image, self.rect)

# Main game loop
def main():
    running = True
    left_paddle = Paddle(20, SCREEN_HEIGHT // 2 - 50)
    right_paddle = Paddle(SCREEN_WIDTH - 30, SCREEN_HEIGHT // 2 - 50)
    ball = Ball()
    
    left_score = 0
    right_score = 0

    while running:
        clock.tick(60)  # 60 FPS

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Input handling
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            left_paddle.move_up()
        if keys[pygame.K_s]:
            left_paddle.move_down()
        if keys[pygame.K_UP]:
            right_paddle.move_up()
        if keys[pygame.K_DOWN]:
            right_paddle.move_down()

        # Update ball position
        out_of_bounds = ball.update()

        # Ball collision with paddles
        if ball.rect.colliderect(left_paddle.rect) and ball.speed_x < 0:
            ball.speed_x = -ball.speed_x
            ball.speed_y += random.choice([-2, 2])
        elif ball.rect.colliderect(right_paddle.rect) and ball.speed_x > 0:
            ball.speed_x = -ball.speed_x
            ball.speed_y += random.choice([-2, 2])

        # Score update
        if out_of_bounds:
            if ball.rect.left <= 0:
                right_score += 1
            else:
                left_score += 1
            ball.reset()

        # Rendering
        screen.fill(BLACK)

        # Draw paddles and ball
        left_paddle.draw(screen)
        right_paddle.draw(screen)
        ball.draw(screen)

        # Draw scores
        left_score_text = font.render(str(left_score), True, WHITE)
        right_score_text = font.render(str(right_score), True, WHITE)
        screen.blit(left_score_text, (SCREEN_WIDTH // 4, 50))
        screen.blit(right_score_text, (3 * SCREEN_WIDTH // 4 - 50, 50))

        # Draw center line
        for y in range(0, SCREEN_HEIGHT, 10):
            pygame.draw.line(screen, WHITE, (SCREEN_WIDTH // 2, y), (SCREEN_WIDTH // 2, y + 5), 2)

        # Draw instructions
        instructions = small_font.render("W/S - Left Paddle | UP/DOWN - Right Paddle", True, WHITE)
        screen.blit(instructions, (30, SCREEN_HEIGHT - 40))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
