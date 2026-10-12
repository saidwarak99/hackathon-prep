"""
main.py - Entry Point for the Cafe Agent Simulation

This script runs the Cafe Agent simulation. It demonstrates:
1. Automated test queries showcasing each tool in action.
2. An optional interactive terminal loop where you can chat with the agent directly.

To run:
    python main.py
"""

import sys
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent import CafeAgent
from llm_provider import get_gemini_api_key, GeminiProvider

# Attempt to load LLM provider
llm_provider = None
api_key = get_gemini_api_key()
if api_key:
    try:
        llm_provider = GeminiProvider()
        print("✅ LLM Provider (Gemini) loaded successfully.")
    except Exception as e:
        print(f"⚠️ Could not load LLM provider: {e}. Falling back to simulation.")
else:
    print("⚠️ No GEMINI_API_KEY found in environment. Falling back to explicit simulation mode.")

def run_demonstration():
    """
    Runs a series of representative user requests through the Cafe Agent
    to demonstrate tool selection, execution, observation, and response synthesis.
    """
    print("=" * 70)
    print("   [CAFE AGENT] ARCHITECTURE SIMULATION")
    print("=" * 70)
    print("This simulation demonstrates the core loop of an AI Agent:")
    print("  User Request -> Agent Decision -> Tool Execution -> Observation -> Final Answer\n")

    agent = CafeAgent(name="BaristaBot", llm_provider=llm_provider)

    sample_requests = [
        # Scenario 1: Tool-Only Question (Triggers get_inventory)
        "How much whole milk do we currently have in inventory?",

        # Scenario 2: RAG-Only Question (Triggers search_cafe_knowledge)
        "What is our policy for storing milk, and what should employees do about customer complaints?",

        # Scenario 3: Tool + RAG Combined Question (Triggers search_cafe_knowledge AND get_inventory)
        "What is the policy for storing milk, and how much whole milk do we currently have in inventory?",

        # Scenario 4: Multi-Tool Database Query (Triggers get_menu and get_today_sales)
        "What drinks are on the menu and what was today's total revenue?",

        # Scenario 5: Direct answer without tool call (Greeting)
        "Hello! Who are you and how can you help me?",

        # Scenario 6: Out of scope request
        "What is the current weather forecast in London?"
    ]

    import time
    for index, request in enumerate(sample_requests, 1):
        print(f"\n>>> DEMO SCENARIO {index} OF {len(sample_requests)} <<<", flush=True)
        agent.run(request)
        time.sleep(1)


def run_interactive_mode():
    """
    Allows the user to interactively enter custom requests to see how
    the agent's decision logic and tools behave.
    """
    print("\n" + "=" * 70)
    print("   [INTERACTIVE MODE] Chat with BaristaBot")
    print("=" * 70)
    print("Try asking about:")
    print("  * 'What is on the menu?'")
    print("  * 'Check our milk stock and inventory.'")
    print("  * 'How are today's sales looking?'")
    print("Type 'exit' or 'quit' to end the session.\n")

    agent = CafeAgent(name="BaristaBot", llm_provider=llm_provider)

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye! Have a great day running the cafe!")
                break

            agent.run(user_input)
            print()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session...")
            break


def main():
    # If '--interactive' or '-i' flag is passed, jump straight to interactive mode
    if len(sys.argv) > 1 and sys.argv[1] in ["--interactive", "-i"]:
        run_interactive_mode()
        return

    # Default flow: Run demo scenarios first, then offer interactive chat
    run_demonstration()

    print("\n" + "=" * 70)
    if sys.stdin.isatty():
        choice = input("Would you like to try Interactive Mode now? (y/n): ").strip().lower()
        if choice in ["y", "yes"]:
            run_interactive_mode()
        else:
            print("Thanks for exploring the Cafe Agent architecture!")
    else:
        print("Demo completed successfully. Run `python main.py -i` for interactive mode.")


if __name__ == "__main__":
    main()
                                                         