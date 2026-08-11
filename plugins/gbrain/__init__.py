# gbrain Memory Provider Plugin
# Full implementation will follow after task scaffolding

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from hermes_cli.config import cfg_get
import logging

logger = logging.getLogger(__name__)


def _load_plugin_config() -> dict:
    """Read optional JSON config written by save_config()."""
    try:
        cfg_path = Path(self._dir) / "config.json"
        if cfg_path.is_file():
            import json
            return json.loads(cfg_path.read_text())
    except Exception:
        pass
    return {}


class GBrainProvider(MemoryProvider):
    """Memory provider that shells out to the gbrain CLI."""

    def __init__(self):
        # defaults; can be overridden by env or saved config
        self._bin: str = os.environ.get("GBRAIN_BIN", str(Path.home() / ".bun" / "bin" / "gbrain"))
        self._dir: str = os.environ.get("GBRAIN_DIR", str(Path.home() / "gbrain"))
        self._limit: int = 5
        self._writable: bool = True  # flipped False in initialize() for non-primary contexts

    # ---------- MemoryProvider ABC ----------
    @property
    def name(self) -> str:
        return "gbrain"

    def is_available(self) -> bool:
        return Path(self._bin).exists() and Path(self._dir).is_dir()

    def initialize(self, session_id: str, **kwargs) -> None:
        agent_context = kwargs.get("agent_context", "primary")
        self._writable = agent_context in ("primary", "flush")
        # lightweight availability check
        self._run(["--version"], timeout=5.0)  # ignore output; failure already caught by is_available

    # ---- core hooks ----
    def system_prompt_block(self) -> str:
        return (
            "You have access to the user's gbrain second brain (PGLite + vector embeddings). "
            "Before answering questions about the user, their projects, or anything they may have captured, "
            "ALWAYS check gbrain FIRST using the gbrain tool or the automatic recall block. "
            "Store durable facts with gbrain capture (or the memory tool, which mirrors writes)."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        q = (query or "").strip()
        if len(q) < 3:
            return ""
        out = self._run(["query", q, "--limit", str(self._limit)])
        if out is None:
            out = self._run(["search", q, "--limit", str(self._limit)])
        return self._format(out, q)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        # v1: no-op; synchronous prefetch is fine (local SQLite fast)
        pass

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "", messages: Optional[List[Dict[str, Any]]] = None) -> None:
        # writes handled via on_memory_write
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [self._tool_schema()]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != self.name:
            raise NotImplementedError(f"Provider {self.name} does not handle tool {tool_name}")
        action = args.get("action")
        if action in ("query", "search"):
            out = self._run([action, args.get("query", ""), "--limit", str(args.get("limit", self._limit))])
            if out is None:
                return '{"error": "gbrain command failed"}'
            return self._format_json(out)
        elif action == "salience":
            days = args.get("days", 7)
            out = self._run(["salience", "--days", str(days), "--limit", str(args.get("limit", self._limit))])
            if out is None:
                return '{"error": "gbrain salience failed"}'
            return self._format_salience_json(out)
        elif action == "capture":
            content = args.get("content", "")
            out = self._run(["capture", content, "--quiet", "--json"], timeout=30)
            if out is None:
                return '{"error": "gbrain capture failed"}'
            return out  # already JSON
        else:
            return f'{{"error": "unsupported action {action}"}}'

    def shutdown(self) -> None:
        pass

    def on_memory_write(self, action: str, target: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not getattr(self, "_writable", True) or action == "remove":
            return
        self._run(["capture", f"[hermes:{target}] {content}", "--quiet", "--json"], timeout=30)

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        pass

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "gbrain_bin", "type": "text", "description": "Path to gbrain binary", "default": self._bin},
            {"key": "gbrain_dir", "type": "text", "description": "Path to gbrain directory (~/.gbrain)", "default": self._dir},
            {"key": "recall_limit", "type": "integer", "description": "How many recall items to inject per turn", "default": self._limit, "minimum": 1, "maximum": 20},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        cfg_dir = Path(self._dir)
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(__import__("json").dumps(values, indent=2))

    def backup_paths(self) -> List[str]:
        return [self._dir]

    # ---------- helpers ----------
    def _run(self, args: list, stdin: str | None = None, timeout: float = 25.0) -> str | None:
        env = dict(os.environ)
        env["PATH"] = f"{Path(self._bin).parent}:" + env.get("PATH", "")
        try:
            p = subprocess.run([self._bin, *args], input=stdin, capture_output=True, text=True, timeout=timeout, env=env, cwd=self._dir)
        except Exception as e:
            logger.warning("gbrain %s error: %s", args[0], e)
            return None
        if p.returncode != 0:
            logger.warning("gbrain %s rc=%s: %s", args[0], p.returncode, p.stderr.strip()[:300])
            return None
        return p.stdout

    def _format(self, raw: Optional[str], query: str) -> str:
        if not raw:
            return ""
        lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip() and not ln.startswith("UPGRADE_AVAILABLE")]
        hits: list[tuple[float, str, str]] = []  # (score, slug, title)
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("[") and "]" in line and "--" in line:
                try:
                    score_part, rest = line.split("]", 1)
                    score = float(score_part[1:])
                    if " -- " in rest:
                        slug_title, excerpt = rest.split(" -- ", 1)
                        slug = slug_title.strip()
                        title = excerpt.strip()
                        # collect following non-blank lines as excerpt until next hit or empty
                        i += 1
                        while i < len(lines) and lines[i] and not lines[i].startswith("["):
                            title += " " + lines[i].strip()
                            i += 1
                        hits.append((score, slug, title))
                        continue
                except ValueError:
                    pass
            i += 1
        if not hits:
            return ""
        hits.sort(key=lambda x: x[0], reverse=True)
        out_lines = [f"GBRAIN RECALL (query: {query}):"]
        for _, slug, title in hits[: self._limit]:
            out_lines.append(f"- {slug}: {title[:600]}")
        return "\n".join(out_lines)

    def _format_json(self, raw: Optional[str]) -> str:
        if not raw:
            return '{"results": []}'
        # gbrain search --json already returns valid JSON; just pass through
        return raw.strip()

    def _format_salience_json(self, raw: Optional[str]) -> str:
        if not raw:
            return '{"results": []}'
        # salience text table -> convert to JSON array of objects
        lines = [ln.rstrip() for ln in raw.splitlines() if ln.strip()]
        results = []
        for ln in lines:
            if ln.startswith("#") or ln.startswith("---"):
                continue
            parts = [p.strip() for p in ln.split()]
            if len(parts) >= 5:
                try:
                    score = float(parts[0])
                    slug = " ".join(parts[3:-1])  # slug may contain spaces? gbrain slugs have no spaces; but be safe
                    title = " ".join(parts[4:])
                    results.append({"score": score, "slug": slug, "title": title})
                except ValueError:
                    pass
        return __import__("json").dumps({"results": results})


def register(ctx):
    """Plugin entry-point."""
    try:
        provider = GBrainProvider()
        if provider.is_available():
            ctx.register_memory_provider(provider)
            logger.info("gbrain memory provider registered")
        else:
            logger.warning("gbrain memory provider not available (bin=%s dir=%s)", provider._bin, provider._dir)
    except Exception as e:
        logger.exception("Failed to register gbrain provider: %s", e)

