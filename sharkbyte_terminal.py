"""Run SharkByte examples and optionally chat through a local GenieX server."""
import argparse
import json
import re
import subprocess
import sys
from urllib.error import URLError
from sharkbyte_local_http import open_local
from sharkbyte_alpha.cli import canonical, read_source, verify
from sharkbyte_experiment import FRONTIER, PHASE_SOURCES, read_receipt, replay, run_experiment

from pathlib import Path
REPO = Path(__file__).resolve().parent
SYSTEM = "You are SharkByte, a local assistant. Explain results accurately. Never invent a run or verification."


def sharkbyte_answer(question, bell_run):
    text = question.lower()
    answer = []
    asks_qft_spectators = (
        re.search(r"\bqft\b", text)
        and ("spectator" in text or "30-qubit" in text or "30 qubit" in text)
        and re.search(r"\b(explain|computed|compute|why|stay|remain)\b", text)
    )
    if asks_qft_spectators:
        answer.append(
            "The /qft demo runs the bundled six-qubit QFT circuit on qubits 0–5 of a 30-qubit "
            "register. Its gates do not target qubits 6–29; those spectators start in |0>, stay "
            "in |0>, and are not entangled with the active six-qubit register. The sparse run "
            "reports 32 populated basis states; the displayed probabilities are 1/32 (0.03125) "
            "for each shown state, with the 24 high-order spectator bits all zero."
        )
    asks_bell_phase = (
        "bell-phase" in text
        or ("bell" in text and "phase" in text and
            re.search(r"\b(show|shows|demo|demonstrate|explain|mean|means|compare)\b", text))
    )
    if asks_bell_phase:
        answer.append(
            "The Bell phase demo shows how a relative phase becomes observable after a basis change. "
            "In the computational basis, the plus Bell state, minus Bell state, and 50/50 mixture "
            "all give 00 and 11 with 50% probability each. After applying H to both qubits, "
            "the plus state gives 00/11 at 50% each, the minus state gives 01/10 at 50% each, "
            "and the mixture gives all four outcomes at 25% each. The pure states have fixed "
            "even or odd parity; the mixture can produce either. One shot cannot identify the "
            "source with certainty, while repeated measurements can distinguish their distributions."
        )
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


def bell_phase_comparison(result):
    labels = ("00", "01", "10", "11")
    lines = ["Apply H to both qubits, then measure. SharkByte simulator probabilities:",
             "Input             00   01   10   11"]
    for name, values in result["probabilities"].items():
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
    receipt = None
    commands = {
        "/help": "Show this command list.",
        "/bell": "Sample the bundled Bell circuit and check its receipt.",
        "/bell-phase": "Compare three states after Hadamard gates.",
        "/qft": "Run the bundled six-qubit QFT in a 30-qubit register.",
        "/run FILE.sb": "Run a quantum circuit. Use /run-frontier FILE.sb for sparse circuits.",
        "/save FILE.json": "Save the last result to a new receipt file.",
        "/verify [FILE.json]": "Check the last receipt or a saved file.",
        "/replay FILE.json": "Verify and rerun the circuit stored in a saved receipt.",
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
                print(f"  {command:<25}{description}")
            continue
        if question == "/doctor":
            print(f"Chat backend: {backend}\nQuantum simulator: CPU", flush=True)
            subprocess.run([sys.executable, "-B", "-m", "sharkbyte_alpha", "doctor"], cwd=REPO)
            continue
        command, _, argument = question.partition(" ")
        argument = argument.strip()
        if argument.startswith('"') and argument.endswith('"'):
            argument = argument[1:-1]
        if command in {"/run", "/run-frontier", "/save", "/verify", "/replay", "/bell", "/qft"}:
            try:
                if command == "/verify":
                    candidate = read_receipt(argument) if argument else receipt
                    if candidate is None:
                        raise ValueError("Run a circuit first or supply a receipt path.")
                    check = verify(candidate)
                    print(check["status"], check["note"])
                elif command == "/replay":
                    print(replay(read_receipt(argument)))
                elif command == "/save":
                    if receipt is None:
                        raise ValueError("Run a circuit first.")
                    with Path(argument).open("xb") as stream:
                        stream.write(canonical(receipt) + b"\n")
                    print("Saved receipt:", argument)
                else:
                    mode = "frontier" if command in {"/qft", "/run-frontier"} else "quantum"
                    source_path = {
                        "/bell": REPO / "examples" / "bell.sb",
                        "/qft": FRONTIER / "qft6_in_30.sb",
                    }.get(command, Path(argument))
                    candidate = run_experiment(read_source(source_path), mode)
                    result = candidate["result"]
                    if mode == "frontier" and result["result"] != "PASS":
                        raise ValueError(result["reason"])
                    receipt = candidate
                    if command == "/bell":
                        bell_run = result["counts"], verify(receipt)
                        print("SharkByte runner:", result["counts"], bell_run[1]["status"])
                    elif mode == "frontier":
                        print(f"Frontier30 CPU: {result['qubits']} qubits, "
                              f"{result['peak_populated_states']} peak states, "
                              f"{result['support_cap']} support cap.")
                    else:
                        print(f"Statevector CPU: {result['qubits']} qubits, "
                              f"{result['shots']} shots, seed {result['seed']}.")
                    if command != "/bell":
                        print("Basis probabilities (up to eight):")
                        for basis, probability in list(result["probabilities"].items())[:8]:
                            print(f"  {basis}  {probability:.8g}")
                        print("Use /save FILE.json to export the complete result.")
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                print(f"{command}: {exc}")
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
            receipt = run_experiment(canonical(PHASE_SOURCES).decode("ascii"), "bell-phase")
            print("SharkByte runner:", bell_phase_comparison(receipt["result"]), flush=True)
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
            payload = json.dumps({"model": args.geniex_model, "messages": messages,
                                  "max_tokens": 384, "stream": False}).encode()
            try:
                with open_local("http://127.0.0.1:18181/v1/chat/completions",
                                data=payload, timeout=90) as response:
                    reply = json.loads(response.read(1_048_577))
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
