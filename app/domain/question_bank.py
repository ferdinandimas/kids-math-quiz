import random

def difficulty_from_answer(ans: int) -> str:
    if ans <= 10:
        return "easy"
    if ans <= 20:
        return "medium"
    if ans >= 50:
        return "hard"
    return "medium"

def make_q(qver: int, idx: int, a: int, op: str, b: int) -> dict:
    if op == "+":
        ans = a + b
        prompt = f"{a} + {b} = ?"
    elif op == "-":
        ans = a - b
        prompt = f"{a} - {b} = ?"
    else:
        raise ValueError("op must be '+' or '-'")

    return {
        "id": f"v{qver}_q{idx:04d}",
        "prompt": prompt,
        "answer": ans,
        "difficulty": difficulty_from_answer(ans),
        "op": "add" if op == "+" else "sub",
    }

def generate_bank_add_sub(
    qver: int,
    *,
    seed: int,
    target_size: int,
    single_digit_add: int,
    single_digit_sub: int,
    teen_add: int,
    teen_sub: int,
    two_digit_sub_v1: int,
    two_digit_sub_v2: int,
) -> list[dict]:
    rng = random.Random(seed)
    seen = set()
    out = []
    idx = 1

    def add_unique(a: int, op: str, b: int):
        nonlocal idx
        key = (a, op, b)
        if key in seen:
            return False
        if op == "-" and a < b:
            return False
        q = make_q(qver, idx, a, op, b)
        seen.add(key)
        out.append(q)
        idx += 1
        return True

    def fill(quota: int, gen_fn):
        tries = 0
        while quota > 0 and tries < 200000:
            a, op, b = gen_fn()
            if add_unique(a, op, b):
                quota -= 1
            tries += 1

    fill(single_digit_add, lambda: (rng.randint(1, 9), "+", rng.randint(1, 9)))
    fill(single_digit_sub, lambda: (rng.randint(1, 9), "-", rng.randint(1, 9)))
    fill(teen_add, lambda: (rng.randint(10, 20), "+", rng.randint(1, 9)))
    fill(teen_sub, lambda: (rng.randint(10, 20), "-", rng.randint(1, 9)))
    fill(two_digit_sub_v1, lambda: (rng.randint(20, 60), "-", rng.randint(1, 20)))
    fill(two_digit_sub_v2, lambda: (rng.randint(20, 99), "-", rng.randint(1, 50)))

    def topping():
        mode = rng.random()
        if mode < 0.45:
            return (rng.randint(1, 9), "+", rng.randint(1, 9))
        if mode < 0.70:
            return (rng.randint(1, 9), "-", rng.randint(1, 9))
        if mode < 0.85:
            return (rng.randint(10, 20), "+", rng.randint(1, 9))
        return (rng.randint(10, 20), "-", rng.randint(1, 9))

    fill(max(0, target_size - len(out)), topping)
    return out[:target_size]

def build_banks():
    bank_v1 = generate_bank_add_sub(
        1,
        seed=101,
        target_size=400,
        single_digit_add=50,
        single_digit_sub=50,
        teen_add=100,
        teen_sub=100,
        two_digit_sub_v1=70,
        two_digit_sub_v2=30,
    )

    bank_v2 = generate_bank_add_sub(
        2,
        seed=202,
        target_size=400,
        single_digit_add=20,
        single_digit_sub=20,
        teen_add=130,
        teen_sub=130,
        two_digit_sub_v1=30,
        two_digit_sub_v2=70,
    )

    q_by_id = {q["id"]: q for q in (bank_v1 + bank_v2)}
    return bank_v1, bank_v2, q_by_id