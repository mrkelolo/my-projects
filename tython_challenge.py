import turtle
#challenge 4
def draw_hexagon(t, side , color):
    t.fillcolor(color)
    t.begin_fill()
    for _ in range(6):
        t.forward(side)
        t.left(60)
    t.end_fill()
def draw_triangle(t, side , color):
    t.fillcolor(color)
    t.begin_fill()
    for _ in range(3):
        t.forward(side)
        t.left(120)
    t.end_fill()
#challenge 5
print("turtle challenges")
print("1 - hexagon only")
print("2 - triangles only")
print("3 - booth")
choice = input("pick what to draw(1,2,or 3):")
#screen setup
screen = turtle.Screen()
screen.title("challenges for turtle")
screen.bgcolor("white")

#challenge 1
if choice == "1" or choice == "3":
   t1 = turtle.Turtle()
   t1.penup()
   t1.goto(-200,100)
   t1.pendown()
   t1.pensize(3)
   #fixed black hexagon
   t1.fillcolor("black")
   t1.begin_fill()
   for _ in range(6):
       t1.forward(60)
       t1.left(60)
t1.end_fill()
#challenge 2
if choice == "1" or choice == "3":
    t2 = turtle.Turtle()
    t2.penup()
    t2.goto(-200,-100)
    t2.pendown()   
    t2.pencolor("red")
    t2.pensize(3)
    
    # Filled red hexagon
    t2.fillcolor("red")
    t2.begin_fill()
    for _ in range(6):
        t2.forward(60)
        t2.left(60)
    t2.end_fill()

# ==========================================================
# CHALLENGE 3: Draw 3 Triangles at the same time 
#              in different locations
# ==========================================================
if choice == "2" or choice == "3":
    colors = ["blue", "red", "green"]
    positions = [(100, 150), (100, 50), (100, -50)]
    
    for color, pos in zip(colors, positions):
        t = turtle.Turtle()
        t.penup()
        t.goto(pos)
        t.pendown()
        t.setheading(60)
        draw_triangle(t, 80, color)

# Keep the window open until you click it
print("Click the turtle window to exit.")
turtle.exitonclick()