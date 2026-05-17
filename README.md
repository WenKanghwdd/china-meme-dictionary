# 🦞 China Meme Dictionary

**Understand trending Chinese internet slang — with translations in English, 日本語, 한국어, and Français.**

A self-updating, multilingual dictionary of Chinese internet memes, deployed on GitHub Pages.
New memes are automatically scraped every week from Chinese social media (Weibo, Baidu, Zhihu),
translated into four languages, and published — no manual work needed after setup.

---

## ✨ Features

- 🌐 **Multilingual** — Each meme has explanations in English, Japanese, Korean, and French
- 🔄 **Auto-updating** — GitHub Actions crawls trending Chinese hot lists every Monday
- 🔍 **Searchable** — Filter memes by Chinese name or pinyin in real-time
- 📱 **Responsive** — Works beautifully on desktop and mobile
- 🎨 **Chinese-inspired design** — Warm red, cream, and orange tones
- 🔥 **Trending + Classic** — Two sections: this week's hot memes and all-time classics
- 💰 **Zero cost** — Free APIs only, deploy on GitHub Pages for free

---

## 📁 Project Structure

```
china-meme-dictionary/
├── index.html                # Main website (single file)
├── data/
│   └── memes.json            # Meme data consumed by the website
├── scripts/
│   └── scrape_memes.py       # Weekly scraper and translator
├── .github/
│   └── workflows/
│       └── update-memes.yml  # GitHub Actions auto-update schedule
└── README.md                 # This file
```

---

## 🚀 How to Use Locally

### Option 1: Open directly

Just open `index.html` in your browser. The page will load data from `data/memes.json`.

Because of browser CORS policies, opening the file directly may prevent `fetch()` from loading the local JSON. If this happens, use Option 2.

### Option 2: Run a local server (recommended)

```bash
# Using Python 3
python3 -m http.server 8000

# Or using Node.js
npx serve .
```

Then open `http://localhost:8000` in your browser.

### Option 3: Run the scraper locally

```bash
cd china-meme-dictionary
pip install requests beautifulsoup4
python scripts/scrape_memes.py
```

This will fetch trending Chinese terms and update `data/memes.json`.

---

## 🌍 Deploy to GitHub Pages

Follow these steps even if you have never used GitHub before.

### Step 1: Create a GitHub repository

1. Go to [github.com/new](https://github.com/new)
2. Name your repository (e.g., `china-meme-dictionary`)
3. Choose **Public** (required for GitHub Pages free tier)
4. Click **Create repository**

### Step 2: Upload the files

**Method A — Using the web interface (easier for beginners):**

1. On your repository page, click **Add file** → **Upload files**
2. Drag and drop these files/folders:
   - `index.html`
   - `data/` folder (with `memes.json` inside)
   - `scripts/` folder (with `scrape_memes.py` inside)
   - `.github/` folder (with `workflows/update-memes.yml` inside)
   - `README.md`
3. Commit the changes (click **Commit changes**)

**Method B — Using Git command line:**

```bash
git clone https://github.com/YOUR_USERNAME/china-meme-dictionary.git
cd china-meme-dictionary
# Copy all project files here
git add .
git commit -m "Initial commit"
git push
```

### Step 3: Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** (top tab)
3. In the left sidebar, click **Pages**
4. Under **Branch**, select **main** (or master) and set folder to **/ (root)**
5. Click **Save**
6. Wait 1–2 minutes. Your site will be live at:
   `https://YOUR_USERNAME.github.io/china-meme-dictionary`

### Step 4: Enable GitHub Actions (for auto-updates)

1. Go to your repository on GitHub
2. Click **Settings** → **Actions** → **General**
3. Under **Workflow permissions**, select:
   - ✅ **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**
4. Click **Save**

### Step 5: Verify auto-updates

1. Go to your repository → **Actions** tab
2. You should see **Weekly Meme Update** listed as a workflow
3. To test it immediately, click **Run workflow** → **Run workflow** (green button)
4. Watch the workflow run — it will scrape memes, update `data/memes.json`, and commit the changes
5. After the workflow completes, refresh your GitHub Pages site to see new memes

---

## 🔄 How the Auto-Update Works

| Time (UTC) | Time (Beijing) | Event |
|------------|--------------|-------|
| Monday 00:00 | Monday 08:00 | GitHub Actions triggers |
| 00:00–00:03 | 08:00–08:03 | Python scraper fetches top terms from Weibo, Baidu, Zhihu hot lists |
| 00:03–00:04 | 08:03–08:04 | Filters out news headlines, keeps meme-like terms |
| 00:04–00:05 | 08:04–08:05 | Generates translations (EN/JA/KO/FR) |
| 00:05–00:06 | 08:05–08:06 | Merges with existing data, writes `data/memes.json` |
| 00:06–00:07 | 08:06–08:07 | Commits and pushes changes |
| — | — | GitHub Pages automatically redeploys |

You can also **manually trigger** an update anytime:
1. Go to your repository → **Actions** tab
2. Select **Weekly Meme Update** in the left sidebar
3. Click **Run workflow** → **Run workflow**

---

## 🧠 Data Format

Each meme entry in `data/memes.json` follows this structure:

```json
{
  "id": 1,
  "chinese": "内卷",
  "pinyin": "nèi juǎn",
  "explanations": {
    "en": "Involution — fierce, counterproductive competition...",
    "ja": "インボリューション — 過度な競争により...",
    "ko": "인볼루션 — 모두가 더 열심히 일하지만...",
    "fr": "Involution — compétition épuisante..."
  },
  "source": "weibo",
  "date": "2024-01-15",
  "is_trending": false
}
```

- `is_trending: true` → appears in the **🔥 Trending Now** section
- `is_trending: false` → appears in **📚 Classic Memes**

---

## 🛠 Technical Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Pure HTML + CSS + JavaScript (no frameworks) |
| Data format | JSON |
| Scraper | Python 3 + requests |
| Automation | GitHub Actions (cron) |
| Hosting | GitHub Pages (free) |
| Translation | Built-in rules + MyMemory API (free tier) |

---

## 📜 License

This project is open source. Feel free to fork, modify, and share.

---

## 🙏 Credits

- Hot list data sourced from [imsyy.top](https://api-hot.imsyy.top) (free public API)
- Translations powered by MyMemory API and built-in rules
- Inspired by the ever-evolving, wonderfully weird world of Chinese internet culture

---

*Made with 🦞 for everyone who loves Chinese internet culture.*
