'''import turtle

screen = turtle.Screen()

# Turtle 1
t1 = turtle.Turtle()
t1.shape("turtle")
t1.color("red")
t1.shapesize(5,5,5)
t1.penup()
t1.goto(-200, 50)

# Turtle 2
t2 = turtle.Turtle()
t2.shape("turtle")
t2.color("blue")
t2.shapesize(5,5,5)
t2.penup()
t2.goto(-200, 0)

# Turtle 3
t3 = turtle.Turtle()
t3.shape("turtle")
t3.color("green")
t3.shapesize(5,5,5)
t3.penup()
t3.goto(-200, -50)

# Move them
for i in range(200):
    t1.forward(1)
    t2.forward(2)
    t3.forward(3)

screen.mainloop()'''

#creating a moving car using same pattern too
import turtle

screen = turtle.Screen()

# Red car
car1 = turtle.Turtle()
car1.shape("square")
car1.color("red")
car1.shapesize(2, 4)
car1.penup()
car1.goto(-300, 50)

# Blue car
car2 = turtle.Turtle()
car2.shape("square")
car2.color("blue")
car2.shapesize(2, 4)
car2.penup()
car2.goto(-300, 0)

# Green car
car3 = turtle.Turtle()
car3.shape("square")
car3.color("green")
car3.shapesize(2, 4)
car3.penup()
car3.goto(-300, -50)

# Move the cars
for i in range(200):
    car1.forward(2)
    car2.forward(3)
    car3.forward(4)

screen.mainloop()