#rolling the dice game!
'''import random

while True:
    choice = input('roll the dice? (y/n): ').lower()
    if choice == 'y':
        die1 = random.randint(1 , 6)
        die2 = random.randint(1 , 6)
        print(f'({die1}, {die2})')
    elif choice == 'n':
        print('thanks for playing!')
        break
    else:
        print('invalid choice!')'''
        
# number guessing game
'''import random

number_to_guess = random.randint(1, 100)
while True:
 try:
    guess = int(input('guess the numbeer between 1 and 100: '))
    if guess < number_to_guess:
        print('too low!')
    elif guess > number_to_guess:
        print('too high!')
    else:
        print('congratulations! you guessed the number.')
        break
 except ValueError:
    print('please enter a valid number!')'''
    
# Rock!, paper and scissors game!
'''import random

emojis = {'r': '🪨', 's': '✂️', 'p': '📃'}
choices = ('r', 'p', 's')
while True:
    user_choice = input('rock, paper, scissors? (r/p/s): ').lower()
    if user_choice not in choices:
        print('invalid choice!')
        continue

    computer_choice = random.choice(choices)

    print(f'you chose {emojis[user_choice]}')
    print(f'computer chose {emojis[computer_choice]}')
    if user_choice == computer_choice:
        print('tie')
    elif (
        (user_choice == 'r' and computer_choice == 's') or
        (user_choice == 's' and computer_choice == 'p') or
        (user_choice == 'p' and computer_choice == 'r')
    ):
        print('you win!')
    else:
        print('you lose!')

    should_continue = input('continue? (y/n): ').lower()
    if should_continue == 'n':
        break'''
        
    
