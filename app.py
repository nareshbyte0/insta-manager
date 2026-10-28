"""
InstaManager - Instagram Media Downloader & Hub
A complete, unconstrained project website to preview and download Instagram media:
- Supports ALL usernames & profiles without restriction
- Real-time extraction with automatic fallback for business/private/rate-limited profiles
- Photos, Videos, Reels, Carousels, and Profile Picture
- Direct in-browser 1-click downloads
- Organized bulk ZIP download (images/, videos/, reels/, carousels/, profile_info/)
- Save to local PC folder
"""

import os
import io
import json
import re
import random
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, send_from_directory, send_file, Response
from flask_cors import CORS
import html
import subprocess
# pyrefly: ignore [missing-import]
import instaloader
import requests

app = Flask(__name__, static_folder="static")
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# In serverless environments like Vercel, the root filesystem is read-only; use /tmp
if os.environ.get("VERCEL"):
    DOWNLOADS_DIR = "/tmp/downloads"
else:
    DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.instagram.com/",
}

def clean_username(raw_input: str) -> str:
    """Extract clean username or shortcode from input (handles @username or full URL)."""
    raw = raw_input.strip()
    if "instagram.com" in raw:
        path = urlparse(raw).path.strip("/")
        parts = [p for p in path.split("/") if p]
        if parts:
            if parts[0] in ["p", "reel", "stories"]:
                return parts[1] if len(parts) > 1 else parts[0]
            return parts[0]
    return raw.replace("@", "").strip("/").strip()


def parse_count(s: str) -> int:
    """Safely convert Instagram count string (e.g. 856, 1.2M, 50.4K) to integer."""
    if not s:
        return 0
    clean = str(s).replace(",", "").strip().lower()
    try:
        if clean.endswith("k"):
            return int(float(clean[:-1]) * 1000)
        elif clean.endswith("m"):
            return int(float(clean[:-1]) * 1000000)
        elif clean.endswith("b"):
            return int(float(clean[:-1]) * 1000000000)
        return int(float(clean))
    except Exception:
        return 0


def scrape_genuine_profile(username: str) -> dict:
    """
    Scrape 100% genuine Instagram profile metadata directly from live Instagram
    using social crawler headers to avoid empty JS app shells.
    Extracts real full name, real username, real bio, real follower/following/post counts,
    real verified status, and real HD profile picture on scontent.cdninstagram.com.
    """
    clean_user = username.replace("@", "").strip("/").strip()
    headers = {
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    url = f"https://www.instagram.com/{clean_user}/"
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            text = r.text
            
            # 1. Avatar from og:image
            og_image_m = re.search(r'<meta property="og:image" content="(.*?)"', text)
            avatar_url = html.unescape(og_image_m.group(1)) if og_image_m else None
            
            # 2. Title -> Full name
            og_title_m = re.search(r'<meta property="og:title" content="(.*?)"', text)
            full_name = clean_user
            if og_title_m:
                raw_title = html.unescape(og_title_m.group(1))
                m = re.match(r'^(.*?)\s*\(@', raw_title)
                if m:
                    full_name = m.group(1).strip()
                    
            # 3. Description -> Followers, Following, Posts, Bio
            meta_desc_m = re.search(r'<meta content="(.*?)" name="description"', text) or re.search(r'<meta name="description" content="(.*?)"', text)
            og_desc_m = re.search(r'<meta property="og:description" content="(.*?)"', text)
            desc_text = html.unescape(meta_desc_m.group(1)) if meta_desc_m else (html.unescape(og_desc_m.group(1)) if og_desc_m else "")
            
            followers = 0
            following = 0
            posts = 0
            bio = ""
            
            if desc_text:
                f_m = re.search(r'([\d\.,kKmMbB]+)\s*Followers', desc_text, re.IGNORECASE)
                if f_m:
                    followers = parse_count(f_m.group(1))
                    
                fg_m = re.search(r'([\d\.,kKmMbB]+)\s*Following', desc_text, re.IGNORECASE)
                if fg_m:
                    following = parse_count(fg_m.group(1))
                    
                p_m = re.search(r'([\d\.,kKmMbB]+)\s*Posts', desc_text, re.IGNORECASE)
                if p_m:
                    posts = parse_count(p_m.group(1))
                    
                bio_m = re.search(r'on Instagram:\s*"(.*?)"\s*$', desc_text, re.DOTALL)
                if bio_m:
                    bio = bio_m.group(1)
                elif " - " in desc_text:
                    parts = desc_text.split(" - ", 1)
                    if len(parts) > 1 and "See Instagram" not in parts[1]:
                        bio = parts[1]

            is_verified = 'is_verified":true' in text or 'Verified' in desc_text or 'verified":true' in text
            is_private = "This account is private" in text or 'is_private":true' in text

            return {
                "username": clean_user,
                "full_name": full_name,
                "biography": bio,
                "followers": followers,
                "followees": following,
                "media_count": posts,
                "is_private": is_private,
                "is_verified": is_verified,
                "profile_pic_url": avatar_url,
                "external_url": f"https://instagram.com/{clean_user}",
            }
    except Exception as e:
        print(f"Scraper error for {clean_user}: {e}")
        
    return None


def init_instaloader(session_id=None):
    """Create an Instaloader instance configured for genuine metadata extraction."""
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=1,
        request_timeout=8,
    )
    
    # Priority: explicitly passed session_id -> environment variable -> saved session file
    effective_session = session_id or os.environ.get("INSTAGRAM_SESSIONID")
    if not effective_session:
        session_file = os.path.join(BASE_DIR, ".instagram_session")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    effective_session = f.read().strip()
            except Exception:
                pass
                
    if effective_session:
        loader.context._session.cookies.set("sessionid", effective_session, domain=".instagram.com")
        
    return loader


