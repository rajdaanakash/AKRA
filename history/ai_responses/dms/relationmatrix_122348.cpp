#include <iostream>
using namespace std;

class Relation {
    private:
        int **matrix;
        int n;

    public:
        // Constructor
        Relation(int **matrix, int n) {
            this->matrix = matrix;
            this->n = n;
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
            return isReflexive() && isSymmetric() && isTransitive();
        }

        // Function to check if the relation is a partial order relation
        bool isPartialOrder() {
            return isAntiSymmetric() && isTransitive() && isReflexive();
        }
};

int main() {
    int n = 3;
    int **matrix = new int*[n];
    for (int i = 0; i < n; i++) {
        matrix[i] = new int[n];
    }

    // Initialize the matrix
    matrix[0][0] = 1; matrix[0][1] = 0; matrix[0][2] = 0;
    matrix[1][0] = 0; matrix[1][1] = 1; matrix[1][2] = 0;
    matrix[2][0] = 0; matrix[2][1] = 0; matrix[2][2] = 1;

    Relation relation(matrix, n);

    cout << "Is reflexive: " << (relation.isReflexive() ? "Yes" : "No") << endl;
    cout << "Is symmetric: " << (relation.isSymmetric() ? "Yes" : "No") << endl;
    cout << "Is anti-symmetric: " << (relation.isAntiSymmetric() ? "Yes" : "No") << endl;
    cout << "Is transitive: " << (relation.isTransitive() ? "Yes" : "No") << endl;
    cout << "Is equivalence: " << (relation.isEquivalence() ? "Yes" : "No") << endl;
    cout << "Is partial order: " << (relation.isPartialOrder() ? "Yes" : "No") << endl;

    // Deallocate memory
    for (int i = 0; i < n; i++) {
        delete[] matrix[i];
    }
    delete[] matrix;

    return 0;
}