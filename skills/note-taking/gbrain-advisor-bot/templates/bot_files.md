# Bot file skeletons (copy + modify)

## retrieval.py
```python
import os, re, subprocess

HORMOZI_PREFIX = "experts/alex-hormozi/"

def _gbrain(args):
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.bun/bin") + ":" + env.get("PATH", "")
    r = subprocess.run(["gbrain"] + args, capture_output=True, text=True, env=env, timeout=60)
    return r.stdout

def _slugs_from(out, prefix, k):
    slugs = []
    for line in out.splitlines():
        if prefix in line:
            slug = re.sub(r'^\[[^\]]*\] +', '', line).split()[0]
            if slug.startswith(prefix) and slug not in slugs:
                slugs.append(slug)
        if len(slugs) >= k:
            break
    return slugs

def retrieve(query, k=6, prefix=HORMOZI_PREFIX):
    slugs = _slugs_from(_gbrain(["query", query, "--limit", "12"]), prefix, k)
    if not slugs:
        domain = ["offer","lead magnet","sales","pricing","value","focus",
                  "three pillar pitch","closer framework","cta formula"]
        merged = []
        for d in domain:
            merged += _slugs_from(_gbrain(["query", d, "--limit", "6"]), prefix, k)
        seen = set()
        for s in merged:
            if s not in seen:
                seen.add(s); slugs.append(s)
            if len(slugs) >= k: break
    return [{"slug": s, "text": _gbrain(["get", s])} for s in slugs]
```

## llm.py
```python
import os, requests

def synthesize(mode, query, notes):
    cfg = {
        "api_key": os.environ.get("OPENCODE_ZEN_API_KEY"),
        "base_url": os.environ.get("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1"),
        "model": os.environ.get("OPENCODE_ZEN_MODEL", "hy3-free"),
    }
    if not cfg["api_key"]:
        return "[retrieval-only] No key. Notes:\n\n" + "\n---\n".join(
            f"{n['slug']}\n{n['text'][:1500]}" for n in notes)
    context = "\n\n".join(f"[{n['slug']}]\n{n['text']}" for n in notes)
    sys = ("You are Alex Hormozi's advisory voice. Answer ONLY from the notes, "
           "cite slugs, mark inference [inference]. Mode: " + mode)
    r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {cfg['api_key']}"},
        json={"model": cfg["model"], "temperature": 0.4,
              "messages":[{"role":"system","content":sys+"\n\nNOTES:\n"+context},
                          {"role":"user","content":query}]},
        timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
```

## bot.py (argparse)
```python
import argparse, retrieval, llm
def main():
    a = argparse.ArgumentParser()
    a.add_argument("mode", choices=["ask","draft","brainstorm"])
    a.add_argument("query", nargs="+")
    args = a.parse_args()
    q = " ".join(args.query)
    notes = retrieval.retrieve(q)
    print(llm.synthesize(args.mode, q, notes))
if __name__ == "__main__":
    main()
```
