#!/usr/bin/env python3
"""
China Meme Dictionary — Automatic Scraper & Translator

Fetches trending Chinese terms from multiple hot-search APIs,
generates multi-language explanations, and merges with existing data.
If scraping yields few results, falls back to a curated archive of
historical Chinese internet memes with original popularity dates.
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
# ── Historical Meme Archive (curated, with original popularity dates) ──
# Used as fallback when live scraping returns fewer than 5 meme-like terms.
# Each entry: (chinese, pinyin, en_explanation, ja_explanation, ko_explanation, fr_explanation, period_label, source)
# period_label e.g. "2020-03" (year-month the meme peaked)
HISTORICAL_MEMES = [
    # ── 2020 ──
    ("有内味了", "yǒu nèi wèi le",
     "'That's the vibe' — Used when something has that authentic, characteristic feel. Originated from gaming/ACG culture.",
     "「それっぽい」 — 本物らしい雰囲気を持つときに使う。ゲーム・ACG文化から。",
     "'그 맛이야' — 진짜 그 느낌이 난다는 뜻. 게임/ACG 문화에서 유래.",
     "'Ça a cette vibe' — Utilisé pour dire que quelque chose a ce feeling authentique. Issu de la culture gaming.",
     "2020-03", "weibo"),
    ("我太难了", "wǒ tài nán le",
     "'I'm too difficult/My life is so hard' — A popular lament expressing frustration with life's struggles. Often used humorously.",
     "「俺、難しすぎる」 — 人生の苦労を嘆く表現。よく冗談交じりに使われる。",
     "'나 너무 힘들어' — 인생의 고난에 대한 불평을 표현. 주로 유머러스하게 사용.",
     "'C'est trop dur' — Exprime la frustration face aux difficultés de la vie. Souvent utilisé avec humour.",
     "2020-04", "weibo"),
    ("黑人抬棺", "hēi rén tái guān",
     "'Black Men Carrying Coffins' — A viral meme featuring Ghanaian pallbearers dancing with a coffin. Used to signify 'game over' or epic failure.",
     "「黒人葬儀ダンス」 — ガーナの葬儀屋が棺桶を担いで踊る動画。大失敗・終了のミーム。",
     "'흑인 관 운반' — 가나의 장의사들이 관을 메고 춤추는 바이럴 영상. '게임 오버'를 상징.",
     "'Porteurs de cercueil noirs' — Méme viral de porteurs ghanéens dansant avec un cercueil. Signifie 'game over'.",
     "2020-04", "weibo"),
    ("一起爬山吗", "yì qǐ pá shān ma",
     "'Wanna go hiking?' — A sinister meme from the drama 'The Bad Kids'. Said by a murderer to his victims. Became a dark humor meme.",
     "「一緒に山登りしない？」 — ドラマ『隠秘的角落』から。殺人鬼の台詞で、ダークジョークとして。",
     "'같이 등산할래?' — 드라마 '은밀한 각도'에서 유래. 살인자의 대사로 암흑 유머로 사용.",
     "'On va faire de la randonnée ?' — Méme noir du drama 'The Bad Kids'. Phrase d'un meurtrier devenue virale.",
     "2020-06", "baidu"),
    ("爷青回", "yé qīng huí",
     "'My Youth Has Returned' — Abbreviation of 爷的青春回来了. Used when something nostalgic comes back, triggering childhood memories.",
     "「俺の青春が戻ってきた」 — 懐かしいものが復活した時の感動を表す略語。",
     "'내 청춘이 돌아왔다' — 향수를 불러일으키는 무언가가 돌아왔을 때의 감동을 표현.",
     "'Ma jeunesse est de retour' — Abréviation utilisée quand quelque chose de nostalgique fait son retour.",
     "2020-09", "weibo"),
    ("打工人", "dǎ gōng rén",
     "'Wage Worker' — A self-deprecating term for office workers/employees who are tired of the grind. Became a rallying cry for the working class.",
     "「労働者」 — サラリーマンや労働者が自己卑下する言葉。労働者階級の合言葉に。",
     "'월급쟁이' — 직장인의 자조적 표현. 노동자 계급의 구호가 됨.",
     "'Travailleur salarié' — Terme d'autodérision pour les employés, cri de ralliement de la classe ouvrière.",
     "2020-10", "weibo"),

    # ── 2021 ──
    ("蚌埠住了", "bèng bù zhù le",
     "'Can't Hold It' — A pun on '崩不住了' (can't hold it together), using the city name Bengbu. Means 'I can't stop laughing / I'm losing it'.",
     "「笑いが止まらない」 — 「崩不住了（我慢できない）」の駄洒落。笑いが止まらない時の表現。",
     "'참을 수 없어' — '崩不住了(참을 수 없다)'의 말장난. 웃음을 참을 수 없을 때 사용.",
     "'J'en peux plus' — Jeu de mots sur l'expression 'je craque'. Montre qu'on n'en peut plus de rire.",
     "2021-01", "weibo"),
    ("小丑竟是我自己", "xiǎo chǒu jìng shì wǒ zì jǐ",
     "'The Joker Is Me' — A self-mocking phrase used when you realize you've been the fool in a situation. Based on the Joker character.",
     "「ピエロは私だった」 — 自分が笑い者だったと気づいた時の自嘲的な言葉。ジョーカーから。",
     "'광대는 바로 나' — 자신이 바보였다는 걸 깨달았을 때의 자조적 표현. 조커 캐릭터에서 유래.",
     "'Le clown, c'est moi' — Phrase d'autodérision quand on réalise qu'on a été le dindon de la farce.",
     "2021-03", "weibo"),
    ("拿来吧你", "ná lái ba nǐ",
     "'Give It Here!' — A confident, grabby phrase used when you want something and you're taking it. Popularized by a short video creator.",
     "「よこせ！」 — 何かを手に入れたい時に使う強気な表現。ショート動画クリエイターから。",
     "'내놔!' — 무언가를 가져가고 싶을 때 쓰는 자신감 넘치는 표현. 숏폼 크리에이터에게서 유래.",
     "'Donne-moi ça !' — Phrase confiante pour réclamer quelque chose. Popularisée par un créateur de vidéos courtes.",
     "2021-06", "baidu"),
    ("YYDS", "yǒng yuǎn de shén",
     "'Eternal God / GOAT' — Abbreviation of 永远的神. Used to praise someone or something as the greatest of all time.",
     "「永遠の神」 — 「永遠的神」の略。最高を褒める言葉。",
     "'영원의 신' — '永遠的神'의 약자. 누군가를 최고라고 칭송할 때 사용.",
     "'Dieu éternel' — Acronyme de '永远的神'. Utilisé pour qualifier quelqu'un de légendaire.",
     "2021-07", "weibo"),
    ("绝绝子", "jué jué zǐ",
     "'Absolutely Amazing' — An exaggerated way to say something is incredible. Often used by young women on social media.",
     "「最高すぎる」 — 「絶句」の強調形。若い女性がSNSで感動を表現。",
     "'완전 대박' — '기가 막히다'를 강조. 젊은 여성들이 SNS에서 감탄할 때 사용.",
     "'Absolument incroyable' — Exagération pour dire que quelque chose est époustouflant.",
     "2021-08", "weibo"),

    # ── 2022 ──
    ("栓Q", "shuān Q",
     "'Thank You (funny version)' — Humorous mispronunciation of 'thank you'. Popularized by a viral video of a farmer speaking English.",
     "「サンキュー（笑）」 — 'thank you'の面白い発音。バイラル動画で流行。",
     "'감사합니다 (웃긴 버전)' — 'thank you'의 웃긴 발음. 바이럴 영상으로 유행.",
     "'Merci (version comique)' — Prononciation tordue de 'thank you' devenue virale.",
     "2022-03", "baidu"),
    ("刘畊宏", "liú gēng hóng",
     "'Liu Genghong' — A Taiwanese singer turned fitness influencer whose livestream workouts went viral during COVID lockdowns.",
     "「劉畊宏」 — 台湾出身の歌手兼フィットネスインフルエンサー。ロックダウン中に配信が話題に。",
     "'류겅홍' — 대만 출신 가수 겸 피트니스 인플루언서. 코로나 봉쇄 기간 실시간 운동 방송이 대유행.",
     "'Liu Genghong' — Chanteur taiwanais devenu influenceur fitness, ses lives sont devenus viraux pendant le confinement.",
     "2022-04", "weibo"),
    ("互联网嘴替", "hù lián wǎng zuǐ tì",
     "'Internet Mouth Substitute' — Someone who perfectly articulates what you're thinking online. 'They're my spokesperson on the internet.'",
     "「ネットの代弁者」 — 自分の考えを完璧に言葉にしてくれる人。ネット上の代弁者。",
     "'인터넷 대리 입' — 자신의 생각을 완벽히 대변해주는 사람. '인터넷 입替我'.",
     "'Porte-parole d'internet' — Personne qui exprime parfaitement ce que vous pensez en ligne.",
     "2022-06", "weibo"),
    ("退退退", "tuì tuì tuì",
     "'Back Off Back Off Back Off' — A meme of an angry woman yelling and doing a dance-like gesture to drive someone away. Became a symbol of 'delete this'.",
     "「下がれ下がれ下がれ」 — 怒った女性が追い払うように叫ぶミーム。拒絶の象徴に。",
     "'물러서 물러서 물러서' — 화난 여성이 쫓아내는 듯한 동작의 밈. 거절의 상징.",
     "'Dégage dégage dégage' — Méme d'une femme en colère chassant quelqu'un. Symbole de rejet.",
     "2022-06", "baidu"),
    ("大脑皮层光滑", "dà nǎo pí céng guāng huá",
     "'Smooth Brain' — Self-deprecating humor about being dumb or unable to understand something.",
     "「脳がツルツル」 — 自分の頭の悪さを自嘲するユーモア。",
     "'매끄러운 뇌' — 자신의 멍청함을 자조하는 유머.",
     "'Cerveau lisse' — Humour d'autodérision sur le fait d'être bête.",
     "2022-08", "weibo"),
    ("家人们", "jiā rén men",
     "'Family Members' — A way to address your online followers/friends. 'Hey family...' Creates a sense of intimacy and community.",
     "「ファミリー」 — フォロワーや友達への呼びかけ。親密感を演出。",
     "'가족들' — 온라인 팔로워/친구를 부르는 말. 친밀감을 조성.",
     "'Ma famille' — Façon de s'adresser à ses abonnés ou amis en ligne. Crée une intimité.",
     "2022-10", "weibo"),

    # ── 2023 ──
    ("泰酷辣", "tài kù là",
     "'Too Cool, Man' — A funny mispronunciation of '太酷了' made by a contestant on a Chinese variety show. Went viral for its awkward delivery.",
     "「超かっこいい」 — 中国バラエティ番組での珍発音が話題に。",
     "'너무 쿨하다' — 중국 예능 출연자의 재미있는 발음 실수로 유행.",
     "'Trop cool, mec' — Mauvaise prononciation devenue virale grâce à une émission chinoise.",
     "2023-03", "weibo"),
    ("挖呀挖呀挖", "wā ya wā ya wā",
     "'Dig Dig Dig' — A children's song that went viral on Douyin. Adults used it as a soothing, brain-clearing earworm.",
     "「ほ〜りほ〜り」 — 抖音でバイラルした子ども向けの歌。大人にも癒しとして人気。",
     "'파라파라파' — 틱톡에서 바이럴된 동요. 어른들에게도 힐링 송으로 인기.",
     "'Creuse creuse creuse' — Comptine devenue virale sur Douyin. Les adultes l'utilisent comme anti-stress.",
     "2023-05", "douyin"),
    ("i人e人", "i rén e rén",
     "'I-Person / E-Person' — Chinese internet shorthand for introvert/extrovert, borrowed from MBTI personality types. 'I人' = introvert, 'E人' = extrovert.",
     "「I人・E人」 — MBTIから来た内向的・外向的のネット略語。",
     "'I인 E인' — MBTI에서 유래한 내향적/외향적 성격을 나타내는 인터넷 약어.",
     "'I人 / E人' — Abréviations issues du MBTI. I = introverti, E = extraverti.",
     "2023-06", "weibo"),
    ("泼天富贵", "pō tiān fù guì",
     "'Overwhelming Fortune' — Literally 'splashing sky fortune'. Describes an unexpectedly huge windfall or viral success.",
     "「降って湧いた大金」 — 予想外の大金やバイラルヒットを指す。",
     "'엄청난 행운' — 예상치 못한 큰 돈이나 바이럴 성공을 표현.",
     "'Fortune débordante' — Décrit un coup de chance inattendu ou un succès viral.",
     "2023-09", "weibo"),
    ("遥遥领先", "yáo yáo lǐng xiān",
     "'Far Ahead / Leading the Pack' — Originally used by Huawei in product launches. Became a popular rallying cry for Chinese tech pride.",
     "「大きくリード」 — ファーウェイ製品発表での決め台詞。中国技術の誇りを表す。",
     "'압도적 선두' — 화웨이 제품 발표회 유행어. 중국 기술 자부심의 상징.",
     "'Largement en tête' — Slogan des lancements Huawei. Devenu cri de ralliement tech.",
     "2023-09", "weibo"),
    ("显眼包", "xiǎn yǎn bāo",
     "'Attention Seeker' — Literally 'conspicuous bag'. Describes someone who deliberately acts out to get attention, often cringily.",
     "「目立ちたがり」 — 注目を集めたがる人を指す。",
     "'관종' — 관심을 끌려고 과장된 행동을 하는 사람.",
     "'L'accrocheur' — Personne qui fait tout pour attirer l'attention.",
     "2023-10", "weibo"),
    ("遥遥领先", "yáo yáo lǐng xiān",
     "'Far Ahead / Leading the Pack' — Originally used by Huawei in product launches. Became a popular rallying cry for Chinese tech pride.",
     "「大きくリード」 — ファーウェイ製品発表での決め台詞。中国技術の誇りを表す。",
     "'압도적 선두' — 화웨이 제품 발표회 유행어. 중국 기술 자부심의 상징.",
     "'Largement en tête' — Slogan des lancements Huawei. Devenu cri de ralliement tech.",
     "2023-09", "weibo"),

    # ── 2024 ──
    ("科目三", "kē mù sān",
     "'Subject 3' — Originally a driving test subject. Became a viral dance trend on Douyin featuring specific body-wave moves.",
     "「教科書3」 — 運転免許の技能試験。抖音で特定の波打つダンスがバイラルに。",
     "'과목 3' — 운전면허 시험 과목. 더우인에서 웨이브 댄스가 바이럴.",
     "'Leçon 3' — Devenue une danse virale sur Douyin (TikTok chinois).",
     "2024-01", "douyin"),
    ("小土豆", "xiǎo tǔ dòu",
     "'Little Potato' — Affectionate term for southern Chinese tourists visiting Harbin in winter, who bundle up adorably.",
     "「小さなジャガイモ」 — 冬のハルビンに来る南方観光客の愛称。",
     "'작은 감자' — 겨울에 하얼빈을 방문하는 남부 관광객을 애정 담아 부르는 말.",
     "'Petite pomme de terre' — Terme affectueux pour les touristes du sud visitant Harbin.",
     "2024-01", "weibo"),
    ("脆皮大学生", "cuì pí dà xué shēng",
     "'Crispy College Students' — Gen Z university students who are physically fragile and get injured doing mundane things.",
     "「脆い大学生」 — 日常的なことで簡単にケガをするZ世代大学生。",
     "'바삭한 대학생' — 평범한 일에도 쉽게 다치는 Z세대 대학생을 놀리는 말.",
     "'Étudiants croustillants' — Étudiants de la génération Z qui se blessent en faisant des choses banales.",
     "2024-03", "weibo"),
    ("情绪价值", "qíng xù jià zhí",
     "'Emotional Value' — Buzzword for the emotional benefit someone brings to a relationship. High 'emotional value' = they make you feel good.",
     "「感情的価値」 — 人間関係で相手がもたらす感情的なメリット。",
     "'감정적 가치' — 인간관계에서 상대방이 주는 정서적 혜택.",
     "'Valeur émotionnelle' — Bénéfice émotionnel qu'une personne apporte dans une relation.",
     "2024-05", "baidu"),
]

# ── Historical meme lookup ─────────────────────────────────
HISTORICAL_MAP = {}
for h in HISTORICAL_MEMES:
    HISTORICAL_MAP[h[0]] = h


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
        return 'A concise slang term expressing a complex modern emotion or social phenomenon.'
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

    # 5. Take top 10 from live scrape
    live_trending = filtered[:10]

    # 6. Fallback: if live scraping produced < 5 memes, supplement with historical archive
    today = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d')
    MIN_MEMES = 5
    TARGET_COUNT = 8
    new_trending = []

    # 6a. Process live-scraped terms first
    for ft in live_trending:
        if ft['chinese'] in existing_map and existing_map[ft['chinese']].get('is_trending'):
            existing = existing_map[ft['chinese']]
            existing['date'] = today
            new_trending.append(existing)
            print(f"  Updated trending: {ft['chinese']}")
        else:
            meme = build_new_meme(ft['chinese'], 'web', today)
            new_trending.append(meme)
            print(f"  New trending: {ft['chinese']}")

    # 6b. Supplement with historical memes if needed
    if len(new_trending) < TARGET_COUNT:
        need = TARGET_COUNT - len(new_trending)
        print(f"\n  Only found {len(new_trending)} trending memes from live scraping.")
        print(f"  Supplementing with {need} historical memes from archive...")

        # Collect historical memes not already in the dataset
        historical_candidates = []
        for h in HISTORICAL_MEMES:
            chinese = h[0]
            if chinese not in existing_map and chinese not in {m['chinese'] for m in new_trending}:
                historical_candidates.append(h)

        # Remove entries where chinese is already in the final list to avoid duplicates
        added = 0
        for h in historical_candidates:
            if added >= need:
                break
            chinese, pinyin, en, ja, ko, fr, period_label, source = h
            meme = {
                'chinese': chinese,
                'pinyin': pinyin,
                'explanations': {'en': en, 'ja': ja, 'ko': ko, 'fr': fr},
                'source': source,
                'date': period_label,  # Use historical period as date (e.g., "2021-06")
                'is_trending': True,
                '_historical': True,  # Internal flag
            }
            new_trending.append(meme)
            print(f"  + Historical ({period_label}): {chinese}")
            added += 1

    # 7. Assign IDs to entries without one
    new_trending = assign_ids(new_trending, existing_ids)

    # 8. Ensure all classics retain is_trending=false, remove internal flag
    for c in classics:
        c['is_trending'] = False
        c.pop('_historical', None)

    for nt in new_trending:
        nt.pop('_historical', None)

    # 9. Merge
    output = classics + new_trending
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
