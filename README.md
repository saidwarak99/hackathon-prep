# ☕ Cafe Agent: AI Agent Architecture Simulation

Welcome to **Cafe Agent**, a lightweight educational project designed to demystify the internal mechanics of an **AI Agent** without relying on external LLM APIs.

Before plugging an agent into OpenAI, Google Gemini, Anthropic Claude, or local LLMs, it is crucial to understand the fundamental architecture: **how an agent perceives an input, reasons about what tools to invoke, executes actions, consumes real-world observations, and synthesizes a final answer**.

---

## 1. What is an AI Agent?

A traditional Large Language Model (LLM) is simply a text-prediction engine. By itself, an LLM:
* **Cannot query current state** (e.g., it does not know today's sales numbers or if milk is in stock).
* **Cannot take actions** in the world (e.g., place an order, query a database, call an API).
* **Is frozen in time** based on its training cutoff.

An **AI Agent** is an autonomous software entity built on top of a reasoning engine. An agent:
1. **Perceives** an environment or user request.
2. **Maintains State & Memory**.
3. **Reasons & Plans** which actions or external tools are needed to fulfill a goal.
4. **Executes Tools** to query data or make changes in the environment.
5. **Observes** the output of those tools.
6. **Iterates or Responds** until the goal is achieved.

> **Key Formula:**
> $$\text{AI Agent} = \text{Reasoning Engine} + \text{Tools (Actions)} + \text{Environment (Memory/Observation)} + \text{Control Loop}$$

---

## 2. What is a Tool?

A **tool** is an executable function, API, script, or database query that the agent can choose to call. 

In code, a tool has three components:
1. **A Function Implementation**: The code that actually does the work (e.g., queries a database).
2. **A Signature & Parameters**: What arguments the function accepts.
3. **A Schema / Description**: A human-readable description of *what the tool does* and *when it should be used*. In real LLMs, the model reads this description to decide if the tool matches the user's intent.

### Tools in this Project (`tools.py`):
| Tool Name | Purpose | What it Returns |
| :--- | :--- | :--- |
| `get_inventory()` | Checks current cafe ingredients, stock levels, and flags reorder needs | Dictionary of 10 items with stock & status |
| `get_today_sales()` | Retrieves today's sales metrics, order count, and revenue | POS metrics, revenue, top-selling items |
| `get_menu()` | Fetches the complete cafe menu categorized with prices & dietary tags | Categories: Coffee, Teas, Pastries |

---

## 3. How the Agent Loop Works

The agent loop (popularized by architectures like **ReAct: Reasoning + Acting**) follows a cyclic execution flow:

```
                  ┌──────────────────────┐
                  │     User Request     │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ 1. REASONING / PLAN  │
                  │  "Which tool needed?"│
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            │ (Tool Needed)                   │ (No Tool Needed)
            ▼                                 ▼
  ┌──────────────────┐               ┌──────────────────┐
  │ 2. EXECUTE TOOL  │               │ DIRECT RESPONSE  │
  │  Invoke function │               │ Greeting/Reject  │
  └─────────┬────────┘               └────────┬─────────┘
            │                                 │
            ▼                                 │
  ┌──────────────────┐                        │
  │ 3. OBSERVATION   │                        │
  │ Receive raw data │                        │
  └─────────┬────────┘                        │
            │                                 │
            ▼                                 │
  ┌──────────────────┐                        │
  │ 4. SYNTHESIS     │                        │
  │ Compose answer   │                        │
  └─────────┬────────┘                        │
            │                                 │
            └────────────────┬────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    Final Response    │
                  └──────────────────────┘
```

### Trace Example from the Simulation:
```
[AGENT LOOP STARTED] Processing user request:
   "Could you check our inventory and tell me if we have any low stock items?"

[STEP 1: AGENT DECISION / REASONING]
   Selected Tool : get_inventory
   Agent's Logic : User is asking about supplies/stock (matched keyword: 'inventory'). Needs live inventory data.

[STEP 2: TOOL EXECUTION]
   Invoking tool function: get_inventory()

[STEP 3: TOOL OBSERVATION / DATA RETURNED]
   Tool Status: success
   Data Preview: Keys received -> ['coffee_beans_house_blend', 'whole_milk', 'oat_milk', ...]

[STEP 4: RESPONSE SYNTHESIS]
   Agent is composing natural language response for user...

[FINAL AGENT RESPONSE]:
Here is the current inventory status:
* Total tracked items: 10
* Attention needed (Low Stock Items):
- Oat Milk (Barista Edition): 3.0 cartons (Reorder threshold: 8.0 cartons)
- Artisan Vanilla Syrup: 2.0 bottles (Reorder threshold: 3.0 bottles)
- Artisan Sourdough Loaf: 4.0 loaves (Reorder threshold: 5.0 loaves)

Recommendation: Place orders for Oat Milk, Vanilla Syrup, and Sourdough Loaves promptly.
```

---

## 4. Project Structure

```
hackathon/
│
├── data.py          # Mock database: Cafe inventory, today's sales, and menu
├── tools.py         # Executable tools & tool registry (name, description, callable)
├── agent.py         # CafeAgent class: Decision logic, execution loop, and synthesis
├── main.py          # Runner: Automated demo scenarios + Interactive CLI
└── README.md        # Architecture documentation & LLM integration guide
```

---

## 5. How This Simulation Connects to an LLM Later

In this simulation, the agent's decision logic and response synthesis are written with explicit Python logic (`agent.py`) so you can inspect every step.

When you are ready to upgrade this project to a real LLM (like Google Gemini or OpenAI), **you do not need to rewrite your tools or data!** The architecture remains identical:

### Architecture Comparison:

| Stage | Simulation (`Cafe Agent`) | Real LLM Agent (Gemini / OpenAI) |
| :--- | :--- | :--- |
| **Tool Registry** | Python dict in `tools.py` | JSON Schema / Function Declarations passed to LLM API |
| **Decision Step** | Keyword & intent matching in `decide_tool()` | LLM emits a `tool_call` object with function name & arguments |
| **Execution Step** | `agent.execute_tool(tool_name)` | Your Python runner executes `tool_name(**args)` |
| **Observation** | Dictionary returned from `tools.py` | Result is appended to chat history with `role: "tool"` |
| **Synthesis** | Formatted string in `synthesize_response()` | LLM reads the tool output and writes a natural language reply |

### Real LLM Code Example (Google Gemini / OpenAI):

#### With Google GenAI SDK:
```python
from google import genai
from tools import get_inventory, get_today_sales, get_menu

# 1. Provide the exact same Python tools to the Gemini client
client = genai.Client()

# 2. Gemini automatically inspects the docstrings & signatures of the tools
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="How much revenue did our cafe generate today?",
    config={
        "tools": [get_inventory, get_today_sales, get_menu]
    }
)

# 3. If Gemini decides a tool is needed, it returns a function call:
# response.function_calls -> [FunctionCall(name='get_today_sales', args={})]
```

#### With OpenAI Function Calling:
```python
from openai import OpenAI
from tools import TOOL_REGISTRY

client = OpenAI()

# 1. Define tools as JSON Schemas
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_today_sales",
            "description": "Retrieve today's financial metrics and sales performance.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

# 2. Ask the model
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "How are our sales looking today?"}],
    tools=tools,
    tool_choice="auto"
)

# 3. Handle model tool decision
message = response.choices[0].message
if message.tool_calls:
    for call in message.tool_calls:
        fn_name = call.function.name
        # Execute tool locally
        raw_result = TOOL_REGISTRY[fn_name]["function"]()
        # Feed back to model for final synthesis
```

---

## 6. How to Run the Project

### 1. Run Automated Demonstration
Runs 5 distinct scenarios demonstrating each tool, greetings, and out-of-scope handling:
```bash
python main.py
```

### 2. Run Interactive Mode
Chat with `BaristaBot` directly in your terminal:
```bash
python main.py -i
```
Try asking:
* *"What drinks do you have on the menu and what do they cost?"*
* *"Do we need to reorder any milk or coffee beans in inventory?"*
* *"What is our total revenue and best seller today?"*
* *"Hi BaristaBot, who are you?"*
* *"Can you book me a train ticket?"*
