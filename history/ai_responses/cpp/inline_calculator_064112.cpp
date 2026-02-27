#include <iostream>
using namespace std;

// Inline function to add two numbers
inline int add(int a, int b) {
    return (a + b);
}

int main() {
    int x, y;
    cout << "Enter first number: ";
    cin >> x;
    cout << "Enter second number: ";
    cin >> y;
    cout << "Sum is: " << add(x, y) << endl;
    return 0;
}