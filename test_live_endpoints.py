import sys
import json
import urllib.request
import urllib.error
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def post_json(path: str, data: dict, retry_on_429: bool = True):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8")
    
    for attempt in range(2 if retry_on_429 else 1):
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=150) as resp:
                elapsed = time.time() - start
                res_body = json.loads(resp.read().decode("utf-8"))
                return resp.getcode(), elapsed, res_body
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start
            err_text = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_text)
            except Exception:
                err_json = {"detail": err_text}
            if e.code == 429 and attempt == 0 and retry_on_429:
                print(f"      [429 RateLimit encountered, waiting 8s for window reset...]")
                time.sleep(8)
                continue
            return e.code, elapsed, err_json
        except Exception as e:
            elapsed = time.time() - start
            return 0, elapsed, {"error": str(e)}

def run_tests():
    print("=" * 70)
    print("1. VERIFYING LIVE GEMINI VIA GEMINI PROVIDER")
    print("=" * 70)
    from llm_provider import GeminiProvider, sanitize_error
    try:
        provider = GeminiProvider()
        res = provider.generate(
            messages=[{"role": "user", "content": "Respond strictly with: 'Gemini live provider operational.'"}],
            tools=[]
        )
        print("Live Provider Status : SUCCESS")
        print("Model Name           :", provider.model_name)
        print("Provider Output      :", res.get("content"))
    except Exception as e:
        print("Live Provider Status : FAILED ->", type(e).__name__, sanitize_error(e))

    time.sleep(3)

    print("\n" + "=" * 70)
    print("2. TESTING INDIVIDUAL 6 SPECIALIST AGENTS & RAG ENDPOINTS")
    print("=" * 70)

    endpoints = [
        ("1. Sales Intelligence Agent", "/api/agents/sales/chat", {"message": "What was today's sales revenue and top seller?"}),
        ("2. Menu Intelligence Agent", "/api/agents/menu/chat", {"message": "What categories and items do we offer on the menu?"}),
        ("3. Feedback Intelligence Agent", "/api/agents/feedback/chat", {"message": "Summarize recent customer feedback ratings and sentiments."}),
        ("4. Inventory Intelligence Agent", "/api/agents/inventory/chat", {"message": "What inventory items are low on stock and need reordering?"}),
        ("5. Decision Recommendation Agent", "/api/agents/recommendations/chat", {"message": "What are your top business recommendations for today?"}),
        ("6. Restaurant Knowledge Agent", "/api/agents/knowledge/chat", {"message": "What are the rules for storing milk according to our SOP?"}),
        ("7. RAG Semantic Search", "/api/knowledge/search", {"query": "rules for storing milk", "top_k": 3})
    ]

    for label, path, payload in endpoints:
        print(f"\n--- Testing {label} ({path}) ---")
        code, elapsed, res = post_json(path, payload)
        print(f"Status Code : {code} (took {elapsed:.2f}s)")
        if code == 200:
            print("Status      :", res.get("status"))
            if "agent" in res:
                print("Agent       :", res.get("agent"))
            if "executed_tools" in res:
                tools_used = [t.get("tool_name") for t in res.get("executed_tools", [])]
                print("Tools Used  :", tools_used)
            if "total_results" in res:
                print("Results Count:", res.get("total_results"))
                print("Citations   :", res.get("citations"))
            answer = res.get("answer", "")
            if answer:
                print(f"Answer      :\n{answer}")
        else:
            print("ERROR DETAIL:", res)
        time.sleep(4)

    print("\n" + "=" * 70)
    print("3. TESTING UNIFIED ORCHESTRATOR MULTI-AGENT TEST (/api/chat)")
    print("=" * 70)
    orchestrator_payload = {
        "message": "What is our current milk stock in inventory, and what are the standard operating procedures for storing milk?"
    }
    code, elapsed, res = post_json("/api/chat", orchestrator_payload)
    print(f"Status Code : {code} (took {elapsed:.2f}s)")
    if code == 200:
        print("Status          :", res.get("status"))
        print("Selected Agents :", res.get("selected_agents"))
        print("Route           :", res.get("route"))
        print("Evidence Sources:", res.get("evidence_sources"))
        print("Data Origin     :", res.get("data_origin"))
        print("Synthesized Answer:\n", res.get("answer"))
    else:
        print("ERROR DETAIL:", res)

if __name__ == "__main__":
    run_tests()
