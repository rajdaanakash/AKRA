#include <iostream>
using namespace std;

// Function to calculate factorial
long long factorial(int n) {
    long long fact = 1;
    for (int i = 2; i <= n; i++) {
        fact *= i;
    }
    return fact;
}

int main(int argc, char* argv[]) {
    int n;

    // Check if command line argument is provided
    if (argc > 1) {
        n = stoi(argv[1]);
    } else {
        cout << "Enter the number of terms: ";
        cin >> n;
    }

    double sum = 1.0;
    for (int i = 2; i <= n; i++) {
        double term = (i % 2 == 0) ? -1.0 / factorial(i) : 1.0 / factorial(i);
        sum += term;
    }

    cout << "Sum of the series: " << sum << endl;

    return 0;
}