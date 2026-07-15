'''def person_info(name, age, nationality):
    print("welcome:", name)
    print("age:", age)
    print("nationality:", nationality)


def main():
    number = int(input("amount: "))
    for i in range(number):
        name = input("enter first name: ")
        age = input("enter your age: ")
        nationality = input("enter your nationality: ")
        person_info(name, age, nationality)'''
        
'''def total_points(game_score):
    if 5 <= game_score <= 10:
        return 2
    elif 10 < game_score <= 20:
        return 3
    return 0

if __name__ == '__main__':
    score = int(input("Enter the game score: "))
    game_points = total_points(score)
    print(game_points)'''
    
'''def good_deal(cost):
  if cost >= 50 and cost < 150:
      response = "This is a good deal!"
  elif cost >= 150:
      response = "Overpriced!"
  else:
      response = "Cheap, Buy Now!"
  return response
store = input("Enter Store Name: ")
cost = float(input("Item Cost: "))
res = good_deal(cost)
print(store, "-", res)
if res == "This is a good deal!":
   print("Buy before it's too late!")'''
   
'''from random import randint
passenger = input("Enter passenger name (quit to quit): ")
while passenger != "quit":
     flight_number = randint(1, 3)
     print(passenger , ", Flight Number:" , flight_number)
     passenger = input("Enter passenger name (quit to quit): ")'''
     
     #Exercise 1: Calculate the multiplication and sum of two numbers
'''multi = 250
sum = 62
print(multi * sum)
print(multi + sum)'''

#Exercise 2: Print the Sum of a Current Number and a Previous number
'''cur_num = 9
pre_num = 21
print(cur_num + pre_num)'''

#Exercise 3: Print characters present at an even index number
'''s = input("Enter a string: ")
print(s[0:len(s):2])'''

#Exercise 4: Remove first n characters from a string
'''s = input("hello")
n = int(input("2:"))
print(s[n:])'''

#Exercise 5: Check if the first and last numbers of a list are the same
'''numbers = [int(x) for x in input("Enter numbers separated by spaces: ").split()]
if numbers and numbers[0] == numbers[-1]:
    print(True)
else:
    print(False)'''
    
#Exercise 6: Display numbers divisible by 5
'''nums = [int(x) for x in input("5,10,15,20,25,30,35,40,45,50").split()]
print([n for n in nums if n % 5 == 0])'''

#Exercise 7: Find the number of occurrences of a substring in a string
'''string = "emma"
print(s.count(string))'''

#Exercise 8: Print the following pattern
'''for i in range(1, 6):
    print(" ".join(str(i) for _ in range(i)))'''
    
#Exercise 9: Check Palindrome Number
'''n = input("Enter a number: ")
print(n == n[::-1])'''

#Exercise 10: Merge two lists using the following condition
'''list1 = [10, 20, 25, 30, 35]
list2 = [40, 45, 60, 75, 90]
result = [n for n in list1 if n % 2 != 0] + [n for n in list2 if n % 2 == 0]
print(result)'''

#Exercise 12: Print multiplication table from 1 to 10
'''for i in range(1, 11):
    print(" ".join(str(i * j) for j in range(1, 11)))'''
    
'''print((6+3) - (6+3))
print(100 + 5 * 3)
print((6+3)+(6+3))
print(5+4 - 7+3)'''

#python operator code challenge
'''a = 15
b = 4
print(a % b)
print(a // b)
print(a ** b)
a+=10'''

#python list:they are list items that are stored in sqaure brackets,they can be used to store 3 or 4 values.
'''kellylist = ["money","good life","longlife","fame","greatness"]
print(kellylist)
print(len(kellylist))'''

'''list1 = [22 , 45 ,60 ,100]
list2 = ['kelly','success','chidi','george']
list3 = [True , False , True , False]
print(list1 , list2 , list3)'''
'''mylist =['abc' ,350 , True ,'kelly']
print(type(mylist))'''

'''mylist = ['carlifornia' , 'america' , 'nigeria' , 'egypt']
print(mylist[1])
print(mylist[-1])
print(mylist[-2])'''

'''thislist = ["apple", "banana", "cherry", "orange", "kiwi", "melon", "mango"]
print(thislist[2:5])
print(thislist[:4])
print(thislist[2:])
print(thislist[-4:-1])'''

'''thislist = ['apple' , 'banana' , 'cherry']
if 'apple' in thislist:
    print("yes, 'apple' is in the fruits list")'''
    
#change item value
'''thislist = ["apple", "banana", "cherry"]
thislist[1] = "blackcurrant"
print(thislist)'''

'''thislist = ["apple", "banana", "cherry", "orange", "kiwi", "mango"]
thislist[1:3] = ["blackcurrant", "watermelon"]
print(thislist)'''

#Change the second value by replacing it with two new values:
'''thislist = ["apple", "banana", "cherry"]
thislist[1:2] = ["blackcurrant", "watermelon"]
print(thislist)
thislist = ["apple", "banana", "cherry"]
thislist[1:3] = ["watermelon"]
print(thislist)'''
#insert method:insert an item without replacing any value.
'''thislist = ["apple", "banana", "cherry"]
thislist.insert(2, "watermelon")
print(thislist)'''
#To add an item to the end of the list, use the append() method:
'''thislist = ["apple", "banana", "cherry"]
thislist.append("orange")
print(thislist)'''

