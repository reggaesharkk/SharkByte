"""Run SharkByte examples and optionally chat through a local GenieX server."""
import argparse
import json
import re
import subprocess
import sys
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from pathlib import Path
REPO = Path(__file__).resolve().parent
SYSTEM = "You are SharkByte, a local assistant. Explain results accurately. Never invent a run or verification."


def sharkbyte_answer(question, bell_run):
    text = question.lower()
    answer = []
    if "rightmost" in text and ("bit" in text or "qubit" in text):
        answer.append("SharkByte displays bitstrings most-significant bit first. "
                      "The rightmost bit represents qubit 0, the least-significant bit.")
    if ("bell" in text or (bell_run and "counts" in text)) and re.search(
        r"\b(unequal|different|counts|shots|split)\b", text
    ):
        if bell_run:
            counts, _ = bell_run
            answer.append(f"The last Bell run sampled {sum(counts.values()):,} shots: "
                          f"{counts['00']} of 00 and {counts['11']} of 11.")
        answer.append("The ideal Bell circuit gives 00 and 11 with equal probability. "
                      "Finite random samples can give unequal counts.")
    if "integrity_verified" in text or (bell_run and "integrity" in text):
        if bell_run:
            _, verification = bell_run
            answer.append(f"The last Bell receipt returned {verification['status']}. "
                          + verification["note"])
        else:
            answer.append("INTEGRITY_VERIFIED means the receipt's recomputed hashes match. "
                          "Authorship and correctness require separate evidence.")
    return " ".join(answer)


def bell_phase_comparison():
    from sharkbyte_alpha.quantum import evaluate, parse

    def probabilities(preparation):
        statements = f"qubits 2; shots 1; seed 42; {preparation} h 0; h 1; measure_all;"
        source = statements.replace(";", ";\n")
        return evaluate(parse(source))["probabilities"]

    plus = probabilities("h 0; cx 0 1;")
    minus = probabilities("h 0; cx 0 1; z 0;")
    zero = probabilities("")
    one = probabilities("x 0; x 1;")
    labels = ("00", "01", "10", "11")
    mixture = {label: (zero[label] + one[label]) / 2 for label in labels}
    lines = ["Apply H to both qubits, then measure. SharkByte simulator probabilities:",
             "Input             00   01   10   11"]
    for name, values in (("Plus Bell", plus), ("Minus Bell", minus), ("50/50 mixture", mixture)):
        lines.append(f"{name:16}" + " ".join(f"{values[label]:4.0%}" for label in labels))
    lines.append("The plus state always has even parity and the minus state always has odd parity. "
                 "The mixture can produce either parity, so no single shot identifies all three sources. "
                 "Over repeated trials, observing both parities rules out either pure Bell state.")
    return "\n".join(lines)



