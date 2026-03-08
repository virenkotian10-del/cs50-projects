import sys
from crossword import *
import copy

class CrosswordCreator():

    def __init__(self, crossword):
        """
        Create new CSP crossword generate.
        """
        self.crossword = crossword
        self.domains = {
            var: self.crossword.words.copy()
            for var in self.crossword.variables
        }

    def letter_grid(self, assignment):
        """
        Return 2D array representing a given assignment.
        """
        letters = [
            [None for _ in range(self.crossword.width)]
            for _ in range(self.crossword.height)
        ]
        for variable, word in assignment.items():
            direction = variable.direction
            for k in range(len(word)):
                i = variable.i + (k if direction == Variable.DOWN else 0)
                j = variable.j + (k if direction == Variable.ACROSS else 0)
                letters[i][j] = word[k]
        return letters

    def print(self, assignment):
        """
        Print crossword assignment to the terminal.
        """
        letters = self.letter_grid(assignment)
        for i in range(self.crossword.height):
            for j in range(self.crossword.width):
                if self.crossword.structure[i][j]:
                    print(letters[i][j] or " ", end="")
                else:
                    print("█", end="")
            print()

    def save(self, assignment, filename):
        """
        Save crossword assignment to an image file.
        """
        from PIL import Image, ImageDraw, ImageFont
        cell_size = 100
        cell_border = 2
        interior_size = cell_size - 2 * cell_border
        letters = self.letter_grid(assignment)

        # Create a blank canvas - FIXED: Use RGB instead of RGBA
        img = Image.new(
            "RGB",  # Changed from "RGBA" to "RGB" to work with JPEG
            (self.crossword.width * cell_size,
             self.crossword.height * cell_size),
            "black"
        )
        font = ImageFont.truetype("assets/fonts/OpenSans-Regular.ttf", 80)
        draw = ImageDraw.Draw(img)

        for i in range(self.crossword.height):
            for j in range(self.crossword.width):

                rect = [
                    (j * cell_size + cell_border,
                     i * cell_size + cell_border),
                    ((j + 1) * cell_size - cell_border,
                     (i + 1) * cell_size - cell_border)
                ]
                if self.crossword.structure[i][j]:
                    draw.rectangle(rect, fill="white")
                    if letters[i][j]:
                        _, _, w, h = draw.textbbox((0, 0), letters[i][j], font=font)
                        draw.text(
                            (rect[0][0] + ((interior_size - w) / 2),
                             rect[0][1] + ((interior_size - h) / 2) - 10),
                            letters[i][j], fill="black", font=font
                        )

        img.save(filename)

    def solve(self):
        """
        Enforce node and arc consistency, and then solve the CSP.
        """
        print("Starting solve...")
        self.enforce_node_consistency()
        print("Node consistency enforced")
        self.ac3()
        print("AC3 completed")
        result = self.backtrack(dict())
        print(f"Backtrack result: {result}")
        return result

    def enforce_node_consistency(self):
        """
        Update `self.domains` such that each variable is node-consistent.
        """
        for variable in self.domains:
            # Keep only words that have the same length as the variable
            self.domains[variable] = {
                word for word in self.domains[variable] 
                if len(word) == variable.length
            }

    def revise(self, x, y):
        """
        Make variable `x` arc consistent with variable `y`.
        """
        revised = False
        overlap = self.crossword.overlaps[x, y]
        
        if overlap is None:
            return False
        
        i, j = overlap  # x's i-th character must equal y's j-th character
        
        # Check each word in x's domain
        words_to_remove = set()
        for word_x in self.domains[x]:
            # Check if there's any word in y's domain that satisfies the constraint
            found_match = False
            for word_y in self.domains[y]:
                if word_x[i] == word_y[j]:
                    found_match = True
                    break
            
            if not found_match:
                words_to_remove.add(word_x)
                revised = True
        
        # Remove inconsistent words from x's domain
        self.domains[x] -= words_to_remove
        return revised

    def ac3(self, arcs=None):
        """
        Update `self.domains` such that each variable is arc consistent.
        """
        if arcs is None:
            # Start with all arcs in the problem
            arcs = []
            for x in self.crossword.variables:
                for y in self.crossword.neighbors(x):
                    arcs.append((x, y))
        
        queue = arcs.copy()
        
        while queue:
            x, y = queue.pop(0)
            if self.revise(x, y):
                # If x's domain was revised, add all arcs pointing to x
                if len(self.domains[x]) == 0:
                    return False
                for z in self.crossword.neighbors(x):
                    if z != y:
                        queue.append((z, x))
        
        return True

    def assignment_complete(self, assignment):
        """
        Return True if `assignment` is complete.
        """
        return len(assignment) == len(self.crossword.variables)

    def consistent(self, assignment):
        """
        Return True if `assignment` is consistent.
        """
        # Check all values are distinct
        words = list(assignment.values())
        if len(words) != len(set(words)):
            return False
        
        # Check each value has correct length
        for variable, word in assignment.items():
            if len(word) != variable.length:
                return False
        
        # Check no conflicts between neighboring variables
        for variable in assignment:
            for neighbor in self.crossword.neighbors(variable):
                if neighbor in assignment:
                    overlap = self.crossword.overlaps[variable, neighbor]
                    if overlap:
                        i, j = overlap
                        if assignment[variable][i] != assignment[neighbor][j]:
                            return False
        
        return True

    def order_domain_values(self, var, assignment):
        """
        Return a list of values in the domain of `var`, ordered by least-constraining values.
        """
        if not self.domains[var]:
            return []  # Return empty list if no domain values
            
        def count_eliminations(word):
            """Count how many choices this word eliminates for neighbors."""
            eliminations = 0
            for neighbor in self.crossword.neighbors(var):
                if neighbor not in assignment:  # Only consider unassigned neighbors
                    overlap = self.crossword.overlaps[var, neighbor]
                    if overlap:
                        i, j = overlap
                        for neighbor_word in self.domains[neighbor]:
                            if word[i] != neighbor_word[j]:
                                eliminations += 1
            return eliminations
        
        # Sort by number of eliminations (ascending - least constraining first)
        return sorted(self.domains[var], key=count_eliminations)

    def select_unassigned_variable(self, assignment):
        """
        Return an unassigned variable according to MRV and degree heuristics.
        """
        unassigned = [v for v in self.crossword.variables if v not in assignment]
        
        if not unassigned:
            return None
            
        # Sort by minimum remaining values (MRV)
        unassigned.sort(key=lambda v: len(self.domains[v]))
        
        # If tie, sort by degree (number of neighbors)
        mrv_value = len(self.domains[unassigned[0]])
        tied_variables = [v for v in unassigned if len(self.domains[v]) == mrv_value]
        
        if len(tied_variables) > 1:
            tied_variables.sort(key=lambda v: len(self.crossword.neighbors(v)), reverse=True)
        
        return tied_variables[0]

    def backtrack(self, assignment):
        """
        Using Backtracking Search, return a complete assignment if possible.
        """
        if self.assignment_complete(assignment):
            return assignment
        
        var = self.select_unassigned_variable(assignment)
        if var is None:
            return None
        
        for value in self.order_domain_values(var, assignment):
            new_assignment = assignment.copy()
            new_assignment[var] = value
            
            if self.consistent(new_assignment):
                # Save current domains for backtracking
                old_domains = copy.deepcopy(self.domains)
                
                # Make inference (forward checking)
                self.domains[var] = {value}
                inferences_made = self.ac3([(neighbor, var) for neighbor in self.crossword.neighbors(var)])
                
                # Only continue if inferences were successful (domains not empty)
                if inferences_made:
                    result = self.backtrack(new_assignment)
                    if result is not None:
                        return result
                
                # Backtrack - restore domains
                self.domains = old_domains
        
        return None


def main():

    # Check usage
    if len(sys.argv) not in [3, 4]:
        sys.exit("Usage: python generate.py structure words [output]")

    # Parse command-line arguments
    structure = sys.argv[1]
    words = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) == 4 else None

    # DEBUG: Add print statements
    print(f"Structure file: {structure}")
    print(f"Words file: {words}")
    
    # Generate crossword
    crossword = Crossword(structure, words)
    creator = CrosswordCreator(crossword)
    
    # DEBUG: Add more info
    print(f"Number of variables: {len(crossword.variables)}")
    print(f"Number of words: {len(crossword.words)}")
    
    # Print variables for debugging
    for var in crossword.variables:
        print(f"  Variable: {var}")
    
    assignment = creator.solve()

    # Print result
    if assignment is None:
        print("No solution.")
    else:
        print("Solution found!")
        creator.print(assignment)
        if output:
            creator.save(assignment, output)
            print(f"Image saved as: {output}")


if __name__ == "__main__":
    main()