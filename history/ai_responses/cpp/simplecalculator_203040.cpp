#include <iostream>
using namespace std;

int main() {
    int choice;
    float num1, num2;

    cout << "Simple Calculator" << endl;
    cout << "1. Addition" << endl;
    cout << "2. Subtraction" << endl;
    cout << "3. Multiplication" << endl;
    cout << "4. Division" << endl;

    cout << "Enter your choice (1/2/3/4): ";
    cin >> choice;

    cout << "Enter first number: ";
    cin >> num1;

    cout << "Enter second number: ";
    cin >> num2;

    switch (choice) {
        case 1:
            cout << num1 << " + " << num2 << " = " << num1 + num2 << endl;
            break;
        case 2:
            cout << num1 << " - " << num2 << " = " << num1 - num2 << endl;
            break;
        case 3:
            cout << num1 << " * " << num2 << " = " << num1 * num2 << endl;
            break;
        case 4:
            if (num2 != 0) {
                cout << num1 << " / " << num2 << " = " << num1 / num2 << endl;
            } else {
                cout << "Error: Division by zero is not allowed." << endl;
            }
            break;
        default:
            cout << "Invalid choice." << endl;
    }

    return 0;
}