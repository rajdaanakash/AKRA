# Define a function to add two numbers
def add_numbers(num1, num2):
    return num1 + num2

# Get input from the user
num1 = float(input("Enter the first number: "))
num2 = float(input("Enter the second number: "))

# Call the function and print the result
result = add_numbers(num1, num2)
print(f"The sum of {num1} and {num2} is: {result}")