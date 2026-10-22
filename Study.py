# study_sample.py
# Run with: python study_sample.py

import json
from collections import Counter


# 1. Functions and list comprehensions
def square_numbers(numbers):
    return [n ** 2 for n in numbers]


def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True


# 2. Classes and objects
class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self.balance += amount

    def withdraw(self, amount):
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount

    def __str__(self):
        return f"{self.owner}: ₹{self.balance}"


# 3. Dictionaries and Counter
def word_frequency(text):
    words = text.lower().split()
    return Counter(words)


# 4. File handling with JSON
def save_and_load(data, filename="sample.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    with open(filename) as f:
        return json.load(f)


def main():
    # Functions
    nums = [1, 2, 3, 4, 5]
    print("Squares:", square_numbers(nums))
    print("Primes up to 30:", [n for n in range(31) if is_prime(n)])

    # Classes + error handling
    account = BankAccount("Asha", 1000)
    account.deposit(500)
    print(account)
    try:
        account.withdraw(5000)
    except ValueError as e:
        print("Error:", e)

    # Dictionaries
    text = "the quick brown fox jumps over the lazy dog the end"
    print("Most common words:", word_frequency(text).most_common(3))

    # File I/O
    data = {"name": "Asha", "skills": ["Python", "SQL"], "active": True}
    print("Loaded from file:", save_and_load(data))


if __name__ == "__main__":
    main()