def main(load_model=None, system=SYSTEM):
    parser = argparse.ArgumentParser()
    parser.add_argument("--geniex-model", choices=["qualcomm/Qwen3-0.6B", "qualcomm/Qwen3-0.6B:W4A16"])
    args = parser.parse_args()
    model = None
    history = []
    bell_run = None
    bell_receipt = None
    from sharkbyte_alpha.cli import verify
    commands = {
        "/help": "Show this command list.",
        "/bell": "Sample the bundled Bell circuit and check its receipt.",
        "/bell-phase": "Compare three states after Hadamard gates.",
        "/qft": "Run the bundled six-qubit QFT in a 30-qubit register.",
        "/verify": "Check the hashes of the last Bell receipt in this session.",
        "/doctor": "Show the chat backend and SharkByte CLI settings.",
        "/quit": "Exit SharkByte.",
    }

    backend = "SharkByte tools only"
    if args.geniex_model:
        backend = f"GenieX · {args.geniex_model}"
    elif load_model:
        backend = "Trained QA v2 adapter · Local CPU"
    print(f"SharkByte · {backend}. Type /help for commands.")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question == "/quit":
            break
        if question == "/help":
            for command, description in commands.items():
                print(f"  {command:<12}{description}")
            continue
        if question == "/doctor":
            print(f"Chat backend: {backend}\nQuantum simulator: CPU", flush=True)
            subprocess.run([sys.executable, "-B", "-m", "sharkbyte_alpha", "doctor"], cwd=REPO)
            continue
        if question == "/qft":
            frontier = REPO / "benchmarks" / "sb_quantum_benchmark"
            result = subprocess.run([sys.executable, "-B", str(frontier / "frontier30.py"),
                                     str(frontier / "qft6_in_30.sb")], cwd=REPO,
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                print("Frontier30:", result.stderr.strip() or result.stdout.strip())
                continue
            report = json.loads(result.stdout)
            print(f"Frontier30: {report['result']} · {report['qubits']} qubits · "
                  f"{report['final_populated_states']} final states · "
                  f"{report['peak_populated_states']} peak states")
            print("Basis probabilities (up to eight):")
            for basis, probability in list(report["probabilities"].items())[:8]:
                print(f"  {basis}  {probability:.8g}")
            continue
        if question == "/bell":
            result = subprocess.run(
                [sys.executable, "-B", "-m", "sharkbyte_alpha", "run",
                 str(REPO / "examples/bell.sb"), "--mode", "quantum"],
                cwd=REPO, capture_output=True, check=True, timeout=30,
            )
            record = json.loads(result.stdout)
            counts = record["result"]["counts"]
            verification = verify(record)
            bell_run = counts, verification
            bell_receipt = record
            print("SharkByte runner:", counts, verification["status"])
            continue
        if question == "/verify":
            if bell_receipt is None:
                print("Run /bell first to create a receipt.")
            else:
                verification = verify(bell_receipt)
                print(verification["status"], verification["note"])
            continue
        if not question or len(question) > 2000:
            continue
        normalized = question.lower().replace("−", "-")
        phase_question = (
            "mixture" in normalized
            and re.search(r"\bhadamard\b|\bapply h\b", normalized)
            and re.search(r"\|00[>⟩]\s*\+\s*\|11[>⟩]", normalized)
            and re.search(r"\|00[>⟩]\s*-\s*\|11[>⟩]", normalized)
            and re.search(r"\b(probabilit\w*|distinguish|apart)\b", normalized)
        )
        if question == "/bell-phase" or phase_question:
            print("SharkByte runner:", bell_phase_comparison(), flush=True)
            continue
        if re.fullmatch(r"/[\w-]+", question):
            print("Unknown command. Type /help for available commands.")
            continue
        answer = sharkbyte_answer(question, bell_run)
        if answer:
            print("SharkByte:", answer, flush=True)
            continue
        user_message = {"role": "user", "content": question}
        messages = [{"role": "system", "content": system}, *history, user_message]
        truncated = False
        if args.geniex_model:
            request = Request("http://127.0.0.1:18181/v1/chat/completions",
                              json.dumps({"model": args.geniex_model, "messages": messages,
                                          "max_tokens": 384, "stream": False}).encode(),
                              {"Content-Type": "application/json"})
            try:
                with build_opener(ProxyHandler({})).open(request, timeout=90) as response:
                    reply = json.load(response)
                choice = reply["choices"][0]
                answer = choice["message"]["content"].strip()
                truncated = choice.get("finish_reason") == "length"
            except (URLError, TimeoutError, ValueError, KeyError, IndexError, AttributeError, TypeError) as exc:
                print(f"GenieX request failed: {exc}", file=sys.stderr)
                continue
        else:
            if load_model is None:
                print("Chat requires a local model. Type /help to use the simulator and diagnostics.")
                continue
            if model is None:
                torch, tokenizer, model = load_model()
            prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                add_generation_prompt=True, enable_thinking=False)
            ids = tokenizer(prompt, add_special_tokens=False, return_tensors="pt").input_ids
            with torch.inference_mode():
                out = model.generate(ids, attention_mask=torch.ones_like(ids), do_sample=False,
                                     max_new_tokens=96, use_cache=True)
            answer = tokenizer.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip()
        print("SharkByte model:", answer, flush=True)
        if truncated:
            print("GenieX reached the response limit.", flush=True)
        history = [*history, user_message, {"role": "assistant", "content": answer}][-4:]


if __name__ == "__main__":
    main()
