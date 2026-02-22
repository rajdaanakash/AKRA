#include <iostream>
using namespace std;

// Function to remove duplicates from an array
void removeDuplicates(int arr[], int n) {
    int temp[n];
    int j = 0;

    // Traverse the array
    for (int i = 0; i < n; i++) {
        int flag = 0;

        // Check if the element is already present in the temp array
        for (int k = 0; k < j; k++) {
            if (arr[i] == temp[k]) {
                flag = 1;
                break;
            }
        }

        // If the element is not present, add it to the temp array
        if (flag == 0) {
            temp[j] = arr[i];
            j++;
        }
    }

    // Print the array without duplicates
    cout << "Array without duplicates: ";
    for (int i = 0; i < j; i++) {
        cout << temp[i] << " ";
    }
    cout << endl;
}

int main() {
    int arr[] = {1, 2, 2, 3, 4, 4, 5, 6, 6};
    int n = sizeof(arr) / sizeof(arr[0]);

    cout << "Original array: ";
    for (int i = 0; i < n; i++) {
        cout << arr[i] << " ";
    }
    cout << endl;

    removeDuplicates(arr, n);

    return 0;
}