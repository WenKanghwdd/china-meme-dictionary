#!/usr/bin/env python3
"""
China Meme Dictionary — Automatic Scraper & Translator

Fetches trending Chinese terms from multiple hot-search APIs,
generates multi-language explanations, and merges with existing data.
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlencode

try:
    import requests
except ImportError:
    print("ERROR: requests library not found. Run: pip install requests")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
DATA_FILE = os.path.join(REPO_ROOT, 'data', 'memes.json')

# ── User-Agent rotation ────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": USER_AGENTS[int(time.time()) % len(USER_AGENTS)],
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weibo.com/",
    }

# ── Source API endpoints ───────────────────────────────────
# Using free public hot-list aggregator APIs (no API key needed)
SOURCES = [
    {
        "name": "weibo",
        "url": "https://api-hot.imsyy.top/hot/weibo",
        "parser": "imsyy_generic",
    },
    {
        "name": "baidu",
        "url": "https://api-hot.imsyy.top/hot/baidu",
        "parser": "imsyy_generic",
    },
    {
        "name": "zhihu",
        "url": "https://api-hot.imsyy.top/hot/zhihu",
        "parser": "imsyy_generic",
    },
]

# ── Heuristics: filter out pure news headlines ─────────────
# If a term matches these patterns, it's probably news, not a meme
NEWS_KEYWORDS = [
    "死亡", "事故", "车祸", "地震", "台风", "洪水", "暴雨",
    "遇难", "受伤", "逮捕", "拘留", "审判", "判决", "起诉",
    "爆炸", "火灾", "塌方", "坠楼", "枪击", "刺杀",
    "新冠", "确诊", "新增", "阳性", "疫苗", "核酸",
    "总统", "首相", "外长", "外交部", "发言人",
    "声明", "抗议", "制裁", "战争", "冲突", "袭击",
    "财报", "涨跌", "股市", "期货", "黄金", "利率",
    "GDP", "CPI", "通胀",
]

def is_likely_meme(word):
    """Return True if the term looks like a meme/slang rather than a news event."""
    # Longer text is more likely to be a news headline
    if len(word) > 20:
        return False
    # Very short text (2-3 chars) could be meme shorthand
    # Check for news keywords
    for kw in NEWS_KEYWORDS:
        if kw in word:
            return False
    # Meme/slang often contains certain patterns
    meme_patterns = [
        r'了$',         # ends with 了 (破防了, emo了)
        r'子$',         # ends with 子 (绝绝子)
        r'人$',         # ends with 人 (社恐→社恐人)
        r'[A-Za-z]+$',  # contains English letters (YYDS, emo, 栓Q)
        r'的[^的]+$',   # 的xx pattern
    ]
    for pat in meme_patterns:
        if re.search(pat, word):
            return True
    # Fuzzy: short, vivid phrasing is meme-like
    if len(word) <= 8 and not any(kw in word for kw in ["中国", "美国", "日本", "俄罗斯", "报道", "发布", "宣布"]):
        return True
    return False

# ── Pinyin generation (simple fallback) ────────────────────
# NOTE: For proper pinyin, we'd use pypinyin; here we use a basic lookup.
# The github workflow can optionally install pypinyin for better results.
SIMPLE_PINYIN = {}

def simple_pinyin(text):
    """Generate basic pinyin using rules. Returns lowercase."""
    # Known pinyins for common slang characters
    known = {
        '内': 'nei', '卷': 'juan', '躺': 'tang', '平': 'ping',
        '芭': 'ba', '比': 'bi', 'Q': 'Q', '了': 'le',
        '社': 'she', '恐': 'kong', '绝': 'jue', '子': 'zi',
        '永': 'yong', '远': 'yuan', '的': 'de', '神': 'shen',
        '破': 'po', '防': 'fang', '凡': 'fan', '尔': 'er', '赛': 'sai',
        'e': 'yī', 'm': 'mó', 'o': 'ōu',
        '栓': 'shuan',
        '无': 'wu', '语': 'yu',
        '显': 'xian', '眼': 'yan', '包': 'bao',
        '遥': 'yao', '领': 'ling', '先': 'xian',
        '小': 'xiao', '土': 'tu', '豆': 'dou',
        '泼': 'po', '天': 'tian', '富': 'fu', '贵': 'gui',
        '太': 'tai', '酷': 'ku', '辣': 'la',
        '脆': 'cui', '皮': 'pi', '大': 'da', '学': 'xue', '生': 'sheng',
        '情': 'qing', '绪': 'xu', '价': 'jia', '值': 'zhi',
        '科': 'ke', '目': 'mu', '三': 'san',
    }
    result = []
    for ch in text:
        if ch in known:
            result.append(known[ch])
        elif re.match(r'[a-zA-Z]', ch):
            result.append(ch.lower())
        else:
            result.append(ch)
    return ' '.join(result)

# ── Translation engine ─────────────────────────────────────
# Built-in explanation templates for common patterns
EXPLANATION_TEMPLATES = {
    "en": (
        "Trending term on Chinese social media. {context} "
        "Often used in memes and casual online conversations among Chinese netizens."
    ),
    "ja": (
        "中国のSNSで流行中の用語。{context} "
        "中国のネットユーザーの間でミームやカジュアルな会話でよく使われます。"
    ),
    "ko": (
        "중국 SNS에서 유행하는 용어입니다. {context} "
        "중국 네티즌들 사이에서 밈과 일상 대화에 자주 사용됩니다."
    ),
    "fr": (
        "Terme tendance sur les réseaux sociaux chinois. {context} "
        "Souvent utilisé dans les mèmes et les conversations en ligne informelles."
    ),
}

# Specific generated context per term (fallback)
def build_context(text):
    """Build a differentiated English context sentence for any term."""
    # Check for common patterns
    if re.search(r'[A-Za-z]', text) and not re.search(r'[\u4e00-\u9fff]', text):
        return "It contains English letters and is often used as internet shorthand."
    if text.endswith('了'):
        stem = text[:-1]
        return f'Literally "{stem} happened", expressing a change of state or emotional reaction.'
    if text.endswith('子'):
        return 'The suffix "子" adds a cute or exaggerated tone typical of youth slang.'
    if text.endswith('人'):
        return f'Literally "{text} person", used to categorize a type of person in internet culture.'
    if len(text) <= 3:
        return f'A concise slang term expressing a complex modern emotion or social phenomenon.'
    if len(text) <= 6:
        return 'A vivid expression that captures a specific mood or situation in modern Chinese life.'
    return 'An emerging internet expression reflecting contemporary Chinese youth culture.'

def generate_explanations(text):
    """Generate multi-language explanations for a trending term."""
    ctx = build_context(text)
    exp = {}
    for lang, template in EXPLANATION_TEMPLATES.items():
        exp[lang] = template.format(context=ctx)
    return exp

# ── Try MyMemory API for better translations ───────────────
def try_mymemory_translate(text, source_lang='zh-CN', target_lang='en'):
    """Attempt to translate via MyMemory API free tier. Returns None on failure."""
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text,
            'langpair': f'{source_lang}|{target_lang}',
            'de': 'china-meme-dict@github',
        }
        resp = requests.get(url, params=params, timeout=8,
                            headers={'User-Agent': USER_AGENTS[0]})
        if resp.status_code == 200:
            data = resp.json()
            if data.get('responseStatus') == 200:
                translated = data.get('responseData', {}).get('translatedText', '')
                if translated and translated != text and translated.lower() != 'no match':
                    return translated
    except Exception as e:
        pass  # Fall through to built-in
    return None

def enhance_with_translation(text, explanations):
    """Try to improve explanations using free translation APIs."""
    # Try English translation via MyMemory
    en_trans = try_mymemory_translate(text, 'zh-CN', 'en')
    if en_trans and en_trans != text:
        # Replace generic explanation with the actual translation + context
        explanations['en'] = (
            f'"{en_trans}" — Literal translation of this trending Chinese term. '
            f'Originally from Chinese social media, it has become a widely used internet meme.'
        )
    # Try other languages (via English as pivot or direct)
    for lang in ['ja', 'ko', 'fr']:
        target_map = {'ja': 'ja', 'ko': 'ko', 'fr': 'fr'}
        # Try direct translation
        trans = try_mymemory_translate(text, 'zh-CN', target_map[lang])
        if trans and trans != text and 'NO MATCH' not in trans.upper():
            explanations[lang] = (
                f'"{trans}" — 中国のSNSで使われる流行語。'
                if lang == 'ja' else
                f'"{trans}" — 중국 SNS에서 사용되는 유행어.'
                if lang == 'ko' else
                f'"{trans}" — Terme tendance sur les réseaux sociaux chinois.'
            )

# ── API parsers ────────────────────────────────────────────
def parse_imsyy_generic(data, source_name):
    """Parse the free hot-list API response format."""
    results = []
    try:
        items = data.get('data', [])
        for item in items[:15]:  # Take top 15 from each source
            title = item.get('title', '') or item.get('word', '') or ''
            title = re.sub(r'#[^#]+#', '', title).strip()  # Remove hashtags
            title = re.sub(r'\[.*?\]', '', title).strip()
            if not title:
                continue
            hot = item.get('hot', 0) or item.get('count', 0) or 0
            results.append({'title': title, 'hot': hot})
    except Exception as e:
        print(f"  [WARN] Parse error for {source_name}: {e}")
    return results

def fetch_source(source):
    """Fetch one hot-list source and return extracted terms."""
    name = source['name']
    url = source['url']
    print(f"  Fetching {name}...")

    try:
        resp = requests.get(url, headers=get_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if source['parser'] == 'imsyy_generic':
            return parse_imsyy_generic(data, name)
        else:
            print(f"  [WARN] Unknown parser: {source['parser']}")
            return []
    except requests.exceptions.Timeout:
        print(f"  [WARN] {name} timed out.")
    except requests.exceptions.RequestException as e:
        print(f"  [WARN] {name} request failed: {e}")
    except json.JSONDecodeError:
        print(f"  [WARN] {name} returned invalid JSON.")
    except Exception as e:
        print(f"  [WARN] {name} error: {e}")
    return []

# ── Main logic ─────────────────────────────────────────────
def load_existing_data():
    """Load existing memes.json. Return (classics, trending, all_ids, existing_map)."""
    classics = []
    trending = []
    existing_map = {}  # chinese → meme object

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for meme in data:
                existing_map[meme['chinese']] = meme
                if meme.get('is_trending'):
                    trending.append(meme)
                else:
                    classics.append(meme)
            print(f"  Loaded existing data: {len(classics)} classics, {len(trending)} trending")
        except Exception as e:
            print(f"  [WARN] Failed to load existing data: {e}")
    else:
        print(f"  No existing data file found at {DATA_FILE}")

    return classics, trending, existing_map

def deduplicate_terms(terms, existing_map):
    """Remove terms that already exist in the database and filter out non-memes."""
    unique = []
    seen = set()
    for term in terms:
        chinese = term['chinese']
        if chinese in seen:
            continue
        seen.add(chinese)
        # Skip if already a classic meme
        if chinese in existing_map and not existing_map[chinese].get('is_trending'):
            print(f"  Skipping (already classic): {chinese}")
            continue
        # Filter news-like terms
        if not is_likely_meme(chinese):
            print(f"  Filtered out (news-like): {chinese}")
            continue
        unique.append(term)
    return unique

def assign_ids(new_terms, existing_ids):
    """Assign unique IDs to new terms."""
    max_id = max(existing_ids) if existing_ids else 0
    for term in new_terms:
        max_id += 1
        term['id'] = max_id
    return new_terms

def build_new_meme(chinese, source, date_str):
    """Build a complete meme object with auto-generated translations."""
    pinyin = simple_pinyin(chinese)
    exps = generate_explanations(chinese)
    # Try to enhance with real translations
    enhance_with_translation(chinese, exps)

    return {
        'chinese': chinese,
        'pinyin': pinyin,
        'explanations': exps,
        'source': source or 'web',
        'date': date_str,
        'is_trending': True,
    }

def main():
    print("=" * 50)
    print("China Meme Dictionary — Scraper v1.0")
    print(f"Date: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # 1. Load existing data
    classics, old_trending, existing_map = load_existing_data()
    existing_ids = set(m['id'] for m in classics + old_trending if 'id' in m)

    # 2. Scrape all sources
    all_raw = []
    for src in SOURCES:
        terms = fetch_source(src)
        print(f"    Got {len(terms)} terms from {src['name']}")
        all_raw.extend(terms)
        time.sleep(1.5)  # Rate limiting

    # 3. Extract unique chinese terms, sorted by popularity
    seen_titles = set()
    deduped_raw = []
    for t in all_raw:
        title = t['title'].strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            deduped_raw.append(t)

    # 4. Filter and deduplicate
    candidate_terms = [{'chinese': t['title'], 'hot': t['hot']} for t in deduped_raw]
    filtered = deduplicate_terms(candidate_terms, existing_map)

    # 5. Take top 10
    filtered = filtered[:10]

    # 6. Build full meme objects
    today = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d')
    new_trending = []
    for ft in filtered:
        # Check if it previously existed as trending (update explanations)
        if ft['chinese'] in existing_map and existing_map[ft['chinese']].get('is_trending'):
            existing = existing_map[ft['chinese']]
            existing['date'] = today
            new_trending.append(existing)
            print(f"  Updated trending: {ft['chinese']}")
        else:
            meme = build_new_meme(ft['chinese'], 'web', today)
            new_trending.append(meme)
            print(f"  New trending: {ft['chinese']}")

    # 7. Assign IDs to truly new entries
    new_trending = assign_ids(new_trending, existing_ids)

    # 8. Ensure all classics retain is_trending=false
    for c in classics:
        c['is_trending'] = False

    # 9. Merge
    output = classics + new_trending
    # Sort: classics by id, trending by id
    output.sort(key=lambda x: x.get('id', 9999))

    # 10. Write
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"Done! Written {len(output)} entries to {DATA_FILE}")
    print(f"  {len(classics)} classics + {len(new_trending)} trending")
    print(f"{'=' * 50}")

if __name__ == '__main__':
    main()
