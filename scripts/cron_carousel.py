#!/usr/bin/env python3
"""
Instagram Carousel Auto-Generator & Poster (Cron Job)

This script:
1. Fetches content from a source (JSON file, RSS, or generates from templates)
2. Creates carousel configs
3. Generates slides using thread-to-carousel.py
4. Posts to Instagram via Graph API

Setup:
1. Create a Facebook App at https://developers.facebook.com
2. Add Instagram Basic Display or Instagram Graph API
3. Get long-lived access token with instagram_content_publish permission
4. Connect Instagram Business account to Facebook Page
5. Add credentials to .env

Usage (cron):
    0 9 * * * cd /root/autoclipping/instagram-thread-carousel && python3 scripts/cron_carousel.py >> logs/cron.log 2>&1
"""

import json
import os
import sys
import subprocess
import shutil
import random
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Load .env
def load_env():
    # Try working directory first (for cron jobs), then script directory
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

load_env()

# ============================================================
# CONFIGURATION
# ============================================================

# Instagram Graph API
INSTAGRAM_APP_ID = os.environ.get("INSTAGRAM_APP_ID")
INSTAGRAM_APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_USER_ID = os.environ.get("INSTAGRAM_USER_ID")  # Instagram Business Account ID

# Content source - choose one:
# - "templates": Use built-in templates (rotating topics)
# - "json": Read from content/source.json
# - "rss": Fetch from RSS feed (RSS_FEED_URL required)
# - "api": Call custom API (CONTENT_API_URL required)
CONTENT_SOURCE = os.environ.get("CONTENT_SOURCE", "templates")

RSS_FEED_URL = os.environ.get("RSS_FEED_URL")
CONTENT_API_URL = os.environ.get("CONTENT_API_URL")

# Posting schedule
POST_TIME = os.environ.get("POST_TIME", "09:00")  # HH:MM 24h
TIMEZONE = os.environ.get("TIMEZONE", "UTC")

# Output
WORKSPACE_ROOT = Path(__file__).resolve().parents[1] / "workspace"
LOGS_DIR = Path(__file__).resolve().parents[1] / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Default profile (can be overridden per carousel)
DEFAULT_PROFILE = {
    "name": os.environ.get("DEFAULT_PROFILE_NAME", "Ze Nith"),
    "handle": os.environ.get("DEFAULT_PROFILE_HANDLE", "@zenith"),
    "verified": os.environ.get("DEFAULT_PROFILE_VERIFIED", "true").lower() == "true",
    "headshot": os.environ.get("DEFAULT_PROFILE_HEADSHOT", "headshots/default-headshot.png"),
}

# ============================================================
# CONTENT TEMPLATES (for CONTENT_SOURCE="templates")
# ============================================================

