import sqlite3

db = "/Users/wgfu/Desktop/novel-agent/portal/config.db"
conn = sqlite3.connect(db)
c = conn.cursor()

c.executescript("""
CREATE TABLE IF NOT EXISTS banned_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT UNIQUE NOT NULL,
    category TEXT DEFAULT '通用',
    replacement TEXT DEFAULT '',
    severity TEXT DEFAULT 'error',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS compliance_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key TEXT UNIQUE NOT NULL,
    rule_value TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alias_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    real_name TEXT UNIQUE NOT NULL,
    alias TEXT NOT NULL,
    category TEXT DEFAULT '地名',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS style_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    prompt TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Seed data
banned = [
    ("中国","国家","夏国","error"),("美国","国家","鹰国","error"),
    ("日本","国家","樱国","error"),("英国","国家","雾都联邦","error"),
    ("法国","国家","鸢尾联邦","error"),("德国","国家","铁十字联邦","error"),
    ("俄罗斯","国家","雪原联邦","error"),("韩国","国家","槿国","error"),
    ("北京","城市","上京","error"),("上海","城市","海州","error"),
    ("深圳","城市","鹏都","error"),("广州","城市","南陵","error"),
    ("成都","城市","锦都","error"),("重庆","城市","山城","error"),
    ("微信","产品","信聊","warn"),("支付宝","产品","金付","warn"),
    ("淘宝","产品","万货","warn"),("百度","产品","千寻","warn"),
    ("抖音","产品","律动","warn"),("微博","产品","言博","warn"),
]
for w in banned:
    c.execute("INSERT OR IGNORE INTO banned_words (word,category,replacement,severity) VALUES (?,?,?,?)", w)

rules = [
    ("world_name","蓝星","虚构世界名称","世界观"),
    ("naming_rule","所有地名、人名、组织名、产品名必须使用虚构名称","禁止使用真实世界名称","规则"),
    ("bypass_rule","不得使用谐音、缩写、拼音、外文原名绕过规则","杜绝擦边绕过","规则"),
    ("chapter_min_words","2500","章节最低字数要求","写作规范"),
]
for r in rules:
    c.execute("INSERT OR IGNORE INTO compliance_rules (rule_key,rule_value,description,category) VALUES (?,?,?,?)", r)

styles = [
    ("金庸风","传统武侠，典雅大气","以金庸风格写作：典雅大气的文风，注重人物性格刻画和意境描写，多用传统修辞手法，节奏张弛有度。"),
    ("古龙风","简洁凌厉，意境留白","以古龙风格写作：短句快节奏，对话为主体，大量留白和意境描写，人物神秘感强。"),
    ("番茄风","爽文直白，快节奏","以番茄风格写作：直白爽快的文风，快节奏推进剧情，注重升级体系和战斗描写。"),
    ("辰东风","宏大叙事，神话底蕴","以辰东风格写作：宏大的世界观设定，厚重的神话底蕴，伏笔深远，人物有血有肉。"),
    ("默认","项目基线风格","以流畅自然的中文写作，注重情节推进和人物塑造，文风平实有力。"),
]
for s in styles:
    c.execute("INSERT OR IGNORE INTO style_presets (name,description,prompt) VALUES (?,?,?)", s)

conn.commit()
conn.close()
print("OK: config.db created with seed data")
