import pygame

pygame.init()

gameDisplay = pygame.display.set_mode([800,600])
pygame.display.set_caption('Laser Cat')



running = True
catLeft = pygame.image.load("cat.png")
catLeft.convert()
catRight = pygame.image.load("cat2.png")
catRight.convert()
catImage = catLeft
catX = 400
catY = 300

background = pygame.image.load("background1.jpg")
background = pygame.transform.scale(background, [800,600])
catXChange = 0
clock = pygame.time.Clock()
while running:
    pygame.display.flip()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                catXChange = -10
                catImage = catLeft
            if event.key == pygame.K_RIGHT:
                catXChange = 10
                catImage = catRight
        if event.type == pygame.KEYUP:
            catXChange = 0

    catX += catXChange
    gameDisplay.blit(background, [0,0])
    gameDisplay.blit(catImage, [catX,catY])

    clock.tick(60)

pygame.quit()
quit()