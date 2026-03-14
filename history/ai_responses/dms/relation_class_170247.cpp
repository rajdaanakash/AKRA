#include <iostream>
using namespace std;

class Relation {
private:
    int **matrix;
    int n;

public:
    // Constructor
    Relation(int n) {
        this->n = n;
        matrix = new int*[n];
        for (int i = 0; i < n; i++) {
            matrix[i] = new int[n];
        }
    }

    // Function to input the relation matrix
    void inputMatrix() {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                cin >> matrix[i][j];
            }
        }
    }

    // Function to check if the relation is reflexive
    bool isReflexive() {
        for (int i = 0; i < n; i++) {
            if (matrix[i][i] == 0) {
                return false;
            }
        }
        return true;
    }

    // Function to check if the relation is symmetric
    bool isSymmetric() {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (matrix[i][j] != matrix[j][i]) {
                    return false;
                }
            }
        }
        return true;
    }

    // Function to check if the relation is anti-symmetric
    bool isAntiSymmetric() {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (i != j && matrix[i][j] == 1 && matrix[j][i] == 1) {
                    return false;
                }
            }
        }
        return true;
    }

    // Function to check if the relation is transitive
    bool isTransitive() {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                for (int k = 0; k < n; k++) {
                    if (matrix[i][j] == 1 && matrix[j][k] == 1 && matrix[i][k] == 0) {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    // Function to check if the relation is an equivalence relation
    bool isEquivalence() {
        if (isReflexive() && isSymmetric() && isTransitive()) {
            return true;
        }
        return false;
    }

    // Function to check if the relation is a partial order relation
    bool isPartialOrder() {
        if (isReflexive() && isAntiSymmetric() && isTransitive()) {
            return true;
        }
        return false;
    }
};

int main() {
    int n;
    cout << "Enter the number of elements: ";
    cin >> n;

    Relation relation(n);
    cout << "Enter the relation matrix: " << endl;
    relation.inputMatrix();

    cout << "Is reflexive: " << (relation.isReflexive() ? "Yes" : "No") << endl;
    cout << "Is symmetric: " << (relation.isSymmetric() ? "Yes" : "No") << endl;
    cout << "Is anti-symmetric: " << (relation.isAntiSymmetric() ? "Yes" : "No") << endl;
    cout << "Is transitive: " << (relation.isTransitive() ? "Yes" : "No") << endl;

    if (relation.isEquivalence()) {
        cout << "The relation is an equivalence relation." << endl;
    } else if (relation.isPartialOrder()) {
        cout << "The relation is a partial order relation." << endl;
    } else {
        cout << "The relation is neither an equivalence nor a partial order relation." << endl;
    }

    return 0;
}