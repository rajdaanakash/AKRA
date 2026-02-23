def calculate_square(num):
    return num ** 2

number = int(input("Enter a number: "))
square = calculate_square(number)
print("The square of", number, "is:", square)