TEMPLATES = [
    {
        "topic": "productivity",
        "title": "The Compound Effect",
        "hook": "Small habits create massive results over time.",
        "tweets": [
            "Most people overestimate what they can do in a day.\n\nAnd underestimate what they can do in a year.",
            "The math is simple but brutal:\n\n→ 1% better daily = 37x in a year\n→ 1% worse daily = near zero\n\nConsistency beats intensity every time.",
            "You don't need motivation.\nYou need a system.\n\nMotivation is a feeling. Systems are reliable.\n\nBuild the system once. Let it run forever.",
            "The best time to start was years ago.\n\nThe second best time is right now.\n\nYour future self will thank you.",
        ],
        "theme": "light",
    },
    {
        "topic": "mindset",
        "title": "Action Over Perfection",
        "hook": "Done is better than perfect. Always.",
        "tweets": [
            "Perfectionism is just fear in a tuxedo.\n\nIt whispers: \"Wait until it's ready.\"\n\nIt's never ready. Ship it anyway.",
            "The gap between where you are and where you want to be...\n\nIs filled with imperfect action.\nNot perfect plans.",
            "Every expert was once a beginner who refused to quit.\n\nThe only difference: they started before they felt ready.\n\nYou can too.",
            "Progress > Perfection\n\nSave this carousel. Read it when you're stuck.\n\nThen take one messy step forward.",
        ],
        "theme": "dark",
    },
    {
        "topic": "learning",
        "title": "How to Learn Anything Fast",
        "hook": "The 80/20 rule applies to learning too.",
        "tweets": [
            "You don't need 10,000 hours.\n\nYou need the RIGHT 20 hours.\n\nFocus on the 20% that gives 80% of results.",
            "Step 1: Deconstruct the skill\nWhat are the core sub-skills?\n\nStep 2: Learn enough to self-correct\nGet to \"good enough to practice\" fast.\n\nStep 3: Remove barriers\nMake practice frictionless.\n\nStep 4: Practice 45 min/day for 20 days.",
            "Immersion beats intensity.\n\n15 minutes daily > 3 hours once a week.\n\nYour brain consolidates during sleep.\nSpaced repetition wins.",
            "Teach it to learn it.\n\nIf you can't explain it simply, you don't understand it.\n\nWrite a tweet. Record a video. Explain to a friend.\n\nTeaching forces clarity.",
        ],
        "theme": "light",
    },
    {
        "topic": "business",
        "title": "Building Leverage",
        "hook": "Code and media are permissionless leverage.",
        "tweets": [
            "Labor leverage: people work for you (hard to scale)\nCapital leverage: money works for you (needs money)\n\nCode leverage: write once, run forever (zero marginal cost)\nMedia leverage: create once, distribute infinitely (zero marginal cost)",
            "The internet made distribution free.\n\nYour job: create something worth distributing.\n\nThen let the network do the work.",
            "Build assets, not rent.\n\n→ Code = asset\n→ Content = asset\n→ Audience = asset\n→ Relationships = asset\n\nEmployment = renting your time.\nOwnership = building assets.",
            "Start small. Think long-term.\n\nEvery piece of code you write.\nEvery article you publish.\nEvery video you make.\n\nIs a soldier in your army of leverage.\n\nDeploy them wisely.",
        ],
        "theme": "dark",
    },
]

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def log(msg: str, level: str = "INFO"):
    """Log to console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [{level}] {msg}"
    print(log_msg)
    (LOGS_DIR / "cron.log").write_text(
        (LOGS_DIR / "cron.log").read_text() + log_msg + "\n"
        if (LOGS_DIR / "cron.log").exists() else log_msg + "\n"
    )

def get_next_carousel_folder() -> Path:
    """Get the next carousel workspace folder (by date)."""
    today = datetime.now().strftime("%Y-%m-%d")
    base = WORKSPACE_ROOT / today
    base.mkdir(parents=True, exist_ok=True)
    
    # Find existing carousels today
    existing = [d for d in base.iterdir() if d.is_dir() and d.name.startswith("carousel-")]
    next_num = len(existing) + 1
    folder = base / f"carousel-{next_num:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ref").mkdir(exist_ok=True)
    return folder

def select_template() -> Dict:
    """Select a template (weighted random or sequential)."""
    # For now, random selection
    return random.choice(TEMPLATES)

def load_json_content() -> Optional[Dict]:
    """Load content from JSON file."""
    json_path = Path(__file__).resolve().parents[1] / "content" / "source.json"
    if json_path.exists():
        return json.loads(json_path.read_text())
    return None

def fetch_rss_content() -> Optional[List[Dict]]:
    """Fetch content from RSS feed."""
    if not RSS_FEED_URL:
        return None
    try:
        import feedparser
        feed = feedparser.parse(RSS_FEED_URL)
        items = []
        for entry in feed.entries[:5]:
            items.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", "")[:500],
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
        return items
    except Exception as e:
        log(f"RSS fetch failed: {e}", "ERROR")
        return None

def fetch_api_content() -> Optional[Dict]:
    """Fetch content from custom API."""
    if not CONTENT_API_URL:
        return None
    try:
        resp = requests.get(CONTENT_API_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log(f"API fetch failed: {e}", "ERROR")
        return None

def build_carousel_config(template: Dict, folder: Path) -> Path:
    """Build config.json for thread-to-carousel.py."""
    
    # Convert template tweets to slide format
    slides = []
    tweets = template["tweets"]
    
    # Slide 1: Hook (always single)
    slides.append({"tweets": [{"text": tweets[0], "image": None}]})
    
    # Remaining tweets: combine short ones, keep long ones solo
    i = 1
    while i < len(tweets):
        tweet = tweets[i]
        # Check if next tweet exists and both are short (< 150 chars, no image)
        if (i + 1 < len(tweets) and 
            len(tweet) < 150 and 
            len(tweets[i + 1]) < 150):
            slides.append({
                "tweets": [
                    {"text": tweet, "image": None},
                    {"text": tweets[i + 1], "image": None}
                ]
            })
            i += 2
        else:
            slides.append({"tweets": [{"text": tweet, "image": None}]})
            i += 1
    
    config = {
        "profile": DEFAULT_PROFILE,
        "theme": template.get("theme", "light"),
        "slides": slides
    }
    
    config_path = folder / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    log(f"Created config: {config_path}")
    return config_path

def generate_carousel(config_path: Path, output_dir: Path) -> List[Path]:
    """Run thread-to-carousel.py to generate slides."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "thread-to-carousel.py"
    
    result = subprocess.run(
        [sys.executable, str(script_path), str(config_path), str(output_dir)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1]
    )
    
    if result.returncode != 0:
        log(f"Generation failed: {result.stderr}", "ERROR")
        raise RuntimeError(f"Carousel generation failed: {result.stderr}")
    
    log(f"Generation output: {result.stdout.strip()}")
    
    # Collect generated slides
    slides = sorted(output_dir.glob("slide-*.png")) + sorted(output_dir.glob("slide-*.mp4"))
    log(f"Generated {len(slides)} slides")
    return slides

