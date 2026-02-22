#include <iostream>
using namespace std;

// Function to add two numbers
double add(double num1, double num2) {
    return num1 + num2;
}

// Function to subtract two numbers
double subtract(double num1, double num2) {
    return num1 - num2;
}

// Function to multiply two numbers
double multiply(double num1, double num2) {
    return num1 * num2;
}

// Function to divide two numbers
double divide(double num1, double num2) {
    if (num2 != 0)
        return num1 / num2;
    else {
        cout << "Error! Division by zero is not allowed.";
        return 0;
    }
}

int main() {
    double num1, num2;
    int choice;

    cout << "Simple Calculator Program" << endl;
    cout << "1. Addition" << endl;
    cout << "2. Subtraction" << endl;
    cout << "3. Multiplication" << endl;
    cout << "4. Division" << endl;
    cout << "Enter your choice (1-4): ";
    cin >> choice;

    cout << "Enter first number: ";
    cin >> num1;
    cout << "Enter second number: ";
    cin >> num2;

    switch (choice) {
        case 1:
            cout << "Result: " << add(num1, num2) << endl;
            break;
        case 2:
            cout << "Result: " << subtract(num1, num2) << endl;
            break;
        case 3:
            cout << "Result: " << multiply(num1, num2) << endl;
            break;
        case 4:
            cout << "Result: " << divide(num1, num2) << endl;
            break;
        default:
            cout << "Invalid choice" << endl;
    }

    return 0;
}