#To append elements from another list to the current list, use the extend() method.
'''thislist = ["apple", "banana", "cherry"]
tropical = ["mango", "pineapple", "papaya"]
thislist.extend(tropical)
print(thislist)'''

#The remove() method removes the specified item.
'''thislist = ["apple", "banana", "cherry"]
thislist.remove("banana")
print(thislist)'''

#The pop() method removes the specified index.
'''thislist = ["apple", "banana", "cherry"]
thislist.pop(1)
print(thislist)'''

#The del keyword also removes the specified index:
#Remove the first item:
'''thislist = ["apple", "banana", "cherry"]
del thislist[0]
print(thislist)'''
#removes the whole item:
'''thislist = ["apple", "banana", "cherry"]
del thislist'''

#the clear methods empties the list,the list is still there,but has no content.
'''thislist = ['apple' , 'mango' ,'pineapple' ,'pear' ,'orange']
thislist.clear()
print(thislist)'''

'''thislist = ["apple" , "banana" ,"cherry"]
for x in thislist:
 print(thislist)'''
 
'''thislist = ["apple", "banana", "cherry"]
for i in range(len(thislist)):
  print(thislist[i])'''
#A short hand for loop that will print all items in a list:
'''thislist = ["apple", "banana", "cherry"]
[print(x) for x in thislist]'''

#list comprehension:List comprehension offers a shorter syntax when you want to create a new list based on the values of an existing list.
'''fruits = ["apple", "banana", "cherry", "kiwi", "mango"]
newlist = []

for x in fruits:
  if "a" in x:
    newlist.append(x)

print(newlist)'''
#shorter way
'''fruits = ["apple", "banana", "cherry", "kiwi", "mango"]
newlist = [x for x in fruits if "a" in x]
print(newlist)'''
'''fruits = ["apple", "banana", "cherry", "kiwi", "mango"]
newlist = [x for x in fruits if x != "apple"]
print(newlist)'''

'''newlist = [x for x in range(10)]
print(newlist)'''

#sort list:List objects have a sort() method that will sort the list alphanumerically, ascending, by default:
'''thislist = ["orange", "mango", "kiwi", "pineapple", "banana"]
thislist.sort()
print(thislist)

thislist = [24 , 12 ,100 ,30 ,1 ,71 ,50 ,66 ,82 ,14]
thislist.sort()
print(thislist)'''
#To sort descending, use the keyword argument reverse = True
'''thislist = ["orange", "mango", "kiwi", "pineapple", "banana"]
thislist.sort(reverse = True)
print(thislist)'''
#customise sort function:You can also customize your own function by using the keyword argument key = function.
'''def myfunc(n):
  return abs(n - 50)

thislist = [100, 50, 65, 82, 23]
thislist.sort(key = myfunc)
print(thislist)'''

#stop watch timer
'''from time import *
stopwatch = input("1 - start, 0 - stop:")
while stopwatch != "0":
    if stopwatch == "1":
        start_timer = time()
        stopwatch = input("0 - End timer:")
        end_timer = time()
        total = end_timer - start_timer
        updated_time = round(total,2)
        print("total time:",updated_time,"sec")'''
        
#copying list function:You can use the built-in List method copy() to copy a list.
'''thislist = ["apple", "banana", "cherry"]
mylist = thislist.copy()
print(mylist)   
#or
thislist = ["apple", "banana", "cherry"]
mylist = list(thislist)
print(mylist)'''
#class and agent

'''class Agent():
    def __init__(self,name,health,car):
        self.name = name
        self.health = health
        self.car = car
    def player_info(self):
        print("welcome, ",self.name)
        print("your health:",self.health)
        print("car choice:",self.car)
        
class spy(Agent):
    def spy_talk(self):
        print("my name is," ,self.name)
    def shoot(self,bad_guy):
        if bad_guy.health >0:
            bad_guy.health -= 20
            print(bad_guy.name, "has lost",bad_guy.health)
james_bond = spy("james bond",100,"jaguar")
ethan_hunt = Agent("ethan hunt",50,"ferrari")
james_bond.player_info()
james_bond.shoot(ethan_hunt)'''

#python list(class teaching)
'''ages = []
while True:
    age = int(input("enter an age (0 to stop): "))
    if age == 0:
        break
    ages.append(age)

minors = sum(1 for a in ages if a < 18)
seniors = sum(1 for a in ages if a >= 70)

print("all the ages:", ages)
print("number of minors:", minors, "- number of seniors:", seniors)'''

ages_input = input("Enter ages separated by spaces: ")
try:
    ages = [int(x) for x in ages_input.split()]
except ValueError:
    print("Invalid input. Please enter integers separated by spaces.")
    ages = []

seniors = sum(1 for a in ages if a >= 70)
minors = sum(1 for a in ages if a < 18)

print("List of all ages:", ages)
print("- Seniors:", seniors, "- Minors:", minors)