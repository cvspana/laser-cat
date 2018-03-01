""" 
 Show how to use a sprite backed by a graphic.
  
 Sample Python/Pygame Programs
 Simpson College Computer Science
 http://programarcadegames.com/
 http://simpson.edu/computer-science/
 
 Explanation video: http://youtu.be/vRB_983kUMc
"""
 
import pygame
import random
pygame.init()
size = (800, 600)
screen = pygame.display.set_mode(size)
pygame.display.init()
# Define some colors
BLACK    = (   0,   0,   0)
WHITE    = ( 255, 255, 255)
GREEN    = (   0, 255,   0)
RED      = ( 255,   0,   0)
BLUE = (0,0,255)
bg = pygame.image.load("Background1.jpg").convert_alpha()
bg = pygame.transform.scale(bg, [800,600])
class Cat(pygame.sprite.Sprite):
     catRight = pygame.image.load("cat.png").convert_alpha()
     catLeft = pygame.image.load("cat2.png").convert_alpha()
     def __init__(self):

         pygame.sprite.Sprite.__init__(self)
         self.image = self.catRight
         self.rect = self.image.get_rect()
         self.rect.x = 620
         self.rect.y = 430
         self.image.set_colorkey(WHITE)
     def update(self):
         if pright == True:
             self.rect.x += 7
         if pleft == True:
             self.rect.x -= 7
         if pup == True:
             self.rect.y -= 7
         if pdown == True:
             self.rect.y += 7
         if press == True:
            self.image =  self.catLeft
         if press == False:
            self.image = self.catRight
         if self.rect.x >= 734:
            self.rect.x = 734
         if self.rect.x <= 0:
            self.rect.x = 0  
         if self.rect.y <= 0:
            self.rect.y = 0
         if self.rect.y >= 553:
            self.rect.y = 553

            
             
         
             
class Coin(pygame.sprite.Sprite):
    coinPic = pygame.image.load("coin_Custom_Custom.png").convert_alpha()
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image = self.coinPic
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(765)
        self.rect.y = random.randrange(565)

class Laser(pygame.sprite.Sprite):
    velocity = 5+random.randrange(5)
    laserPic = pygame.image.load("laser.bmp").convert_alpha()
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image = self.laserPic
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(790)
        self.rect.y = random.randrange(100)
        self.rect.y *= -1
    def update(self):
        self.rect.y += self.velocity
        if self.rect.y >= 600:
            self.rect.y = random.randrange(100)
            self.rect.y *= -1
            self.rect.x = random.randrange(790)
            self.velocity = 5+random.randrange(5)


        




 
pygame.display.set_caption("Laser Cat")
 
#Loop until the user clicks the close button.
done = False
 
# Used to manage how fast the screen updates
clock = pygame.time.Clock()
#pygame.mixer.music.load('music.mp3')
#pygame.mixer.music.play(-1)




all_sprites = pygame.sprite.Group()
coin_list = pygame.sprite.Group()
lasers = pygame.sprite.Group()
cat = Cat()
coin = Coin()
pright = False
pleft = False
pup = False
pdown = False
press = False
score = 0
internalClock = 0

introS = True

text = "Hit Space"
font = pygame.font.SysFont('wingdings', 40)
def introScreen():
    screen.fill(WHITE)
    intro = font.render(str(text), True, BLACK)
    screen.blit(intro,[350,300])

def clearScreen():
    all_sprites.remove(all_sprites)
    lasers.remove(lasers)
    coin_list.remove(coin_list)

def start():
    coin_list.add(coin)
    all_sprites.add(coin)
    all_sprites.add(cat)
    for i in range(7):
        laser = Laser()
        all_sprites.add(laser)
        lasers.add(laser)
# -------- Main Program Loop -----------
while not done:
    pygame.display.set_caption("Laser Cat" +str(clock.get_fps()))
    # --- Main event loop
    for event in pygame.event.get(): # User did something
        if event.type == pygame.QUIT: # If user clicked close
            done = True # Flag that we are done so we exit this loop

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                introS = False
            if event.key == pygame.K_LEFT:
                pleft = True
                press = False
            elif event.key == pygame.K_RIGHT:   
                pright = True
                press = True
            elif event.key == pygame.K_UP:
                pup = True
            elif event.key == pygame.K_DOWN:
                pdown = True
            elif event.key == pygame.K_ESCAPE:
                done = True
        elif event.type == pygame.KEYUP:

            if event.key == pygame.K_LEFT:
                pleft = False
            elif event.key == pygame.K_RIGHT: 
                pright = False
            elif event.key == pygame.K_UP:
                pup = False
            elif event.key == pygame.K_DOWN:
                pdown = False

    if introS == True:
        introScreen()
        clearScreen()
        internalClock = 0
    else:
        #   --- Game logic should go heredf
        if (internalClock ==0):
            start()

        cat.update()
        coin.update()
    
        lasers.update()





        if (internalClock%1800 == 0):
            laser = Laser()
            all_sprites.add(laser)
            lasers.add(laser)
    
        hitcoin = pygame.sprite.spritecollide(cat, coin_list, False)
    
        if len(hitcoin) >= 1:
            coin.rect.x = random.randrange(765)
            coin.rect.y =100+ random.randrange(465)
            score += 1

        hitlaser = pygame.sprite.spritecollide(cat, lasers, False)
        if len(hitlaser) >= 1:
            introS = True
            print(score)

    # --- Drawing code should go here
     
    # First, clear the screen to white. Don't put other drawing commands
    # above this, or they will be erased with this command.
        screen.fill(WHITE)
    
    
        # font = pygame.font.SysFont('arial', 40)

        #text = font.render(str(score),True,WHITE)
        screen.blit(bg, [0,0])
        #screen.blit(text, [10,10])
        all_sprites.draw(screen)
        # --- Go ahead and update the screen with what we've drawn.

        internalClock +=1

    # --- Limit to 60 frames per second
    clock.tick(60)
    pygame.display.flip()
     
# Close the window and quit.
# If you forget this line, the program will 'hang'
# on exit if running from IDLE.
pygame.quit()