# ============================================================
# INSTAGRAM GRAPH API POSTING
# ============================================================

def get_long_lived_token() -> Optional[str]:
    """Exchange short-lived token for long-lived (60 days)."""
    if not INSTAGRAM_APP_ID or not INSTAGRAM_APP_SECRET or not INSTAGRAM_ACCESS_TOKEN:
        return None
    
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": INSTAGRAM_APP_SECRET,
        "fb_exchange_token": INSTAGRAM_ACCESS_TOKEN,
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token")
    except Exception as e:
        log(f"Token exchange failed: {e}", "ERROR")
        return None

def create_media_container(image_url: str, caption: str, is_carousel: bool = False, children: Optional[List[str]] = None) -> Optional[str]:
    """Create a media container (upload) for Instagram."""
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_USER_ID:
        log("Missing Instagram credentials", "ERROR")
        return None
    
    url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_USER_ID}/media"
    
    if is_carousel and children:
        # Carousel: create children first, then parent
        data = {
            "media_type": "CAROUSEL",
            "children": children,
            "caption": caption,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }
    else:
        # Single image/video
        data = {
            "image_url": image_url,
            "caption": caption,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }
    
    try:
        resp = requests.post(url, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        log(f"Container creation failed: {e}", "ERROR")
        if hasattr(e, 'response') and e.response is not None:
            log(f"Response: {e.response.text}", "ERROR")
        return None

def upload_image_to_temp_host(image_path: Path) -> Optional[str]:
    """
    Upload image to a temporary host.
    In production, use: AWS S3, Cloudflare R2, Imgur, or your own CDN.
    For local testing, start a local HTTP server and return the URL.
    """
    # Check if local test server is running
    test_server_url = os.environ.get("LOCAL_TEST_SERVER_URL")
    if test_server_url:
        # Copy to server's public folder
        # LOCAL_TEST_SERVER_URL should be like http://localhost:8080
        # The public directory should be at the server root
        from urllib.parse import urlparse
        parsed = urlparse(test_server_url)
        # Default public dir location for local test server
        public_dir = Path("/root/test_server/public")
        if public_dir.exists():
            dest = public_dir / image_path.name
            shutil.copy2(image_path, dest)
            port = parsed.port or 8080
            return f"http://localhost:{port}/{image_path.name}"
        else:
            log(f"Test server public dir not found: {public_dir}", "WARN")
    
    # Try Imgur API if configured
    imgur_client_id = os.environ.get("IMGUR_CLIENT_ID")
    if imgur_client_id:
        return upload_to_imgur(image_path, imgur_client_id)
    
    # Try Cloudflare R2 if configured
    r2_endpoint = os.environ.get("R2_ENDPOINT")
    r2_access_key = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    r2_bucket = os.environ.get("R2_BUCKET")
    if all([r2_endpoint, r2_access_key, r2_secret_key, r2_bucket]):
        return upload_to_r2(image_path, r2_endpoint, r2_access_key, r2_secret_key, r2_bucket)
    
    # Try AWS S3 if configured
    s3_bucket = os.environ.get("S3_BUCKET")
    s3_region = os.environ.get("S3_REGION", "us-east-1")
    if s3_bucket:
        return upload_to_s3(image_path, s3_bucket, s3_region)
    
    log(f"WARNING: No image upload configured for {image_path}", "WARN")
    log("Set LOCAL_TEST_SERVER_URL, IMGUR_CLIENT_ID, or R2/S3 credentials", "WARN")
    return None


def upload_to_imgur(image_path: Path, client_id: str) -> Optional[str]:
    """Upload to Imgur anonymously."""
    try:
        with open(image_path, "rb") as f:
            files = {"image": f}
            headers = {"Authorization": f"Client-ID {client_id}"}
            resp = requests.post("https://api.imgur.com/3/image", files=files, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()["data"]["link"]
    except Exception as e:
        log(f"Imgur upload failed: {e}", "ERROR")
        return None


def upload_to_r2(image_path: Path, endpoint: str, access_key: str, secret_key: str, bucket: str) -> Optional[str]:
    """Upload to Cloudflare R2 (S3-compatible)."""
    try:
        import boto3
        from botocore.config import Config
        
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        
        key = f"carousel/{datetime.now().strftime('%Y%m%d')}/{image_path.name}"
        s3.upload_file(str(image_path), bucket, key, ExtraArgs={"ACL": "public-read"})
        return f"{endpoint}/{bucket}/{key}"
    except Exception as e:
        log(f"R2 upload failed: {e}", "ERROR")
        return None


def upload_to_s3(image_path: Path, bucket: str, region: str) -> Optional[str]:
    """Upload to AWS S3."""
    try:
        import boto3
        from botocore.config import Config
        
        s3 = boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))
        
        key = f"carousel/{datetime.now().strftime('%Y%m%d')}/{image_path.name}"
        s3.upload_file(str(image_path), bucket, key, ExtraArgs={"ACL": "public-read"})
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    except Exception as e:
        log(f"S3 upload failed: {e}", "ERROR")
        return None

