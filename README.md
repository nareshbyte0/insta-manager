# 📸 InstaManager — Instagram Media Downloader & Vault

> A modern, full-featured web application to preview and download Instagram media in original HD quality. Download single photos, reels, videos, or carousels in one click, or package entire profiles into organized folders in a single ZIP.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)
![Vanilla_JS](https://img.shields.io/badge/Vanilla_JS-ES6+-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

---

## ✨ Features

- **🚀 Instant In-Browser Downloads**: Download files directly to your browser without long-running terminal queues or server-side lag.
- **📁 Structured Bulk ZIP Archives**: Package entire profile media into categorized subfolders:
  - `images/` — Full resolution photography
  - `reels/` — Vertical short-form videos (`.mp4`)
  - `videos/` — Full-length video posts (`.mp4`)
  - `carousels/` — Multi-slide carousel photo/video sets
  - `profile_pic/` — High-definition profile avatar
  - `profile_info/` — Metadata (`profile_info.json` & `readme.txt`)
- **🔍 Universal Search**: Enter any `@username` or paste profile / reel / post URLs directly.
- **🖼️ Rich Media Gallery**: Responsive card grid with live badges, like & comment counts, timestamps, and expandable captions.
- **🎬 Lightbox Video & Photo Modal**: Watch reels and preview photos directly within the app before downloading.
- **📑 Multi-Slide Carousel Support**: Interactive slide indicators to preview and download individual slides or full sets.
- **⚡ Unrestricted Access**: Resilient metadata extraction engine with fallback synthesis ensures every profile works smoothly.
- **💾 Local PC Export**: Option to save media directly into a local `downloads/<username>/` folder and open it in File Explorer.

---

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask, Instaloader, Requests
- **Frontend**: Modern Semantic HTML5, CSS3 (Glassmorphism, CSS Custom Properties, Ambient Glows), Vanilla JavaScript (ES6+)
- **Typography**: Plus Jakarta Sans & JetBrains Mono

---

## 🚀 Getting Started

### Prerequisites

Ensure you have **Python 3.9+** and **Git** installed on your system.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/nareshbyte0/insta-manager.git
   cd insta-manager
   ```

2. **Create a virtual environment (optional but recommended)**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Open in your browser**:
   Navigate to [http://localhost:5000](http://localhost:5000)

---

## 📂 Project Structure

```text
insta-manager/
├── app.py                  # Flask backend API & streaming proxy
├── requirements.txt        # Python package dependencies
├── .gitignore              # Files and directories ignored by Git
├── README.md               # Project documentation
└── static/
    ├── index.html          # Web application UI
    ├── style.css           # Modern dark-mode styling & design system
    └── app.js              # Client-side logic, gallery & download handlers
```

---

## 📝 Disclaimer

This tool is intended for personal and educational backup purposes only. It is not affiliated with, authorized, or endorsed by Instagram or Meta. Please respect copyright laws and content creators' rights when downloading media.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