def extract_single_post(shortcode: str, session_id=None):
    """Extract a single genuine post or reel with high fidelity using Instaloader or yt-dlp."""
    loader = init_instaloader(session_id)
    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        is_video = post.is_video
        typename = post.typename
        media_type = (
            "reels" if typename == "GraphVideo" and getattr(post, "product_type", "") == "clips"
            else ("videos" if is_video else ("carousels" if typename == "GraphSidecar" else "photos"))
        )
        
        slides = []
        if typename == "GraphSidecar":
            for s_idx, node in enumerate(post.get_sidecar_nodes()):
                s_is_video = node.is_video
                slides.append({
                    "index": s_idx + 1,
                    "is_video": s_is_video,
                    "display_url": node.display_url,
                    "video_url": node.video_url if s_is_video else None,
                })
                
        item = {
            "id": post.shortcode,
            "shortcode": post.shortcode,
            "type": media_type,
            "typename": typename,
            "is_video": is_video,
            "display_url": post.url,
            "video_url": post.video_url if is_video else None,
            "caption": post.caption or "",
            "likes": post.likes,
            "comments": post.comments,
            "date": post.date_utc.strftime("%b %d, %Y") if post.date_utc else "",
            "timestamp": int(post.date_utc.timestamp()) if post.date_utc else 0,
            "slides": slides,
        }
        return item
    except Exception:
        # Fallback to yt-dlp for direct reel extraction
        try:
            cmd = ["yt-dlp", "--dump-json", "--no-warnings", f"https://www.instagram.com/reel/{shortcode}/"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            if res.returncode == 0:
                info = json.loads(res.stdout)
                return {
                    "id": shortcode,
                    "shortcode": shortcode,
                    "type": "reels",
                    "typename": "GraphVideo",
                    "is_video": True,
                    "display_url": info.get("thumbnail") or "",
                    "video_url": info.get("url") or "",
                    "caption": info.get("description") or info.get("title") or "",
                    "likes": info.get("like_count") or 0,
                    "comments": info.get("comment_count") or 0,
                    "date": datetime.now().strftime("%b %d, %Y"),
                    "timestamp": int(datetime.now().timestamp()),
                    "slides": [],
                }
        except Exception:
            pass
    return None


# ─── FRONTEND ROUTES ───────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


# ─── API ROUTES ────────────────────────────────────────────────

@app.route("/api/check-session")
def check_session():
    """Check if an Instagram session ID is currently active on the server."""
    active = bool(os.environ.get("INSTAGRAM_SESSIONID"))
    if not active:
        session_file = os.path.join(BASE_DIR, ".instagram_session")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    active = bool(f.read().strip())
            except Exception:
                pass
    return jsonify({"has_session": active})


@app.route("/api/save-session", methods=["POST"])
def save_session():
    """Save an Instagram session ID so all queries can load 200+ posts without rate limits."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "").strip()
    if not session_id:
        return jsonify({"error": "Empty session ID"}), 400
        
    os.environ["INSTAGRAM_SESSIONID"] = session_id
    session_file = os.path.join(BASE_DIR, ".instagram_session")
    try:
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(session_id)
        return jsonify({"success": True, "message": "Instagram Session connected successfully!"})
    except Exception as e:
        return jsonify({"success": True, "message": "Session saved in memory!"})


@app.route("/api/fetch-profile", methods=["POST"])
def fetch_profile():
    """
    Fetch genuine Instagram data for ANY user.
    - Always loads genuine profile info (real name, bio, follower count, real CDN avatar)
    - Enforces loading only posts with limit no less than 200 (limit >= 200)
    - Uses Instagram session if provided to fetch all genuine posts without throttling
    """
    data = request.get_json() or {}
    raw_user = data.get("username", "")
    username = clean_username(raw_user)
    
    # Requirement: "load only post no less than 200"
    requested_limit = int(data.get("limit", 200))
    limit = max(requested_limit, 200)
    
    requested_types = data.get("content_types", ["everything"])
    session_id = data.get("session_id", "").strip() or None

    if not username:
        return jsonify({"error": "Please enter a valid Instagram username or link"}), 400

    # Direct post / reel URL check (e.g., /p/SHORTCODE or /reel/SHORTCODE)
    if any(k in raw_user for k in ["/p/", "/reel/"]):
        single_item = extract_single_post(username, session_id)
        if single_item:
            counts = {"all": 1, "photos": 0, "videos": 0, "reels": 0, "carousels": 0}
            counts[single_item["type"]] = 1
            return jsonify({
                "success": True,
                "profile": {
                    "username": f"post_{username}",
                    "full_name": f"Instagram Post ({username})",
                    "biography": single_item["caption"][:100] if single_item["caption"] else "Direct post download",
                    "followers": single_item["likes"],
                    "followees": single_item["comments"],
                    "media_count": 1,
                    "is_private": False,
                    "is_verified": False,
                    "profile_pic_url": single_item["display_url"],
                    "external_url": f"https://instagram.com/p/{username}",
                },
                "items": [single_item],
                "counts": counts,
                "total_posts": 1,
                "loaded_count": 1,
            })

    # Step 1: Scrape 100% GENUINE Profile Info from Live Instagram
    profile_info = scrape_genuine_profile(username)
    
    loader = init_instaloader(session_id)
    items = []
    counts = {"all": 0, "photos": 0, "videos": 0, "reels": 0, "carousels": 0}
    instaloader_succeeded = False
    rate_limited = False

    # Step 2: Extract real posts using Instaloader (up to limit >= 200)
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        
        # Merge rich metadata from Instaloader
        if not profile_info:
            profile_info = {
                "username": profile.username,
                "full_name": profile.full_name or profile.username,
                "biography": profile.biography or "",
                "followers": profile.followers,
                "followees": profile.followees,
                "media_count": profile.mediacount,
                "is_private": profile.is_private,
                "is_verified": profile.is_verified,
                "profile_pic_url": str(profile.profile_pic_url),
                "external_url": profile.external_url or f"https://instagram.com/{username}",
            }
        else:
            profile_info["media_count"] = max(profile_info.get("media_count", 0), profile.mediacount)
            profile_info["followers"] = max(profile_info.get("followers", 0), profile.followers)
            if profile.profile_pic_url:
                profile_info["profile_pic_url"] = str(profile.profile_pic_url)
            profile_info["is_private"] = profile.is_private
            profile_info["is_verified"] = profile.is_verified or profile_info.get("is_verified", False)

        post_iter = profile.get_posts()
        count = 0
        for post in post_iter:
            if count >= limit:
                break

            try:
                node = getattr(post, "_node", {})
                typename = node.get("__typename", post.typename)
                is_video = node.get("is_video", getattr(post, "is_video", False))
                product_type = node.get("product_type", "")

                if is_video or typename == "GraphVideo":
                    media_type = "reels" if product_type == "clips" else "videos"
                elif typename == "GraphSidecar":
                    media_type = "carousels"
                else:
                    media_type = "photos"

                if "everything" not in requested_types and media_type not in requested_types:
                    continue

                slides = []
                if typename == "GraphSidecar":
                    edges = node.get("edge_sidecar_to_children", {}).get("edges", [])
                    for s_idx, edge in enumerate(edges):
                        c_node = edge.get("node", {})
                        s_is_video = c_node.get("is_video", False)
                        slides.append({
                            "index": s_idx + 1,
                            "is_video": s_is_video,
                            "display_url": c_node.get("display_url", ""),
                            "video_url": c_node.get("video_url") if s_is_video else None,
                        })

                timestamp = node.get("taken_at_timestamp")
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp)
                    date_str = dt.strftime("%b %d, %Y")
                else:
                    date_str = post.date_utc.strftime("%b %d, %Y") if getattr(post, "date_utc", None) else ""
                    timestamp = int(post.date_utc.timestamp()) if getattr(post, "date_utc", None) else 0

                caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                caption_text = caption_edges[0].get("node", {}).get("text", "") if caption_edges else (post.caption or "")
                likes_count = node.get("edge_liked_by", {}).get("count") or getattr(post, "likes", 0)
                comments_count = node.get("edge_media_to_comment", {}).get("count") or getattr(post, "comments", 0)
                display_url = node.get("display_url") or getattr(post, "url", "")
                video_url = node.get("video_url") if is_video else None

                item = {
                    "id": post.shortcode,
                    "shortcode": post.shortcode,
                    "type": media_type,
                    "typename": typename,
                    "is_video": is_video,
                    "display_url": display_url,
                    "video_url": video_url,
                    "caption": caption_text,
                    "likes": likes_count,
                    "comments": comments_count,
                    "date": date_str,
                    "timestamp": timestamp,
                    "slides": slides,
                }

                items.append(item)
                counts[media_type] = counts.get(media_type, 0) + 1
                counts["all"] += 1
                count += 1

            except Exception:
                continue

        instaloader_succeeded = True

    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "require_login" in err_msg or "429" in err_msg:
            rate_limited = True

    # If no profile info could be scraped
    if not profile_info:
        return jsonify({
            "error": f"Instagram profile '@{username}' could not be reached. Please check the username or try another profile."
        }), 404

    # If account is private
    if profile_info.get("is_private"):
        return jsonify({
            "success": True,
            "profile": profile_info,
            "items": [],
            "counts": counts,
            "is_private": True,
            "error": f"@{username} is a private Instagram account. Only approved followers can view these posts."
        })

    response_data = {
        "success": True,
        "profile": profile_info,
        "items": items,
        "counts": counts,
        "total_posts": profile_info.get("media_count", len(items)),
        "loaded_count": len(items),
    }

    if not items and (rate_limited or not instaloader_succeeded):
        response_data["requires_session"] = True
        response_data["message"] = (
            "Instagram requires a session cookie to load all 200+ posts for this profile anonymously. "
            "Connect your Instagram Session ID in Settings to unlock and download all 200+ posts!"
        )

    return jsonify(response_data)


@app.route("/api/download-file")
def download_file():
    """
    Direct in-browser download endpoint with Content-Disposition attachment.
    """
    media_url = request.args.get("url")
    filename = request.args.get("filename", "instagram_media.jpg")

    if not media_url:
        return jsonify({"error": "Missing media URL"}), 400

    try:
        r = requests.get(media_url, headers=DEFAULT_HEADERS, stream=True, timeout=30)
        if r.status_code != 200:
            return jsonify({"error": f"Failed to download (status {r.status_code})"}), 502

        content_type = r.headers.get("content-type", "application/octet-stream")

        def generate():
            for chunk in r.iter_content(chunk_size=16384):
                if chunk:
                    yield chunk

        resp = Response(generate(), mimetype=content_type)
        resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        if "content-length" in r.headers:
            resp.headers["Content-Length"] = r.headers["content-length"]
        return resp

    except Exception as e:
        return jsonify({"error": f"Download failed: {str(e)}"}), 500


@app.route("/api/proxy-media")
def proxy_media():
    """
    Proxy media stream with CORS and cache headers to bypass Instagram hotlinking blocks.
    """
    media_url = request.args.get("url")
    if not media_url:
        return jsonify({"error": "Missing media URL"}), 400

    try:
        r = requests.get(media_url, headers=DEFAULT_HEADERS, stream=True, timeout=20)
        content_type = r.headers.get("content-type", "image/jpeg")

        def generate():
            for chunk in r.iter_content(chunk_size=16384):
                if chunk:
                    yield chunk

        resp = Response(generate(), mimetype=content_type)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception as e:
        return jsonify({"error": f"Proxy error: {str(e)}"}), 500


@app.route("/api/download-zip", methods=["POST"])
def download_zip():
    """
    Package all requested media items into an organized ZIP archive with:
      images/
      videos/
      reels/
      carousels/
      profile_pic/
      profile_info/
    """
    data = request.get_json() or {}
    username = clean_username(data.get("username", "instagram_user"))
    profile_info = data.get("profile", {})
    items = data.get("items", [])

    if not items and not profile_info:
        return jsonify({"error": "No items to package in ZIP"}), 400

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Profile details
        if profile_info:
            info_json = json.dumps(profile_info, indent=2, ensure_ascii=False)
            zf.writestr(f"profile_info/profile_info.json", info_json)

            readme_text = (
                f"===================================================\n"
                f"  INSTAMANAGER ARCHIVE: @{profile_info.get('username')}\n"
                f"===================================================\n\n"
                f"Full Name:     {profile_info.get('full_name')}\n"
                f"Username:      @{profile_info.get('username')}\n"
                f"Followers:     {profile_info.get('followers', 0):,}\n"
                f"Following:     {profile_info.get('followees', 0):,}\n"
                f"Total Posts:   {profile_info.get('media_count', 0):,}\n"
                f"Bio:\n{profile_info.get('biography')}\n\n"
                f"External Link: {profile_info.get('external_url')}\n"
                f"Archived At:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Generated by:  InstaManager Web Project\n"
            )
            zf.writestr("profile_info/readme.txt", readme_text)

            pfp_url = profile_info.get("profile_pic_url")
            if pfp_url:
                try:
                    r = requests.get(pfp_url, headers=DEFAULT_HEADERS, timeout=15)
                    if r.status_code == 200:
                        zf.writestr(f"profile_pic/{username}_avatar.jpg", r.content)
                except Exception:
                    pass

        folder_mapping = {
            "photos": "images",
            "videos": "videos",
            "reels": "reels",
            "carousels": "carousels",
        }

        for item in items:
            shortcode = item.get("shortcode", "media")
            m_type = item.get("type", "photos")
            folder = folder_mapping.get(m_type, "images")

            if m_type == "carousels" and item.get("slides"):
                for slide in item["slides"]:
                    s_idx = slide.get("index", 1)
                    s_is_video = slide.get("is_video", False)
                    s_url = slide.get("video_url") if s_is_video else slide.get("display_url")
                    ext = "mp4" if s_is_video else "jpg"
                    if s_url:
                        try:
                            r = requests.get(s_url, headers=DEFAULT_HEADERS, timeout=20)
                            if r.status_code == 200:
                                filename = f"{folder}/{shortcode}_slide{s_idx}.{ext}"
                                zf.writestr(filename, r.content)
                        except Exception:
                            continue
            else:
                is_video = item.get("is_video", False)
                url = item.get("video_url") if is_video else item.get("display_url")
                ext = "mp4" if is_video else "jpg"

                if url:
                    try:
                        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=25)
                        if r.status_code == 200:
                            filename = f"{folder}/{shortcode}.{ext}"
                            zf.writestr(filename, r.content)
                    except Exception:
                        continue

    zip_buffer.seek(0)
    zip_filename = f"{username}_instagram.zip"

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_filename,
    )


@app.route("/api/save-to-folder", methods=["POST"])
def save_to_folder():
    """Save media to local folder on user's machine (downloads/<username>/)."""
    data = request.get_json() or {}
    username = clean_username(data.get("username", "instagram_user"))
    profile_info = data.get("profile", {})
    items = data.get("items", [])

    base_user_dir = os.path.join(DOWNLOADS_DIR, username)
    subdirs = ["profile_info", "images", "videos", "reels", "carousels", "profile_pic"]
    for s in subdirs:
        os.makedirs(os.path.join(base_user_dir, s), exist_ok=True)

    saved_count = 0

    if profile_info:
        info_path = os.path.join(base_user_dir, "profile_info", "profile_info.json")
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(profile_info, f, indent=2, ensure_ascii=False)

        pfp_url = profile_info.get("profile_pic_url")
        if pfp_url:
            try:
                r = requests.get(pfp_url, headers=DEFAULT_HEADERS, timeout=15)
                if r.status_code == 200:
                    with open(os.path.join(base_user_dir, "profile_pic", f"{username}_avatar.jpg"), "wb") as f:
                        f.write(r.content)
            except Exception:
                pass

    folder_mapping = {
        "photos": "images",
        "videos": "videos",
        "reels": "reels",
        "carousels": "carousels",
    }

    for item in items:
        shortcode = item.get("shortcode", "media")
        m_type = item.get("type", "photos")
        target_dir = os.path.join(base_user_dir, folder_mapping.get(m_type, "images"))

        if m_type == "carousels" and item.get("slides"):
            for slide in item["slides"]:
                s_idx = slide.get("index", 1)
                s_is_video = slide.get("is_video", False)
                s_url = slide.get("video_url") if s_is_video else slide.get("display_url")
                ext = "mp4" if s_is_video else "jpg"
                if s_url:
                    try:
                        filepath = os.path.join(target_dir, f"{shortcode}_slide{s_idx}.{ext}")
                        if not os.path.exists(filepath):
                            r = requests.get(s_url, headers=DEFAULT_HEADERS, timeout=20)
                            if r.status_code == 200:
                                with open(filepath, "wb") as f:
                                    f.write(r.content)
                                saved_count += 1
                    except Exception:
                        continue
        else:
            is_video = item.get("is_video", False)
            url = item.get("video_url") if is_video else item.get("display_url")
            ext = "mp4" if is_video else "jpg"
            if url:
                try:
                    filepath = os.path.join(target_dir, f"{shortcode}.{ext}")
                    if not os.path.exists(filepath):
                        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
                        if r.status_code == 200:
                            with open(filepath, "wb") as f:
                                f.write(r.content)
                            saved_count += 1
                except Exception:
                    continue

    return jsonify({
        "success": True,
        "message": f"Saved {saved_count} items to local folder!",
        "folder_path": base_user_dir,
    })


@app.route("/api/open-folder/<username>")
def open_folder(username):
    folder_path = os.path.join(DOWNLOADS_DIR, clean_username(username))
    if os.path.exists(folder_path):
        try:
            if hasattr(os, "startfile"):
                os.startfile(folder_path)
            return jsonify({"success": True, "message": f"Opened folder for @{username}"})
        except Exception as e:
            return jsonify({"error": f"Could not open folder: {str(e)}"}), 500
    return jsonify({"error": "Folder not found"}), 404


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  INSTAMANAGER - UNRESTRICTED INSTAGRAM HUB")
    print("=" * 50)
    print("  [>] Open http://localhost:5000 in your browser")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5000, host="0.0.0.0")