def publish_media(container_id: str) -> bool:
    """Publish a media container."""
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_USER_ID:
        return False
    
    url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_USER_ID}/media_publish"
    data = {
        "creation_id": container_id,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }
    
    try:
        resp = requests.post(url, data=data, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        log(f"Published: {result}")
        return True
    except Exception as e:
        log(f"Publish failed: {e}", "ERROR")
        if hasattr(e, 'response') and e.response is not None:
            log(f"Response: {e.response.text}", "ERROR")
        return False

def post_carousel_to_instagram(slides: List[Path], caption: str) -> bool:
    """Post a carousel to Instagram via Graph API."""
    
    # Upload all slides and get URLs
    image_urls = []
    for slide in slides:
        url = upload_image_to_temp_host(slide)
        if not url:
            log(f"Failed to upload {slide}", "ERROR")
            return False
        image_urls.append(url)
    
    # Create child containers for each slide
    child_ids = []
    for url in image_urls:
        container_id = create_media_container(url, "", is_carousel=False)
        if not container_id:
            return False
        child_ids.append(container_id)
        log(f"Created child container: {container_id}")
    
    # Create parent carousel container
    parent_id = create_media_container("", caption, is_carousel=True, children=child_ids)
    if not parent_id:
        return False
    log(f"Created parent container: {parent_id}")
    
    # Publish
    return publish_media(parent_id)

# ============================================================
# MAIN CRON JOB
# ============================================================

def run_cron_job():
    """Main cron job entry point."""
    log("=" * 50)
    log("Starting Instagram Carousel Cron Job")
    
    # Check credentials
    if not INSTAGRAM_ACCESS_TOKEN:
        log("ERROR: INSTAGRAM_ACCESS_TOKEN not set in .env", "ERROR")
        log("Get a token from Facebook Graph API Explorer with instagram_content_publish", "ERROR")
        return 1
    
    if not INSTAGRAM_USER_ID:
        log("ERROR: INSTAGRAM_USER_ID not set in .env", "ERROR")
        log("This is your Instagram Business Account ID", "ERROR")
        return 1
    
    # Get content
    template = None
    
    if CONTENT_SOURCE == "json":
        content = load_json_content()
        if content:
            template = content
    elif CONTENT_SOURCE == "rss":
        items = fetch_rss_content()
        if items:
            # Convert first RSS item to template format
            item = items[0]
            template = {
                "topic": "rss",
                "title": item["title"],
                "hook": item["summary"][:200],
                "tweets": [item["summary"][:280], f"Read more: {item['link']}"],
                "theme": "light",
            }
    elif CONTENT_SOURCE == "api":
        content = fetch_api_content()
        if content:
            template = content
    else:
        # Default: templates
        template = select_template()
    
    if not template:
        log("No content available", "ERROR")
        return 1
    
    log(f"Selected template: {template['topic']} - {template['title']}")
    
    # Create workspace
    folder = get_next_carousel_folder()
    log(f"Workspace: {folder}")
    
    # Build config
    config_path = build_carousel_config(template, folder)
    
    # Generate carousel
    try:
        slides = generate_carousel(config_path, folder)
    except Exception as e:
        log(f"Generation error: {e}", "ERROR")
        return 1
    
    if not slides:
        log("No slides generated", "ERROR")
        return 1
    
    # Build caption
    hashtags = " #productivity #mindset #growth #habits #success #motivation"
    caption = f"{template['hook']}\n\n{hashtags}"
    
    # Post to Instagram
    log("Posting to Instagram...")
    success = post_carousel_to_instagram(slides, caption)
    
    if success:
        log("✅ Carousel posted successfully!")
        
        # Save metadata
        meta = {
            "posted_at": datetime.now().isoformat(),
            "template": template["topic"],
            "title": template["title"],
            "slides": [str(s) for s in slides],
            "caption": caption,
        }
        (folder / "post_meta.json").write_text(json.dumps(meta, indent=2))
    else:
        log("❌ Failed to post to Instagram", "ERROR")
        return 1
    
    log("Cron job completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(run_cron_job())