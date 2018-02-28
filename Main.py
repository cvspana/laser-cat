import pygame

pygame.init()

gameDisplay = pygame.display.set_mode([800,600])
pygame.display.set_caption('Laser Cat')



running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

pygame.quit()
quit()