'''def main():
    enter = input("Enter 1 - start or 2 - stop: ").strip()
    while enter != "2":
        destination = input("Do you have a place in mind? (yes/no): ").strip().lower()
        transport = None
        if destination == "yes":
            transport = input("Plane/train or car? ").strip().lower()
            trip_type = input("Beach/city/adventure? ").strip().lower()
        else:
            trip_type = input("Beach/city/adventure? ").strip().lower()

        if trip_type == "beach":
            print("Head to Hawaii.")
            beach = input("Type of beach (popular/remote): ").strip().lower()
            if beach == "popular":
                print("Great, check out Waikiki Beach.")
            elif beach == "remote":
                print("Try a quieter spot like the Na Pali Coast or Hana.")
            else:
                print("I'll assume you want a relaxing beach getaway.")
        elif trip_type == "city":
            print("Consider visiting New York, Tokyo, or Paris.")
        elif trip_type == "adventure":
            print("Consider Costa Rica, New Zealand, or Patagonia for adventure.")
        else:
            print("Couldn't determine trip type; please choose beach, city, or adventure.")

        enter = input("Enter 1 - start again or 2 - stop: ").strip()

if __name__ == "__main__":
    main()'''
    
    def person_info(name, age, nationality):
    print("welcome:", name)
    print("age:", age)
    print("nationality:", nationality)


def main():
    number = int(input("amount: "))
    for i in range(number):
        name = input("enter first name: ")
        age = input("enter your age: ")
        nationality = input("enter your nationality: ")
        person_info(name, age, nationality)

if __name__ == "__main__":
    main()