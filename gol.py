
import pygame
import numpy as np
import random

# Определяем размеры окна и размеры клеточного поля
WIDTH, HEIGHT = 800, 600
ROWS, COLS = 80, 60
CELL_SIZE = min(WIDTH // COLS, HEIGHT // ROWS)

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)

# Инициализация поля
grid = np.zeros((ROWS, COLS), dtype=int)

# Функция для инициализации окна Pygame
def initialize_window():
    pygame.init()
    pygame.display.set_caption('Игра Жизнь Конвея')
    return pygame.display.set_mode((WIDTH, HEIGHT))

# Функция для отрисовки сетки
def draw_grid(surface):
    surface.fill(WHITE)
    for row in range(ROWS):
        for col in range(COLS):
            color = GREEN if grid[row][col] == 1 else BLACK
            pygame.draw.rect(surface, color, (col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE))
    pygame.display.flip()

# Функция для создания начального состояния случайным образом
def randomize_grid():
    global grid
    grid = np.random.choice([0, 1], size=(ROWS, COLS), p=[0.5, 0.5])

# Функция для расчёта следующего поколения по правилам "Жизни"
def next_generation():
    global grid
    new_grid = np.copy(grid)
    for row in range(ROWS):
        for col in range(COLS):
            neighbors = count_neighbors(grid, row, col)
            if grid[row][col] == 1 and (neighbors < 2 or neighbors > 3):
                new_grid[row][col] = 0
            elif grid[row][col] == 0 and neighbors == 3:
                new_grid[row][col] = 1
    grid = new_grid

# Функция для подсчёта соседей клетки
def count_neighbors(grid, row, col):
    count = 0
    for i in range(-1, 2):
        for j in range(-1, 2):
            if i == 0 and j == 0:
                continue
            if 0 <= row + i < ROWS and 0 <= col + j < COLS:
                count += grid[row + i][col + j]
    return count

# Основной цикл программы
def main():
    surface = initialize_window()
    running = True
    paused = False
    fps = 10  # Число поколений в секунду
    clock = pygame.time.Clock()

    randomize_grid()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    randomize_grid()

        if not paused:
            next_generation()
            draw_grid(surface)

        clock.tick(fps)

    pygame.quit()

if __name__ == "__main__":
    main()
