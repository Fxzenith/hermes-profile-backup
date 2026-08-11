---
title: Free AI APIs for Chat Applications
description: Curated list of free API keys and features for building AI chat slash commands (e.g., /aichat)
source: public-apis/public-apis repository + agent-reach integration research
date: 2026-08-08
---

# Free AI APIs for Chat Applications

Comprehensive reference for wiring up an `/aichat` slash command with free-tier LLM inference, search, tools, and agent-reach channels.

## 🎯 Top Free LLM Inference APIs

| API | Free Tier | Models | Key Features |
|-----|-----------|--------|--------------|
| **Groq** | ✅ Generous | Llama 3.1 (70B/8B), Mixtral, Gemma 2 | Ultra-fast LPU inference, streaming, OpenAI-compatible, tool calling |
| **Hugging Face Inference** | ✅ Rate-limited | 100k+ (Llama, Mistral, Qwen, Phi) | Serverless, embeddings, text-gen, conversational |
| **Jina AI** | ✅ Free tier | jina-embeddings, jina-reranker, jina-reader | Embeddings, reranking, web extraction (reader needs no key: `https://r.jina.ai/URL`) |
| **DeepAI** | ✅ Free tier | Various text/image | Text generation, image processing, NSFW classification |
| **NLP Cloud** | ✅ Free tier | spaCy + transformers | NER, sentiment, classification, summarization, QA |
| **GoldBean (Baidu)** | ✅ Free tier | ERNIE LLM, OCR, Translation | Chinese NLP, OCR, multilingual |
| **Brainshop.ai** | ✅ Free | Custom "brain" | Personalized chatbot with memory |

## 🔍 Search & Web Access (RAG / Tool Use)

| API | Free Tier | Use Case |
|-----|-----------|----------|
| **Suprsonic** | ✅ | Unified: web search, scrape, enrich, image gen, TTS, STT, messaging — one key, 20+ caps |
| **Webclaw** | ✅ | Web extraction for LLMs: scrape, crawl, search, summarize |
| **ScriptMasterLabs MCP** | x402 pay-per-use | MCP server: web search, social search, LLM chat |
| **Jina Reader** | ✅ No key | Instant article extraction via `curl https://r.jina.ai/URL` |
| **SerpStack / Zenserp** | ✅ | Google Search results API |
| **NewsAPI / GNews / Currents** | ✅ | Live news headlines for context injection |

## 🧠 Features to Add to `/aichat`

| Feature | APIs | Implementation |
|---------|------|----------------|
| Web Search / RAG | Suprsonic, Webclaw, Jina Reader, SerpStack | `/aichat --search "query"` → inject results |
| Code Execution | Codex, Wandbox, Replit | `/aichat --code "python: print('hi')"` |
| Image Generation | DeepAI, Glitterly, justmeme.wtf, Suprsonic | `/aichat --image "prompt"` |
| Embeddings / Semantic Search | Jina AI, Hugging Face | Store chat history, retrieve context |
| Reranking | Jina AI, Cohere (free tier) | Improve RAG retrieval |
| Summarization | NLP Cloud, Hugging Face, Suprsonic | `/aichat --summarize <url/text>` |
| Translation | LibreTranslate (no key), GoldBean, Langbly | `/aichat --translate "text" --lang es` |
| Sentiment / Toxicity | Perspective API, NLP Cloud, Tisane | Auto-moderate, flag harmful content |
| Speech (STT/TTS) | Suprsonic, Audexum, ElevenLabs (free) | Voice chat interface |
| Web Scraping | Webclaw, Thunderbit, ZenRows, Scrapestack | `/aichat --scrape <url>` |
| Document Processing | DocStruct, OCR.space, iLovePDF | `/aichat --pdf <file>` → extract text |
| Fact Checking | Wikidata, Wikipedia, WolframAlpha | Ground responses in verified data |
| Token Cost Estimation | AI Economics Tools | Show cost per message |

## 🛠 Agent-Reach Channels (Zero-Config on This VPS)

| Channel | What It Gives `/aichat` | Setup |
|---------|------------------------|-------|
| **Web (Jina Reader)** | `curl https://r.jina.ai/URL` for any page | Zero-config |
| **YouTube (yt-dlp)** | `/aichat --youtube <url>` → transcript + summary | Zero-config |
| **GitHub (gh CLI)** | `/aichat --repo <owner/repo>` → read code/issues/PRs | Zero-config (needs `gh auth login`) |
| **RSS/Feeds** | `/aichat --feed <url>` → latest articles as context | Zero-config |
| **Twitter/X** | `/aichat --tweet <id>` or `--search "@handle"` | Needs cookies: `agent-reach configure twitter-cookies --stdin` |
| **Reddit (rdt-cli)** | `/aichat --reddit <subreddit/post>` | Needs cookie: `rdt-cli` credential.json |

> **Cookie Setup**: For Twitter/Reddit, export cookies from browser (Cookie-Editor extension → Header String). See `references/twitter-cli-cookie-debug.md` and `references/reddit-rdt-cli-setup.md`.

## 📋 Recommended Starter Stack

| Priority | API | Key URL | Why |
|----------|-----|---------|-----|
| 1 | **Groq** | console.groq.com | Fastest free LLM, OpenAI-compatible, tool calling |
| 2 | **Hugging Face** | hf.co/settings/tokens | Massive model zoo, embeddings, fallback |
| 3 | **Jina AI** | jina.ai | Free embeddings + reranker + web reader (no key for reader) |
| 4 | **Suprsonic** | suprsonic.ai | All-in-one: search, scrape, image gen, TTS/STT |
| 5 | **NLP Cloud** | nlpcloud.io | Specialized NLP (NER, sentiment, classify) |
| 6 | **Perspective API** | perspectiveapi.com | Free toxicity/safety scoring |
| 7 | **LibreTranslate** | libretranslate.com | No key needed, self-hostable translation |

## 🔧 Example `/aichat` Command Structure

```bash
/aichat [options] "your prompt"

Options:
  --model <name>           # groq:llama-3.1-70b, hf:mistral-7b, etc.
  --search "query"         # Web search + inject results (Suprsonic/Jina)
  --scrape <url>           # Extract page content (Webclaw)
  --youtube <url>          # Transcript + summary (yt-dlp via agent-reach)
  --github <owner/repo>    # Repo context (gh CLI via agent-reach)
  --image "prompt"         # Generate image (DeepAI/Suprsonic)
  --speak                  # TTS response (Suprsonic/Audexum)
  --translate --lang <code> # Translate response (LibreTranslate)
  --summarize <url/text>   # Summarize (NLP Cloud)
  --safe                   # Enable Perspective toxicity filter
  --rag <collection>       # Query local vector store (Jina embeddings)
  --code "lang: code"      # Execute code (Codex/Wandbox)
  --stream                 # Stream tokens (Groq/HF support this)
```

## 📝 Notes

- All APIs listed have genuine free tiers (not just trials)
- Agent-reach provides zero-config web/YouTube/GitHub/RSS on this VPS
- Twitter/Reddit require cookie auth (ban risk on primary accounts — use secondary)
- Jina Reader (`https://r.jina.ai/URL`) works without any API key
- Suprsonic is uniquely valuable: one key unlocks 20+ agent capabilities
- Local vector DB (PGLite like gbrain, or Chroma) recommended for RAG with Jina embeddings