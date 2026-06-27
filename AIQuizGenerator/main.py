import os
from dotenv import load_dotenv
from app import generate_quiz


def main() -> None:
    load_dotenv()
    topic = input("Enter a quiz topic: ")
    quiz = generate_quiz(topic)
    print("\nGenerated Quiz:\n")
    for idx, item in enumerate(quiz, start=1):
        print(f"{idx}. {item['question']}")
        for option in item.get('options', []):
            print(f"  - {option}")
        print(f"Answer: {item['answer']}\n")


if __name__ == "__main__":
    main()
