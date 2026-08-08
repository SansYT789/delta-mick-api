BOT_OWNER_ID = {985004175110848512}

MAX_LOG_ENTRIES = 10
LIXI_DURATION_MIN = 10

# Meme Achievement
MEME_CONFIG = {
    "channel_id": 1528562696398831616,  # Kênh meme
    "role_id": 1529765560433381427,  # Role thưởng
    "required_count": 20,  # Số meme cần đạt
    "cooldown_minutes": 2,  # Thời gian giữa các lần kiểm tra (phút)
}

WORK_COOLDOWN_HOURS = 24
STREAK_BONUS_PER_WEEK = 0.02   # +2%/tuần

WORK_TZ_OFFSET_HOURS = 7  # UTC+7 VN
WORK_START_HOUR = 7       # 7h sáng = mốc "đúng giờ"
WORK_LATE_CUTOFF_HOUR = 12  # sau 12h trưa: không work đc hôm đó
WORK_LATE_PENALTY_PER_MINUTE = 0.01  # -1%/phút trễ
WORK_LATE_PENALTY_MAX = 0.5          # tối đa -50%

WORK_COMPANY_SWITCH_COOLDOWN_DAYS = 7
WORK_PREMIUM_COMPANIES = {"storm", "quantum", "mango_global", "elite_group"}
WORK_PREMIUM_ENTRY_FEE_MULTIPLIER = 10  # phí = 10x lương trung bình công ty đó

WORK_RESIGN_FEE = 500
WORK_RESIGN_COOLDOWN_DAYS = 1

WORK_PRESIDENT_NICKNAME_PREFIX = "[Chủ tịch] "

COMPANIES = {
    "delta": {
        "name": "Tập đoàn Delta",
        "base_pay": (80, 140),
    },
    "mango_mustard": {
        "name": "Tập đoàn Mango Mustard",
        "base_pay": (60, 110),
    },
    "beast": {
        "name": "Công ty thành phẩm Beast",
        "base_pay": (70, 120),
    },
    "olivier": {
        "name": "Công ty thực vật Ô liu",
        "base_pay": (50, 90),
    },
    "phonk": {
        "name": "Tập đoàn Phonk",
        "base_pay": (90, 150),
    },
    "one_more_game": {
        "name": "Công ty One More Game",
        "base_pay": (65, 130),
    },
    "nova": {
        "name": "Tập đoàn Nova Technology",
        "base_pay": (120, 200),
    },
    "cyber_core": {
        "name": "Công ty Cyber Core",
        "base_pay": (150, 260),
    },
    "golden_leaf": {
        "name": "Tập đoàn Golden Leaf",
        "base_pay": (100, 180),
    },
    "storm": {
        "name": "Tập đoàn Storm Industries",
        "base_pay": (180, 320),
    },
    "quantum": {
        "name": "Công ty Quantum Labs",
        "base_pay": (250, 450),
    },
    "mango_global": {
        "name": "Mango Global Corporation",
        "base_pay": (350, 600),
    },
    "elite_group": {
        "name": "Tập đoàn Elite Group",
        "base_pay": (500, 900),
    },
}

MAX_POSITION_LEVEL = 9         # 0..9: lao công -> ... -> chủ tịch
POSITION_NAMES = [
    "Thực tập sinh",
    "Nhân viên",
    "Nhân viên cấp cao",
    "Trưởng nhóm",
    "Trưởng phòng",
    "Quản lý",
    "Giám đốc",
    "Phó tổng giám đốc",
    "Tổng giám đốc",
    "Chủ tịch",
]
POSITION_BUFFS = [
    0.00, # Lao công
    0.08, # Nhân viên
    0.15, # Nhân viên cấp cao
    0.25, # Trưởng nhóm
    0.35, # Trưởng phòng
    0.50, # Quản lý
    0.70, # Giám đốc
    1.00, # Phó tổng
    1.40, # Tổng giám đốc
    2.00, # Chủ tịch
]

# sự kiện xui: (tên, mô tả, cooldown phạt giờ)
BAD_EVENTS = [
    {
        "key": "crisis_911",
        "text": "💥 Sự kiện bất khả kháng xảy ra tại công ty — toàn bộ nhân viên phải sơ tán khẩn cấp.",
        "penalty_hours": 72,
        "chance": 0.006,
    },
    {
        "key": "boss_bankrupt",
        "text": "📉 Sếp vỡ nợ và bỏ trốn — công ty tạm ngừng hoạt động, bạn cần tìm việc khác.",
        "penalty_hours": 48,
        "chance": 0.011,
    },
    {
        "key": "company_layoff",
        "text": "✂️ Công ty cắt giảm nhân sự lớn — bạn bị tạm cho nghỉ để tái cơ cấu.",
        "penalty_hours": 36,
        "chance": 0.017,
    },
    {
        "key": "server_crash",
        "text": "🖥️ Hệ thống công ty bị sập nghiêm trọng — toàn bộ công việc bị đình trệ.",
        "penalty_hours": 24,
        "chance": 0.021,
    },
    {
        "key": "legal_problem",
        "text": "⚖️ Công ty gặp vấn đề pháp lý — hoạt động bị điều tra và tạm dừng.",
        "penalty_hours": 60,
        "chance": 0.009,
    },
    {
        "key": "strike",
        "text": "📢 Nhân viên đình công — công ty đóng cửa tạm thời để giải quyết tranh chấp.",
        "penalty_hours": 30,
        "chance": 0.015,
    },
    {
        "key": "market_crash",
        "text": "📉 Thị trường lao dốc — công ty giảm tốc độ hoạt động và đóng băng dự án.",
        "penalty_hours": 40,
        "chance": 0.013,
    },
    {
        "key": "data_breach",
        "text": "🔓 Công ty bị rò rỉ dữ liệu — mọi hoạt động bị kiểm tra bảo mật.",
        "penalty_hours": 18,
        "chance": 0.026,
    },
    {
        "key": "equipment_failure",
        "text": "🔧 Thiết bị quan trọng bị hỏng — bạn không thể tiếp tục công việc bình thường.",
        "penalty_hours": 12,
        "chance": 0.032,
    },
    {
        "key": "bad_manager",
        "text": "😡 Quản lý mới quá khắt khe — hiệu suất làm việc giảm mạnh.",
        "penalty_hours": 20,
        "chance": 0.021,
    },
]

# sự kiện tốt: thưởng thêm khi /work
GOOD_EVENTS = [
    {
        "key": "bonus_payday",
        "text": "🎉 Công ty thưởng nóng nhân dịp doanh thu tốt!",
        "type": "bonus_pay",
        "value": 0.5,  # +50% lương lần này
        "chance": 0.04,
    },
    {
        "key": "big_bonus_payday",
        "text": "💎 Bạn vừa chốt được một hợp đồng lớn, được thưởng cực đậm!",
        "type": "bonus_pay",
        "value": 1.2,  # +120% lương lần này
        "chance": 0.015,
    },
    {
        "key": "cooldown_reduction",
        "text": "⏱️ Sếp cho bạn nghỉ sớm hôm nay — lần làm việc tiếp theo đến sớm hơn!",
        "type": "cooldown_reduction",
        "value": 0.5,  # giảm 50% cooldown lần tới
        "chance": 0.04,
    },
    {
        "key": "streak_boost",
        "text": "🔥 Bạn làm việc xuất sắc, được cộng thêm uy tín chuỗi làm việc!",
        "type": "streak_boost",
        "value": 2,  # +2 tuần streak
        "chance": 0.03,
    },
    {
        "key": "early_promotion",
        "text": "📈 Cấp trên ấn tượng với bạn và quyết định thăng chức sớm!",
        "type": "promotion",
        "value": 1,  # +1 cấp vị trí
        "chance": 0.02,
    },
    {
        "key": "mega_bonus",
        "text": "🏆 Bạn được vinh danh Nhân viên xuất sắc nhất tháng — thưởng khủng!",
        "type": "bonus_pay",
        "value": 2.0,  # +200% lương lần này
        "chance": 0.008,
    },
]

_FORTUNES = [
    {"title": "🏆 Triệu phú tương lai", "desc": "Vận số giàu sang đang chờ, chỉ cần đừng nghỉ việc giữa chừng.", "weight": 3},
    {"title": "🃏 Bậc thầy scam vặt", "desc": "Chuyên gia hứa suông trong nhóm chat, nhưng tim thì lương thiện.", "weight": 8},
    {"title": "👻 Người vô hình", "desc": "Nhắn tin không ai rep, gọi không ai nghe — nhưng vẫn được yêu quý âm thầm.", "weight": 10},
    {"title": "🎭 Diễn viên ẩn danh", "desc": "Ngoài đời trầm tính, trong Discord là drama queen chính hiệu.", "weight": 9},
    {"title": "🐢 Chậm mà chắc", "desc": "Làm gì cũng trễ deadline nhưng chưa bao giờ thất bại hoàn toàn.", "weight": 12},
    {"title": "🔥 Ngọn lửa cô đơn", "desc": "Cháy hết mình vì đam mê, nhưng hay bị auto AFK giữa trận.", "weight": 9},
    {"title": "🎰 Con nghiện may rủi", "desc": "Gacha game nào cũng chơi, tỉ lệ ra rare thấp không cản được đam mê.", "weight": 8},
    {"title": "🧙 Pháp sư mù mờ", "desc": "Nói chuyện sâu sắc nhưng thật ra đang đoán mò 90% thời gian.", "weight": 10},
    {"title": "👑 Vua/Nữ hoàng không ngai", "desc": "Sinh ra để lãnh đạo, nhưng cái nhóm chat lại không cho quyền admin.", "weight": 5},
    {"title": "🍜 Đại sư mì gói", "desc": "Nấu ăn cả đời chỉ giỏi món này, nhưng làm cực ngon.", "weight": 11},
    {"title": "📉 Nhà đầu tư gãy tay", "desc": "Mua đỉnh bán đáy là chuyên môn, nhưng tinh thần luôn lạc quan.", "weight": 7},
    {"title": "🌙 Cú đêm chính hiệu", "desc": "3 giờ sáng vẫn online, ban ngày ngủ bù không kịp thở.", "weight": 10},
    {"title": "🎯 Xạ thủ một phát trúng", "desc": "Ít nói nhưng câu nào ra câu đó, chốt hạ cực gọn.", "weight": 6},
    {"title": "🐌 Tổ trưởng trì hoãn", "desc": "Việc hôm nay để mai làm, nhưng mai làm thì lại xuất sắc.", "weight": 10},
    {"title": "🎪 Chú hề của nhóm", "desc": "Luôn là người pha trò đầu tiên, nhưng cũng là người an ủi cuối cùng.", "weight": 9},
    {"title": "🧊 Băng giá bên ngoài", "desc": "Nhìn lạnh lùng khó gần, thân rồi mới biết ấm áp cỡ nào.", "weight": 8},
    {"title": "🎲 Người được thần may mắn ưu ái", "desc": "Mở loot box nào cũng trúng, đời thực thì chưa chắc.", "weight": 4},
    {"title": "🌟 Ngôi sao ẩn danh", "desc": "Tài năng thực sự chưa ai phát hiện — hoặc phát hiện rồi mà chưa dám nói.", "weight": 6},
]

WORDLE_MAX_GUESSES = 5
WORDLE_DAILY_LIMIT = 6
WORDLE_WIN_REWARD = 20

WORDLE_WIN_STREAK_REQUIRED = 5
WORDLE_TOTAL_WINS_REQUIRED = 12

WORDLE_WORDS = [
    "APPLE", "BRAVE", "CHESS", "DANCE", "EAGLE", "FLAME", "GRAPE", "HOUSE", "IMAGE", "JOKER",
    "KNIFE", "LEMON", "MONEY", "NIGHT", "OCEAN", "PIANO", "QUIET", "RIVER", "STONE", "TIGER",
    "UNITY", "VOICE", "WATER", "YOUTH", "ZEBRA", "ANGLE", "BLOOM", "CANDY", "DREAM", "EARTH",
    "FRUIT", "GHOST", "HAPPY", "IVORY", "JELLY", "KARMA", "LIGHT", "MUSIC", "NURSE", "OLIVE",
    "PEACE", "QUEEN", "ROBOT", "SMILE", "TABLE", "URBAN", "VIRUS", "WORLD", "YIELD", "BROOM",
    "CLOUD", "DIARY", "EMPTY", "FRESH", "GLASS", "HONEY", "INBOX", "JUDGE", "LASER", "MAGIC",
    "NOBLE", "ORBIT", "PAPER", "QUICK", "ROUND", "SUGAR", "TEACH", "UNCLE", "VAGUE", "WITCH",
    "BEACH", "CRAFT", "DELTA", "ELBOW", "FIELD", "GRAND", "HOTEL", "INPUT", "JOINT", "LUNAR",
    "MANGO", "NOVEL", "OPERA", "PLANT", "QUOTE", "RADIO", "SNAKE", "TREND", "UNITE", "VALID",
    "RATIO", "PHONK", "ABOVE", "ADULT", "AFTER", "AGAIN", "ALBUM", "ALERT", "ALIEN", "ALIKE",
    "ALONE", "AMBER", "ANGEL", "ANGRY", "AWARD", "AWAKE", "BAKER", "BASIC", "BEAST", "BEGAN",
    "BEGIN", "BERRY", "BLACK", "BLADE", "BLAST", "BLIND", "BLOCK", "BOOST", "BRAIN", "BREAD",
    "BRICK", "BRING", "BROWN", "BRUSH", "CABLE", "CAMEL", "CANON", "CARRY", "CHAIN", "CHAIR",
    "CHAOS", "CHARM", "CHASE", "CHEAP", "CHEAT", "CHECK", "CHEEK", "CHEER", "CHILI", "CHOIR",
    "CLEAN", "CLERK", "CLICK", "CLIMB", "CLOCK", "CLOSE", "COAST", "COLOR", "COMIC", "CORAL",
    "COUNT", "COURT", "COVER", "CRANE", "CRASH", "CRAZY", "CREAM", "CREST", "CROSS", "CROWN",
    "CURVE", "DAILY", "DAISY", "DEMON", "DEPTH", "DIGIT", "DIRTY", "DOUBT", "DOZEN", "DRAMA",
    "DRINK", "DRIVE", "DROVE", "EARLY", "ELITE", "ENEMY", "ENJOY", "ENTER", "ERROR", "EVENT",
    "FAITH", "FAIRY", "FALSE", "FANCY", "FAULT", "FIBER", "FINAL", "FIRST", "FLASH", "FLOOD",
    "FLOOR", "FOCUS", "FORCE", "FORTH", "FRAME", "FROST", "GAMER", "GIANT", "GLORY", "GLOWY",
    "GOOSE", "GRADE", "GREEN", "GROUP", "GUARD", "GUIDE", "HEART", "HELLO", "HOMER", "HORSE",
    "HUMAN", "HUMOR", "IDEAL", "INDEX", "ISSUE", "JUICE", "JUMBO", "LAYER", "LOWER", "LUCKY",
    "LUNCH", "MAPLE", "MEDAL", "METAL", "MODEL", "MOUSE", "OASIS", "OFFER", "ORDER", "PASTA",
    "PEACH", "PHONE", "PICKY", "PILOT", "PIXEL", "POWER", "PRIZE", "RANCH", "RAPID", "REACH",
    "RIGHT", "SCARY", "SHARE", "SHARK", "SHINE", "SHIRT", "SHORT", "SIEGE", "SIGMA", "SINCE",
    "SKILL", "SLEEP", "SMART", "SOLAR", "SOLID", "SOUND", "SPACE", "SPARK", "SPEED", "SPIKE",
    "SPORT", "STAFF", "STAGE", "START", "STEEL", "STORM", "STRAW", "STYLE", "SUPER", "SWEET",
    "SWING", "THEME", "THIEF", "THINK", "THROW", "TOAST", "TOKEN", "TOWER", "TOWEL", "TOUCH",
    "TRAIN", "TRUCK", "TRUST", "TRUTH", "VALUE", "VIDEO", "VISIT", "WAGON", "WHALE", "WHEEL",
    "WHITE", "WHOLE", "WOMAN", "WOODS", "WORTH", "WRITE", "WRONG", "YOUNG", "ANGER",
    "STRAY", "SPRAY", "CRONE", "GRASS", "ETHAN", "HOPES", "RATER"
]

FLAG_QUESTIONS_PER_GAME = 5
FLAG_ATTEMPTS_PER_QUESTION = 3
FLAG_SECONDS_PER_QUESTION = 15
FLAG_DAILY_LIMIT = 5

FLAG_STREAK_ROLE_ID = 1531495631259045968
FLAG_STREAK_REQUIRED = 15          # tổng số CÂU đúng cần đạt
FLAG_STREAK_WINDOW_GAMES = 3       # trong tối đa 3 ván liên tiếp
FLAG_STREAK_MIN_MODE_ORDER = 2     # chỉ tính khi mode >= "medium"

FLAG_MODE_ORDER = ["easy", "normal", "medium", "hard", "insane"]

FLAG_COUNTRIES = {
    "easy": [
        ("Việt Nam", "vn", ["viet nam", "vietnam"]),
        ("Mỹ", "us", ["my", "hoa ky", "usa", "united states"]),
        ("Nhật Bản", "jp", ["nhat ban", "nhat", "japan", "nhật"]),
        ("Hàn Quốc", "kr", ["han quoc", "han", "korea", "south korea", "hàn"]),
        ("Trung Quốc", "cn", ["trung quoc", "china"]),
        ("Anh", "gb", ["anh", "uk", "united kingdom", "england"]),
        ("Pháp", "fr", ["phap", "france"]),
        ("Đức", "de", ["duc", "germany"]),
        ("Thái Lan", "th", ["thai lan", "thailand", "thai", "thái"]),
        ("Canada", "ca", ["canada"]),
        ("Úc", "au", ["uc", "australia"]),
        ("Ấn Độ", "in", ["an do", "india", "an", "ấn"]),
        ("Nga", "ru", ["nga", "russia"]),
        ("Ý", "it", ["y", "italy", "italia"]),
        ("Tây Ban Nha", "es", ["tay ban nha", "spain"]),
        ("Brazil", "br", ["brazil", "brasil"]),
        ("Mexico", "mx", ["mexico"]),
        ("Indonesia", "id", ["indonesia"]),
        ("Singapore", "sg", ["singapore"]),
        ("Malaysia", "my", ["malaysia", "ma lay", "mã lay"]),
        ("Bỉ", "be", ["bi", "belgium"]),
        ("Đan Mạch", "dk", ["dan mach", "denmark"]),
        ("Áo", "at", ["ao", "austria"]),
        ("Hungary", "hu", ["hungary"]),
        ("Cộng hòa Séc", "cz", ["cong hoa sec", "czech", "czechia", "sec", "séc"]),
        ("Peru", "pe", ["peru"]),
        ("Venezuela", "ve", ["venezuela"]),
        ("Pakistan", "pk", ["pakistan"]),
        ("Ai Cập", "eg", ["ai cap", "egypt"]),
        ("Argentina", "ar", ["argentina"]),
        ("Israel", "il", ["israel"]),
        ("Ả Rập Xê Út", "sa", ["saudi", "saudi arabia", "a rap", "a rap xe ut"]),
        ("UAE", "ae", ["uae", "united arab emirates", "các tiểu vương quốc", "uae"]),
    ],
    "normal": [
        ("Thụy Điển", "se", ["thuy dien", "sweden"]),
        ("Na Uy", "no", ["na uy", "norway"]),
        ("Hà Lan", "nl", ["ha lan", "netherlands", "holland"]),
        ("Bồ Đào Nha", "pt", ["bo dao nha", "portugal"]),
        ("Ba Lan", "pl", ["ba lan", "poland"]),
        ("Thổ Nhĩ Kỳ", "tr", ["tho nhi ky", "turkey"]),
        ("Philippines", "ph", ["philippines", "philippine", "phi lip pin", "phi líp pin", "phi-lip-pin", "phi-líp-pin", "phi lip pines"]),
        ("New Zealand", "nz", ["new zealand"]),
        ("Thụy Sĩ", "ch", ["thuy si", "switzerland"]),
        ("Ireland", "ie", ["ireland"]),
        ("Romania", "ro", ["romania"]),
        ("Bulgaria", "bg", ["bulgaria"]),
        ("Serbia", "rs", ["serbia"]),
        ("Slovakia", "sk", ["slovakia"]),
        ("Cuba", "cu", ["cuba"]),
        ("Ecuador", "ec", ["ecuador"]),
        ("Guatemala", "gt", ["guatemala"]),
        ("Miến Điện", "mm", ["myanmar", "burma", "mien dien"]),
        ("Campuchia", "kh", ["campuchia", "cambodia", "chich dien", "kampuchea"]),
        ("Lào", "la", ["lao", "laos"]),
        ("Mông Cổ", "mn", ["mong co", "mongolia"]),
        ("Iran", "ir", ["iran", "ba tư"]),
        ("Iraq", "iq", ["iraq"]),
        ("Syria", "sy", ["syria"]),
        ("Nepal", "np", ["nepal"]),
        ("Bangladesh", "bd", ["bangladesh"]),
        ("Sri Lanka", "lk", ["sri lanka", "tích lan"]),
        ("Phần Lan", "fi", ["phan lan", "finland"]),
        ("Hy Lạp", "gr", ["hy lap", "greece"]),
        ("Ukraine", "ua", ["ukraine", "u rai na", "u-rai-na", "u crai na", "u-crai-na", "ucraina"]),
        ("Chile", "cl", ["chile"]),
        ("Colombia", "co", ["colombia"]),
        ("Kenya", "ke", ["kenya"]),
    ],
    "medium": [
        ("Maroc", "ma", ["maroc", "morocco"]),
        ("Iceland", "is", ["iceland"]),
        ("Croatia", "hr", ["croatia"]),
        ("Albania", "al", ["albania"]),
        ("Armenia", "am", ["armenia"]),
        ("Azerbaijan", "az", ["azerbaijan"]),
        ("Belarus", "by", ["belarus"]),
        ("Bosnia và Herzegovina", "ba", ["bosnia", "bosnia herzegovina", "bosnia and herzegovina", "bosnia va herzegovina"]),
        ("Estonia", "ee", ["estonia"]),
        ("Latvia", "lv", ["latvia"]),
        ("Lithuania", "lt", ["lithuania"]),
        ("Slovenia", "si", ["slovenia"]),
        ("Georgia", "ge", ["georgia"]),
        ("Kazakhstan", "kz", ["kazakhstan"]),
        ("Uzbekistan", "uz", ["uzbekistan"]),
        ("Qatar", "qa", ["qatar"]),
        ("Kuwait", "kw", ["kuwait"]),
        ("Oman", "om", ["oman"]),
        ("Jordan", "jo", ["jordan"]),
        ("Lebanon", "lb", ["lebanon"]),
        ("Tunisia", "tn", ["tunisia"]),
        ("Algeria", "dz", ["algeria"]),
        ("Nam Phi", "za", ["nam phi", "south africa"]),
        ("Nigeria", "ng", ["nigeria"]),
        ("Ghana", "gh", ["ghana"]),
        ("Uganda", "ug", ["uganda"]),
        ("Angola", "ao", ["angola"]),
        ("Cameroon", "cm", ["cameroon"]),
        ("Bờ Biển Ngà", "ci", ["bo bien nga", "ivory coast"]),
        ("Ethiopia", "et", ["ethiopia"]),
        ("Tanzania", "tz", ["tanzania"]),
        ("Sudan", "sd", ["sudan"]),
        ("Libya", "ly", ["libya"]),
        ("Somalia", "so", ["somalia"]),
        ("Afghanistan", "af", ["afghanistan"]),
    ],
    "hard": [
        ("Yemen", "ye", ["yemen"]),
        ("Bolivia", "bo", ["bolivia"]),
        ("Paraguay", "py", ["paraguay"]),
        ("Uruguay", "uy", ["uruguay"]),
        ("Bhutan", "bt", ["bhutan"]),
        ("Eswatini", "sz", ["eswatini", "swaziland"]),
        ("Kyrgyzstan", "kg", ["kyrgyzstan"]),
        ("Turkmenistan", "tm", ["turkmenistan"]),
        ("Vanuatu", "vu", ["vanuatu"]),
        ("Suriname", "sr", ["suriname"]),
        ("Djibouti", "dj", ["djibouti"]),
        ("Lesotho", "ls", ["le tho so", "lesotho"]),
        ("Palau", "pw", ["palau"]),
        ("Tuvalu", "tv", ["tuvalu"]),
        ("Andorra", "ad", ["andorra"]),
        ("Liechtenstein", "li", ["liechtenstein"]),
        ("Monaco", "mc", ["monaco"]),
        ("San Marino", "sm", ["san marino"]),
        ("Vatican", "va", ["vatican", "holy see"]),
        ("Maldives", "mv", ["maldives"]),
        ("Fiji", "fj", ["fiji"]),
        ("Samoa", "ws", ["samoa"]),
        ("Tonga", "to", ["tonga"]),
        ("Kiribati", "ki", ["kiribati"]),
        ("Micronesia", "fm", ["micronesia"]),
        ("Quần đảo Marshall", "mh", ["marshall", "marshall islands", "quan dao marshall"]),
        ("Solomon", "sb", ["solomon", "solomon islands"]),
        ("Comoros", "km", ["comoros"]),
        ("Seychelles", "sc", ["seychelles"]),
        ("Mauritius", "mu", ["mauritius"]),
        ("Moldova", "md", ["moldova"]),
        ("Montenegro", "me", ["montenegro"]),
        ("Bắc Macedonia", "mk", ["north macedonia", "macedonia", "bac macedonia"]),
        ("Timor-Leste", "tl", ["timor", "east timor", "dong timor", "đông timor", "timor leste", "timor-leste"]),
        ("Brunei", "bn", ["brunei"]),
        ("Costa Rica", "cr", ["costa rica"]),
        ("Panama", "pa", ["panama"]),
        ("Honduras", "hn", ["honduras"]),
        ("Nicaragua", "ni", ["nicaragua"]),
        ("El Salvador", "sv", ["el salvador"]),
        ("Haiti", "ht", ["haiti"]),
        ("Bahrain", "bh", ["bahrain"]),
        ("Síp", "cy", ["cyprus", "síp"]),
        ("Luxembourg", "lu", ["luxembourg"]),
        ("Malta", "mt", ["malta"]),
    ],
    "insane": [
        ("Bahamas", "bs", ["bahamas"]),
        ("Barbados", "bb", ["barbados"]),
        ("Belize", "bz", ["belize"]),
        ("Guyana", "gy", ["guyana"]),
        ("Jamaica", "jm", ["jamaica"]),
        ("Trinidad and Tobago", "tt", ["trinidad", "trinidad tobago", "trinidad and tobago", "trinidad va tobago", "trinidad và tobago"]),
        ("Cabo Verde", "cv", ["cape verde", "cabo verde"]),
        ("Sao Tome and Principe", "st", ["sao tome", "sao tome and principe", "sao tome va principe", "sao tome và principe"]),
        ("St. Kitts and Nevis", "kn", ["st kitts", "saint kitts", "st kitts and nevis", "st kitts va nevis", "st kitts và nevis", "saint kitts and nevis", "saint kitts va nevis", "saint kitts và nevis"]),
        ("St. Lucia", "lc", ["st lucia", "saint lucia"]),
        ("Saint Vincent and the Grenadines", "vc", ["saint vincent", "st vincent", "saint vincent and the grenadines", "st vincent and the grenadines", "vincent"]),
        ("Grenada", "gd", ["grenada"]),
        ("Antigua và Barbuda", "ag", ["antigua", "antigua barbuda", "antigua and barbuda", "antigua va barbuda"]),
        ("Dominica", "dm", ["dominica"]),
        ("Botswana", "bw", ["botswana"]),
        ("Burkina Faso", "bf", ["burkina", "burkina faso"]),
        ("Burundi", "bi", ["burundi"]),
        ("Chad", "td", ["chad"]),
        ("Congo (Brazzaville)", "cg", ["congo"]),
        ("DRC (Congo Kinshasa)", "cd", ["drc", "democratic republic of congo", "congo kinshasa"]),
        ("Gabon", "ga", ["gabon"]),
        ("Gambia", "gm", ["gambia"]),
        ("Guinea", "gn", ["guinea"]),
        ("Guinea-Bissau", "gw", ["guinea bissau"]),
        ("Guinea Xích Đạo", "gq", ["equatorial guinea", "guinea xich dao"]),
        ("Liberia", "lr", ["liberia"]),
        ("Madagascar", "mg", ["madagascar"]),
        ("Malawi", "mw", ["malawi"]),
        ("Mali", "ml", ["mali"]),
        ("Mauritania", "mr", ["mauritania"]),
        ("Mozambique", "mz", ["mozambique"]),
        ("Namibia", "na", ["namibia"]),
        ("Niger", "ne", ["niger"]),
        ("Rwanda", "rw", ["rwanda"]),
        ("Senegal", "sn", ["senegal"]),
        ("Sierra Leone", "sl", ["sierra leone"]),
        ("Togo", "tg", ["togo"]),
        ("Zambia", "zm", ["zambia"]),
        ("Zimbabwe", "zw", ["zimbabwe"]),
        ("Cộng hoà Dominica", "do", ["dominican republic", "cong hoa dominica"]),
        ("Eritrea", "er", ["eritrea"]),
        ("Nam Sudan", "ss", ["south sudan", "nam sudan"]),
        ("Tajikistan", "tj", ["tajikistan"]),
        ("Papua New Guinea", "pg", ["papua new guinea"]),
        ("Nauru", "nr", ["nauru"]),
        ("Palestine", "ps", ["palestine"]),
        ("Kosovo", "xk", ["kosovo"]),
    ],
}

FLAG_MODE_REWARD_PER_QUESTION = {"easy": 5, "normal": 8, "medium": 12, "hard": 18, "insane": 25}
FLAG_MODE_NAMES = {"easy": "🟢 Dễ", "normal": "🔵 Thường", "medium": "🟡 Trung bình", "hard": "🟠 Khó", "insane": "🔴 Ác mộng"}

DANHGIA_CRITERIA = ["Bố cục", "Màu sắc", "Sáng tạo", "Kỹ thuật"]
DANHGIA_COMMENTS = {
    "low": [
        "Cần cải thiện khá nhiều, thử lại với góc chụp/dựng khác xem sao.",
        "Chưa thực sự nổi bật, còn nhiều điểm để trau chuốt.",
        "Ý tưởng có nhưng thực hiện chưa tới, cố gắng thêm nhé.",
    ],
    "mid": [
        "Ổn áp, có vài điểm sáng nhưng chưa thực sự đột phá.",
        "Tạm được, nếu chỉnh sửa thêm chút sẽ ấn tượng hơn.",
        "Bình thường nhưng không tệ, đủ để xem qua.",
    ],
    "high": [
        "Khá đẹp mắt, bố cục và màu sắc hài hoà.",
        "Ấn tượng tốt, thấy rõ sự đầu tư.",
        "Chất lượng cao, xứng đáng được chú ý.",
    ],
    "top": [
        "Xuất sắc! Đây là kiệt tác thực thụ.",
        "Đỉnh cao, gần như không có điểm trừ nào đáng kể.",
        "Hoàn hảo — chuẩn portfolio chuyên nghiệp.",
    ],
}
DANHGIA_ALLOWED_EXT = (
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".mp4", ".mov", ".webm",
)
DANHGIA_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# Code system
CODE_MAX_USES_DEFAULT = 1
CODE_DEFAULT_DURATION_HOURS = 24

# Daily
DAILY_MIN_REWARD = 1
DAILY_MAX_REWARD = 100
DAILY_STREAK_BONUS_PER_WEEK = 0.05  # +5%/tuần streak
DAILY_TZ_OFFSET_HOURS = 7  # UTC+7 VN

# Jackpot
JACKPOT_MIN_BET = 10
JACKPOT_MAX_BET = 100_000
# Tỉ lệ base ở mức cược thấp (bet = JACKPOT_MIN_BET) và mức cược cao nhất (bet = JACKPOT_MAX_BET)
JACKPOT_BIG_WIN_CHANCE_LOW_BET = 0.25   # 25% ở cược thấp
JACKPOT_BIG_WIN_CHANCE_HIGH_BET = 0.02  # 2% ở cược cao nhất
JACKPOT_SMALL_WIN_CHANCE = 0.20         # cố định 20%, không đổi theo cược
JACKPOT_BIG_WIN_MULTIPLIERS = [2, 3, 4, 5]
JACKPOT_BIG_WIN_WEIGHTS = [50, 30, 15, 5]  # x2 phổ biến nhất, x5 hiếm nhất
JACKPOT_SMALL_WIN_MULTIPLIER = 1.05
JACKPOT_SMALL_LOSS_MULTIPLIERS = [0.75, 0.5, 0.3]
JACKPOT_SMALL_LOSS_WEIGHTS = [50, 30, 20]  # -5% phổ biến nhất, -20% hiếm nhất

# Minesweeper
MINESWEEPER_MIN_DIM = 5
MINESWEEPER_MAX_DIM = 16
MINESWEEPER_DEFAULT_DIM = 9
MINESWEEPER_MINE_RATIO = 0.15
MINESWEEPER_REWARD_PER_SAFE_TILE = 10
MINESWEEPER_CELL_PX = 32

# Minigame chung
MINIGAME_QUESTIONS_PER_GAME = 5
MINIGAME_ATTEMPTS_PER_QUESTION = 3
MINIGAME_SECONDS_PER_QUESTION = 20
MINIGAME_DAILY_LIMIT = 5

MINIGAME_REWARD_PER_QUESTION = {
    "meme": 8,
    "car": 8,
    "country": 10,
    "hoahoc": 15,
    "language": 12,
}
MINIGAME_NAMES = {
    "meme": "Đoán Meme",
    "car": "Đoán Xe",
    "country": "Đoán Quốc Gia",
    "hoahoc": "Hoá Học",
    "language": "Đoán Ngôn Ngữ",
}

# (tên quốc gia, mã ISO cờ, [đáp án ngôn ngữ hợp lệ]) — chỉ dùng quốc gia có ngôn ngữ chính thức rõ ràng
LANGUAGE_POOL = [
    ("Việt Nam", "vn", ["tieng viet", "viet"]),
    ("Nhật Bản", "jp", ["tieng nhat", "nhat"]),
    ("Hàn Quốc", "kr", ["tieng han", "han quoc", "korean"]),
    ("Trung Quốc", "cn", ["tieng trung", "trung quoc", "chinese", "mandarin"]),
    ("Pháp", "fr", ["tieng phap", "phap", "french"]),
    ("Đức", "de", ["tieng duc", "duc", "german"]),
    ("Thái Lan", "th", ["tieng thai", "thai"]),
    ("Nga", "ru", ["tieng nga", "nga", "russian"]),
    ("Ý", "it", ["tieng y", "italian"]),
    ("Tây Ban Nha", "es", ["tieng tay ban nha", "spanish"]),
    ("Brazil", "br", ["tieng bo dao nha", "portuguese"]),
    ("Ấn Độ", "in", ["tieng hindi", "hindi"]),
    ("Indonesia", "id", ["tieng indonesia", "indonesian"]),
    ("Đan Mạch", "dk", ["tieng dan mach", "danish"]),
    ("Hungary", "hu", ["tieng hungary", "hungarian"]),
    ("Cộng hòa Séc", "cz", ["tieng sec", "czech"]),
    ("Thụy Điển", "se", ["tieng thuy dien", "swedish"]),
    ("Na Uy", "no", ["tieng na uy", "norwegian"]),
    ("Hà Lan", "nl", ["tieng ha lan", "dutch"]),
    ("Bồ Đào Nha", "pt", ["tieng bo dao nha", "portuguese"]),
    ("Ba Lan", "pl", ["tieng ba lan", "polish"]),
    ("Thổ Nhĩ Kỳ", "tr", ["tieng tho", "turkish"]),
    ("Ai Cập", "eg", ["tieng a rap", "arabic"]),
    ("Romania", "ro", ["tieng romania", "romanian"]),
    ("Myanmar", "mm", ["tieng myanmar", "burmese"]),
    ("Campuchia", "kh", ["tieng khmer", "khmer"]),
    ("Lào", "la", ["tieng lao", "lao"]),
    ("Mông Cổ", "mn", ["tieng mong co", "mongolian"]),
    ("Phần Lan", "fi", ["tieng phan lan", "finnish"]),
    ("Hy Lạp", "gr", ["tieng hy lap", "greek"]),
    ("Ukraine", "ua", ["tieng ukraina", "ukrainian"]),
    ("Iceland", "is", ["tieng iceland", "icelandic"]),
    ("Croatia", "hr", ["tieng croatia", "croatian"]),
    ("Qatar", "qa", ["tieng a rap", "arabic"]),
    ("Nam Phi", "za", ["tieng anh", "english"]),
]

# Mỗi entry: (tên bài Wikipedia để lấy ảnh, [đáp án hợp lệ (lowercase, không dấu tuỳ)])
MEME_POOL = [
    ("Distracted Boyfriend", ["distracted boyfriend", "chang trai ngoanh lai"]),
    ("Doge (meme)", ["doge"]),
    ("Rickrolling", ["rickroll", "rick roll", "never gonna give you up"]),
    ("Pepe the Frog", ["pepe", "pepe the frog"]),
    ("Grumpy Cat", ["grumpy cat"]),
    ("Nyan Cat", ["nyan cat"]),
    ("Trollface", ["trollface", "troll face"]),
    ("Success Kid", ["success kid"]),
    ("Bad Luck Brian", ["bad luck brian"]),
    ("Woman Yelling at a Cat", ["woman yelling at a cat", "yelling at cat"]),
    ("This Is Fine", ["this is fine"]),
    ("Change My Mind", ["change my mind"]),
    ("Drakeposting", ["drake", "drakeposting", "drake meme"]),
    ("Galaxy Brain", ["galaxy brain", "expanding brain"]),
    ("Shiba Inu (dog breed)", ["shiba inu", "shiba"]),
    ("Keyboard Cat", ["keyboard cat"]),
    ("Harambe", ["harambe"]),
    ("Y U No", ["y u no"]),
    ("Ermahgerd", ["ermahgerd", "gerbil girl"]),
    ("Philosoraptor", ["philosoraptor"]),
]

CAR_POOL = [
    ("Toyota", ["toyota"]),
    ("Ford Motor Company", ["ford"]),
    ("Ferrari", ["ferrari"]),
    ("Lamborghini", ["lamborghini", "lambo"]),
    ("Porsche", ["porsche"]),
    ("BMW", ["bmw"]),
    ("Mercedes-Benz", ["mercedes", "mercedes-benz", "mercedes benz"]),
    ("Audi", ["audi"]),
    ("Honda", ["honda"]),
    ("Volkswagen", ["volkswagen", "vw"]),
    ("Chevrolet", ["chevrolet", "chevy"]),
    ("Nissan", ["nissan"]),
    ("Tesla, Inc.", ["tesla"]),
    ("Bugatti", ["bugatti"]),
    ("Rolls-Royce Motor Cars", ["rolls-royce", "rolls royce"]),
    ("Bentley", ["bentley"]),
    ("Jaguar Cars", ["jaguar"]),
    ("Mazda", ["mazda"]),
    ("Hyundai Motor Company", ["hyundai"]),
    ("Kia Corporation", ["kia"]),
    ("Subaru", ["subaru"]),
    ("Peugeot", ["peugeot"]),
    ("Renault", ["renault"]),
    ("Volvo Cars", ["volvo"]),
    ("Mitsubishi Motors", ["mitsubishi"]),
]

# (tên bài Wikipedia, [đáp án hợp lệ tên quốc gia])
COUNTRY_POOL = [
    ("Eiffel Tower", ["phap", "france"]),
    ("Statue of Liberty", ["my", "hoa ky", "usa", "united states"]),
    ("Great Wall of China", ["trung quoc", "china"]),
    ("Taj Mahal", ["an do", "india"]),
    ("Mount Fuji", ["nhat ban", "japan"]),
    ("Colosseum", ["y", "italy", "italia"]),
    ("Big Ben", ["anh", "uk", "united kingdom", "england"]),
    ("Sydney Opera House", ["uc", "australia"]),
    ("Christ the Redeemer (statue)", ["brazil", "brasil"]),
    ("Machu Picchu", ["peru"]),
    ("Pyramids of Giza", ["ai cap", "egypt"]),
    ("Petra", ["jordan"]),
    ("Angkor Wat", ["campuchia", "cambodia"]),
    ("Ha Long Bay", ["viet nam", "vietnam"]),
    ("Burj Khalifa", ["uae", "united arab emirates", "dubai"]),
    ("Kimchi", ["han quoc", "korea", "south korea"]),
    ("Pho", ["viet nam", "vietnam"]),
    ("Pad thai", ["thai lan", "thailand"]),
    ("Sushi", ["nhat ban", "japan"]),
    ("Paella", ["tay ban nha", "spain"]),
    ("Bratwurst", ["duc", "germany"]),
    ("Poutine", ["canada"]),
    ("Moscow Kremlin", ["nga", "russia"]),
    ("Table Mountain", ["nam phi", "south africa"]),
    ("Neuschwanstein Castle", ["duc", "germany"]),
]

HOAHOC_QUESTIONS = [
    {"q": "Công thức hoá học của Nước là gì?", "answers": ["h2o"]},
    {"q": "Công thức hoá học của Muối ăn (Natri Clorua) là gì?", "answers": ["nacl"]},
    {"q": "Công thức hoá học của Khí Cacbonic là gì?", "answers": ["co2"]},
    {"q": "Công thức hoá học của Khí Oxi là gì?", "answers": ["o2"]},
    {"q": "Công thức hoá học của Khí Nitơ là gì?", "answers": ["n2"]},
    {"q": "Công thức hoá học của Axit Sunfuric là gì?", "answers": ["h2so4"]},
    {"q": "Công thức hoá học của Axit Clohidric là gì?", "answers": ["hcl"]},
    {"q": "Công thức hoá học của Amoniac là gì?", "answers": ["nh3"]},
    {"q": "Công thức hoá học của Metan là gì?", "answers": ["ch4"]},
    {"q": "Công thức hoá học của Đường ăn (Glucozo) là gì?", "answers": ["c6h12o6"]},
    {"q": "Công thức hoá học của Vôi sống (Canxi Oxit) là gì?", "answers": ["cao"]},
    {"q": "Công thức hoá học của Đá vôi (Canxi Cacbonat) là gì?", "answers": ["caco3"]},
    {"q": "Công thức hoá học của Xút ăn da (Natri Hidroxit) là gì?", "answers": ["naoh"]},
    {"q": "Công thức hoá học của Khí Hidro là gì?", "answers": ["h2"]},
    {"q": "Ký hiệu hoá học của nguyên tố Sắt là gì?", "answers": ["fe"]},
    {"q": "Ký hiệu hoá học của nguyên tố Vàng là gì?", "answers": ["au"]},
    {"q": "Ký hiệu hoá học của nguyên tố Bạc là gì?", "answers": ["ag"]},
    {"q": "Ký hiệu hoá học của nguyên tố Đồng là gì?", "answers": ["cu"]},
    {"q": "Ký hiệu hoá học của nguyên tố Chì là gì?", "answers": ["pb"]},
    {"q": "Ký hiệu hoá học của nguyên tố Kẽm là gì?", "answers": ["zn"]},
    {"q": "Ký hiệu hoá học của nguyên tố Natri là gì?", "answers": ["na"]},
    {"q": "Ký hiệu hoá học của nguyên tố Kali là gì?", "answers": ["k"]},
    {"q": "Ký hiệu hoá học của nguyên tố Canxi là gì?", "answers": ["ca"]},
    {"q": "Ký hiệu hoá học của nguyên tố Nhôm là gì?", "answers": ["al"]},
    {"q": "Ký hiệu hoá học của nguyên tố Thuỷ ngân là gì?", "answers": ["hg"]},
    {"q": "Ký hiệu hoá học của nguyên tố Lưu huỳnh là gì?", "answers": ["s"]},
    {"q": "Ký hiệu hoá học của nguyên tố Cacbon là gì?", "answers": ["c"]},
    {"q": "Ký hiệu hoá học của nguyên tố Photpho là gì?", "answers": ["p"]},
    {"q": "pH của dung dịch trung tính là bao nhiêu?", "answers": ["7"]},
    {"q": "Chất nào có công thức C2H5OH (rượu uống)?", "answers": ["etanol", "ethanol", "ruou etylic", "con"]},
]

# Nối từ (word chain)
NOITU_VOCAB_FILE = "noitu_vocab.json"
NOITU_BINGO_REWARD = 300  # thưởng cho người khiến đối phương bí từ
NOITU_TIMEOUT_SECONDS = None  # None = không giới hạn thời gian giữa các lượt
NOITU_WORD_COOLDOWN_GAMES = 49  # 1 từ đã dùng bị khoá trong N ván tiếp theo

# Level system
LEVEL_XP_NEEDED_BASE = 100
LEVEL_XP_NEEDED_PER_LEVEL = 50  # XP cần(level) = BASE + level * PER_LEVEL

LEVEL_XP_GROWTH_PER_LEVEL = 0.03  # +3% XP nhận mỗi hành động / level hiện tại

LEVEL_MESSAGE_XP_BASE = 25
LEVEL_MESSAGE_COOLDOWN_SEC = 5
LEVEL_MESSAGE_SPAM_COOLDOWN_SEC = 10
LEVEL_MESSAGE_SPAM_THRESHOLD = 5     # số tin nhắn trong SPAM_WINDOW_SEC để coi là spam
LEVEL_MESSAGE_SPAM_WINDOW_SEC = 10

LEVEL_MINIGAME_WIN_XP_BASE = 100
LEVEL_MAX = 1000

# AI Chat
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
AI_CHAT_HISTORY_LENGTH = 8  # số lượt (user+bot) gần nhất giữ làm ngữ cảnh
AI_CHAT_COOLDOWN_SEC = 7
AI_CHAT_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI vui vẻ, thân thiện tên là Delta Mick, tích hợp trong 1 Discord bot giải trí. "
    "Trả lời ngắn gọn, tự nhiên, có thể dùng emoji nhẹ nhàng. Trả lời bằng tiếng Việt trừ khi được hỏi bằng ngôn ngữ khác."
)
AI_CHAT_MAX_OUTPUT_TOKENS = 500

# AI Chat nâng cao
AI_CHAT_QUIET_HOURS_START = 23   # 23h VN
AI_CHAT_QUIET_HOURS_END = 4     # 4h VN — không trả lời /ai hay mention trong khung này
AI_AUTOCHAT_IDLE_MINUTES = 30   # im lặng bao lâu thì bot tự khuấy động
AI_AUTOCHAT_CHECK_INTERVAL_SEC = 300  # tần suất task nền kiểm tra kênh im lặng
AI_AUTOCHAT_PROMPT = (
    "Hãy tự nghĩ ra một câu mở đầu chuyện trò ngắn gọn, vui vẻ, tự nhiên để khơi gợi mọi người trong "
    "server trò chuyện (ví dụ một câu hỏi thú vị, một chủ đề bàn tán, một câu đùa). "
    "Chỉ trả lời đúng 1 câu, không giải thích thêm."
)

# Quest (nhiệm vụ ngày/tuần)
QUEST_DAILY_COUNT = 3
QUEST_WEEKLY_COUNT = 3
QUEST_DAILY_TICKET_EXPIRE_HOURS = 24  # vé từ quest ngày hết hạn sau 24h (tới 0h VN hôm sau)

# Mỗi entry: id, mô tả, loại điều kiện (goal_type), target (số cần đạt), reward pool (chọn ngẫu nhiên 1 loại khi giao quest)
QUEST_POOL_DAILY = [
    {"id": "earn_coins_300", "desc": "Kiếm 300 xu từ bất kỳ hoạt động nào", "goal_type": "earn_coins", "target": 300},
    {"id": "win_minigame_3", "desc": "Thắng 3 ván minigame bất kỳ", "goal_type": "win_minigame", "target": 3},
    {"id": "send_messages_20", "desc": "Gửi 20 tin nhắn trong server", "goal_type": "send_messages", "target": 20},
    {"id": "do_work_1", "desc": "Đi làm (/work) 1 lần", "goal_type": "do_work", "target": 1},
    {"id": "claim_daily_1", "desc": "Điểm danh (/daily) hôm nay", "goal_type": "claim_daily", "target": 1},
    {"id": "play_jackpot_2", "desc": "Chơi /jackpot 2 lần", "goal_type": "play_jackpot", "target": 2},
    {"id": "win_wordle_1", "desc": "Thắng 1 ván /wordle", "goal_type": "win_wordle", "target": 1},
    {"id": "win_flag_1", "desc": "Thắng ít nhất 1 câu trong /flag", "goal_type": "win_flag", "target": 1},
    {"id": "noitu_correct_3", "desc": "Nối đúng 3 từ trong trò nối từ", "goal_type": "noitu_correct", "target": 3},
]

QUEST_POOL_WEEKLY = [
    {"id": "earn_coins_2000", "desc": "Kiếm 2000 xu trong tuần", "goal_type": "earn_coins", "target": 2000},
    {"id": "win_minigame_15", "desc": "Thắng 15 ván minigame bất kỳ trong tuần", "goal_type": "win_minigame", "target": 15},
    {"id": "do_work_5", "desc": "Đi làm (/work) 5 lần trong tuần", "goal_type": "do_work", "target": 5},
    {"id": "claim_daily_5", "desc": "Điểm danh (/daily) 5 ngày trong tuần", "goal_type": "claim_daily", "target": 5},
    {"id": "play_chess_3", "desc": "Chơi 3 ván /chess (bất kỳ kết quả) trong tuần", "goal_type": "play_chess", "target": 3},
    {"id": "win_minesweeper_3", "desc": "Thắng 3 ván /minesweeper trong tuần", "goal_type": "win_minesweeper", "target": 3},
]

# Reward pool: khi giao quest, random 1 loại thưởng trong danh sách này (giá trị theo mức "ngày" hoặc "tuần")
QUEST_REWARD_POOL_DAILY = [
    {"type": "coins", "amount": 150},
    {"type": "elo", "amount": 80},
    {"type": "xp", "amount": 200},
    {"type": "game_ticket", "amount": 3},
]
QUEST_REWARD_POOL_WEEKLY = [
    {"type": "coins", "amount": 1000},
    {"type": "elo", "amount": 500},
    {"type": "xp", "amount": 1500},
    {"type": "game_ticket", "amount": 10},
]

# Shop
SHOP_REFRESH_INTERVAL_MIN = 10
SHOP_ITEMS_PER_ROTATION = 7
SHOP_RARITY_STOCK_RANGE = {
    "common": (5, 10),
    "rare": (1, 3),
    "epic": (1, 1),
}

# Mỗi item: id ổn định, tên, mô tả, giá, tiền tệ (coins|elo), rarity, effect (dict máy đọc được nếu instant áp dụng ngay được)
# category: "instant" = áp dụng hiệu ứng ngay khi mua; "inventory" = lưu vào kho đồ, chờ tích hợp vào hệ thống liên quan (chess timer/IQ bot/gợi ý, x2-x3 coins theo giờ...)
SHOP_ITEMS = {
    "mua_tai": {
        "name": "Mua Tài", "desc": "+100 ELO", "price": 50, "currency": "coins",
        "rarity": "rare", "category": "instant", "effect": {"elo": 100},
    },
    "gia_tri_tri_oc": {
        "name": "Giá Trị Trí Óc", "desc": "+10 ELO", "price": 4, "currency": "coins",
        "rarity": "common", "category": "instant", "effect": {"elo": 10},
    },
    "thien_tai_hop_the": {
        "name": "Thiên Tài Hợp Thể", "desc": "+1000 ELO", "price": 650, "currency": "coins",
        "rarity": "common", "category": "instant", "effect": {"elo": 1000},
    },
    "than_nhan_hop_the": {
        "name": "Thần Nhân Hợp Thể", "desc": "+1500 ELO và +30% IQ bot ELO (hiệu lực 1h, hồi chiêu 6h)",
        "price": 800, "currency": "coins", "rarity": "epic", "category": "instant",
        "effect": {"elo": 1500}, "extra_effect": {"type": "bot_iq_boost", "value": 0.3, "duration_hours": 1, "cooldown_hours": 6},
    },
    "goi_y_co_vua": {
        "name": "Gợi Ý Cờ Vua", "desc": "+1 gợi ý nước đi trong trận tiếp theo", "price": 150, "currency": "coins",
        "rarity": "rare", "category": "inventory", "effect": {"chess_hints": 1},
    },
    "ve_game_dong": {
        "name": "Vé Game Đồng", "desc": "+1 lượt chơi", "price": 250, "currency": "coins",
        "rarity": "common", "category": "instant", "effect": {"game_plays": 1},
    },
    "ve_game_bac": {
        "name": "Vé Game Bạc", "desc": "+5 lượt chơi", "price": 1250, "currency": "coins",
        "rarity": "common", "category": "instant", "effect": {"game_plays": 5},
    },
    "ve_game_hoang_kim": {
        "name": "Vé Game Hoàng Kim", "desc": "+10 lượt chơi", "price": 2550, "currency": "coins",
        "rarity": "rare", "category": "instant", "effect": {"game_plays": 10},
    },
    "ve_game_kim_cuong": {
        "name": "Vé Game Kim Cương", "desc": "+20 lượt chơi", "price": 5250, "currency": "coins",
        "rarity": "rare", "category": "instant", "effect": {"game_plays": 20},
    },
    "tui_delta": {
        "name": "Túi Delta", "desc": "+10 delta coins", "price": 50, "currency": "elo",
        "rarity": "common", "category": "instant", "effect": {"coins": 10},
    },
    "boc_delta": {
        "name": "Bọc Delta", "desc": "+100 delta coins", "price": 550, "currency": "elo",
        "rarity": "rare", "category": "instant", "effect": {"coins": 100},
    },
    "tui_delta_lon": {
        "name": "Túi Delta Lớn", "desc": "+300 delta coins", "price": 1600, "currency": "elo",
        "rarity": "epic", "category": "instant", "effect": {"coins": 300},
    },
    "khien_thoi_gian": {
        "name": "Khiên Thời Gian", "desc": "+60 giây thời gian cờ vua trong trận tiếp theo", "price": 300, "currency": "coins",
        "rarity": "common", "category": "inventory", "effect": {"chess_time_bonus_sec": 60},
    },
    "rua_thoi_gian": {
        "name": "Rùa Thời Gian", "desc": "+180 giây thời gian cờ vua trong trận tiếp theo", "price": 1000, "currency": "coins",
        "rarity": "rare", "category": "inventory", "effect": {"chess_time_bonus_sec": 180},
    },
    "la_chan_cho_doi": {
        "name": "Lá Chắn Chờ Đợi", "desc": "+300 giây thời gian cờ vua trong trận tiếp theo", "price": 1750, "currency": "coins",
        "rarity": "epic", "category": "inventory", "effect": {"chess_time_bonus_sec": 300},
    },
    "thoi_lo": {
        "name": "Thối Lộ", "desc": "Tự động nhắn tin riêng gợi ý nước đi tiếp theo (chỉ PvP, 1 lần/ngày, không áp dụng bot)",
        "price": 2000, "currency": "coins", "rarity": "epic", "category": "inventory", "effect": {"chess_dm_hint": 1},
    },
    "thoi_gian_vang": {
        "name": "Thời Gian Vàng", "desc": "×2 delta coins trong 24 giờ", "price": 750, "currency": "elo",
        "rarity": "rare", "category": "inventory", "effect": {"coins_mult_temp": 1.0, "duration_hours": 24},
    },
    "gap_ba_tien_te": {
        "name": "Gấp Ba Tiền Tệ", "desc": "×3 delta coins trong 24 giờ", "price": 1750, "currency": "elo",
        "rarity": "epic", "category": "inventory", "effect": {"coins_mult_temp": 2.0, "duration_hours": 24},
    },
    "qua_oc_cho": {
        "name": "Quả Óc Chó", "desc": "+30% IQ bot ELO cờ vua trong trận tiếp theo", "price": 75, "currency": "coins",
        "rarity": "rare", "category": "inventory", "effect": {"bot_iq_boost_next": 0.3},
    },
    "tri_tue_nhan_tao": {
        "name": "Trí Tuệ Nhân Tạo", "desc": "+1000 IQ bot ELO cờ vua trong trận tiếp theo", "price": 750, "currency": "coins",
        "rarity": "epic", "category": "inventory", "effect": {"bot_iq_boost_next_flat": 1000},
    },
    "mango_mustard_item": {
        "name": "Mango Mustard", "desc": "+367 delta coins, 9% tỉ lệ nhận thêm danh hiệu \"Mango Mustard\"",
        "price": 1800, "currency": "coins", "rarity": "epic", "category": "instant",
        "effect": {"coins": 367}, "title_chance": {"title_key": "mango_mustard", "chance": 0.09},
    },
    "ronaldo_pasta_item": {
        "name": "Ronaldo Pasta", "desc": "+300 ELO, 16% tỉ lệ nhận thêm danh hiệu \"Ronaldo Pasta\"",
        "price": 1000, "currency": "elo", "rarity": "epic", "category": "instant",
        "effect": {"elo": 300}, "title_chance": {"title_key": "ronaldo_pasta", "chance": 0.16},
    },
    "role_delta_mick_bikini": {
        "name": "Role Delta Mick Bikini", "desc": "Nhận role Delta Mick Bikini (giới hạn)", "price": 9000, "currency": "coins",
        "rarity": "epic", "category": "instant", "effect": {"role_id": 1530851089480417340},
    },
    "delta_mick_title": {
        "name": "Delta Mick", "desc": "Danh hiệu \"Delta\"", "price": 400, "currency": "coins",
        "rarity": "rare", "category": "instant", "effect": {"title_key": "delta"},
    },
    "selta_dex_title": {
        "name": "Selta Dex", "desc": "Danh hiệu \"Selta Dex\"", "price": 1400, "currency": "coins",
        "rarity": "epic", "category": "instant", "effect": {"title_key": "selta_dex"},
    },
    "than_delta_title": {
        "name": "Thần Delta", "desc": "Danh hiệu \"Thần Delta\" (60% tỉ lệ KHÔNG nhận được)",
        "price": 4500, "currency": "coins", "rarity": "epic", "category": "instant",
        "effect": {"title_key": "than_delta"}, "fail_chance": 0.6,
    },
}

# Chess
CHESS_CELL_PX = 64
CHESS_BOT_DIFFICULTY_ELO = {"easy": 800, "medium": 1200, "hard": 1800}
CHESS_BOT_DIFFICULTY_DEPTH = {"easy": 0, "medium": 2, "hard": 3}  # 0 = random move
CHESS_CHALLENGE_TIMEOUT_SEC = 120
CHESS_STARTING_ELO = 800
CHESS_ELO_K_FACTOR = 32

# Title system
# key: id nội bộ ổn định (không đổi dù đổi tên hiển thị)
# name: tên hiển thị (dùng trong autocomplete và /give-title)
# desc: mô tả buff (chỉ hiển thị, buff thực tế áp dụng dần khi các hệ thống liên quan hoàn thiện)
# unlock: điều kiện mở khoá bằng lời (hiển thị tham khảo; /give-title cấp thủ công, không tự check)
TITLES = {
    "delta": {"name": "Delta", "desc": "Danh hiệu cơ bản", "unlock": "Mua ở /shop", "buffs": {}},
    "selta_dex": {"name": "Selta Dex", "desc": "×1.2 delta coins", "unlock": "Mua ở /shop", "buffs": {"coins_mult_global": 0.2}},
    "ronaldo_pasta": {"name": "Ronaldo Pasta", "desc": "×1.1 ELO", "unlock": "Mua ở /shop", "buffs": {}},
    "than_delta": {"name": "Thần Delta", "desc": "×1.5 delta coins", "unlock": "Mua ở /shop", "buffs": {"coins_mult_global": 0.5}},
    "delta_mick": {"name": "Delta Mick", "desc": "×1.35 delta coins", "unlock": "Có role <@&1529110081168216084>", "buffs": {"coins_mult_global": 0.35}},
    "mango_mustard": {"name": "Mango Mustard", "desc": "×1.4 delta coins", "unlock": "Có role <@&1531564795231207424>", "buffs": {"coins_mult_global": 0.4}},
    "meme_title": {"name": "Meme", "desc": "×1.1 delta coins", "unlock": "Có role <@&1529765560433381427>", "buffs": {"coins_mult_global": 0.1}},
    "dia_ly": {"name": "Địa Lý", "desc": "+1 lượt chơi /flag vĩnh viễn", "unlock": "Thắng /flag 5 lần", "buffs": {"extra_plays_flag": 1}},
    "nha_tham_hiem": {"name": "Nhà Thám Hiểm", "desc": "×1.2 delta coins phần thưởng /flag", "unlock": "Thắng /flag 15 lần", "buffs": {"coins_mult_flag": 0.2}},
    "bac_thay_dia_ly": {"name": "Bậc Thầy Địa Lý", "desc": "×1.5 delta coins phần thưởng /flag", "unlock": "Thắng /flag 50 lần", "buffs": {"coins_mult_flag": 0.5}},
    "doan_tu": {"name": "Đoán Từ", "desc": "+1 lượt chơi /wordle vĩnh viễn", "unlock": "Thắng /wordle 5 lần", "buffs": {"extra_plays_wordle": 1}},
    "bac_thay_tu_vung": {"name": "Bậc Thầy Từ Vựng", "desc": "×1.1 delta coins phần thưởng /wordle", "unlock": "Thắng /wordle 15 lần", "buffs": {"coins_mult_wordle": 0.1}},
    "tu_dien_song": {"name": "Từ Điển Sống", "desc": "×1.5 delta coins phần thưởng /wordle", "unlock": "Thắng /wordle 50 lần", "buffs": {"coins_mult_wordle": 0.5}},
    "gay_cuoi": {"name": "Gây Cười", "desc": "×1.1 delta coins phần thưởng /meme", "unlock": "Thắng /meme 4 lần", "buffs": {"coins_mult_meme": 0.1}},
    "chua_meme": {"name": "Chúa Meme", "desc": "×1.3 delta coins phần thưởng /meme", "unlock": "Thắng /meme 15 lần", "buffs": {"coins_mult_meme": 0.3}},
    "huyen_thoai_meme": {"name": "Huyền Thoại Meme", "desc": "×1.6 delta coins phần thưởng /meme, +1 lượt /meme vĩnh viễn", "unlock": "Thắng /meme 40 lần", "buffs": {"coins_mult_meme": 0.6, "extra_plays_meme": 1}},
    "xe_co": {"name": "Xe Cộ", "desc": "×1.1 delta coins phần thưởng /car", "unlock": "Thắng /car 3 lần", "buffs": {"coins_mult_car": 0.1}},
    "tay_dua": {"name": "Tay Đua", "desc": "×1.3 delta coins phần thưởng /car", "unlock": "Thắng /car 15 lần", "buffs": {"coins_mult_car": 0.3}},
    "vua_xe_co": {"name": "Vua Xe Cộ", "desc": "×1.6 delta coins phần thưởng /car, +1 lượt /car vĩnh viễn", "unlock": "Thắng /car 40 lần", "buffs": {"coins_mult_car": 0.6, "extra_plays_car": 1}},
    "hon_dao": {"name": "Hòn Đảo", "desc": "×1.1 delta coins phần thưởng /country", "unlock": "Thắng /country 5 lần", "buffs": {"coins_mult_country": 0.1}},
    "nha_du_hanh": {"name": "Nhà Du Hành", "desc": "×1.3 delta coins phần thưởng /country", "unlock": "Thắng /country 20 lần", "buffs": {"coins_mult_country": 0.3}},
    "bach_khoa_the_gioi": {"name": "Bách Khoa Thế Giới", "desc": "×1.6 delta coins phần thưởng /country, +1 lượt /country vĩnh viễn", "unlock": "Thắng /country 50 lần", "buffs": {"coins_mult_country": 0.6, "extra_plays_country": 1}},
    "hoa_hoc": {"name": "Hoá Học", "desc": "×1.1 delta coins, +30% độ khó /hoahoc", "unlock": "Thắng /hoahoc 6 lần", "buffs": {"coins_mult_hoahoc": 0.1}},
    "nha_choi_thuoc": {"name": "Nhà Chơi Thuốc", "desc": "×1.4 delta coins, +60% độ khó /hoahoc", "unlock": "Thắng /hoahoc 18 lần", "buffs": {"coins_mult_hoahoc": 0.4}},
    "nha_khoa_hoc": {"name": "Nhà Khoa Học", "desc": "×2 delta coins, +120% độ khó /hoahoc", "unlock": "Thắng /hoahoc 36 lần từ mode trung bình trở lên", "buffs": {"coins_mult_hoahoc": 1.0}},
    "ke_thu_van": {"name": "Kẻ Thử Vận", "desc": "Không có buff", "unlock": "Dùng /jackpot 1 lần", "buffs": {}},
    "con_bac_moi_noi": {"name": "Con Bạc Mới Nổi", "desc": "+5% may mắn /jackpot", "unlock": "Dùng /jackpot 20 lần", "buffs": {"jackpot_luck": 0.05}},
    "tay_choi_lao_luyen": {"name": "Tay Chơi Lão Luyện", "desc": "+15% may mắn /jackpot", "unlock": "Dùng /jackpot 100 lần", "buffs": {"jackpot_luck": 0.15}},
    "khanh_kiet": {"name": "Khánh Kiệt", "desc": "Không có buff", "unlock": "Thua cược /jackpot 1 lần", "buffs": {}},
    "tho_san_jackpot": {"name": "Thợ Săn Jackpot", "desc": "Không có buff", "unlock": "Thắng cược /jackpot 1 lần", "buffs": {}},
    "trieu_phu_jackpot": {"name": "Triệu Phú Jackpot", "desc": "×1.2 delta coins phần thưởng /jackpot", "unlock": "Kiếm tổng 100k delta coins từ /jackpot", "buffs": {"coins_mult_jackpot": 0.2}},
    "chuoi_thang": {"name": "Chuỗi Thắng", "desc": "+20% may mắn /jackpot", "unlock": "Thắng 10 ván /jackpot liên tiếp", "buffs": {"jackpot_luck": 0.2}},
    "con_cung_than_may_man": {"name": "Con Cưng Thần May Mắn", "desc": "+10% may mắn /jackpot", "unlock": "Trúng jackpot lớn nhất", "buffs": {"jackpot_luck": 0.1}},
    "vua_song_bac": {"name": "Vua Sòng Bạc", "desc": "×1.5 delta coins phần thưởng /jackpot, +5% may mắn /jackpot", "unlock": "Trúng jackpot 10 lần", "buffs": {"coins_mult_jackpot": 0.5, "jackpot_luck": 0.05}},
    "huyen_thoai_jackpot": {"name": "Huyền Thoại Jackpot", "desc": "×2 delta coins phần thưởng /jackpot, +15% may mắn vĩnh viễn (toàn bộ)", "unlock": "Chơi 1000 lần hoặc đạt mọi danh hiệu /jackpot", "buffs": {"coins_mult_jackpot": 1.0, "jackpot_luck": 0.15}},
    "cao_thu": {"name": "Cao Thủ", "desc": "+1 lượt chơi trò chơi đoán vĩnh viễn", "unlock": "Thắng 100 ván trò chơi tổng", "buffs": {"extra_plays_wordle": 1, "extra_plays_flag": 1}},
    "huyen_thoai_tro_choi": {"name": "Huyền Thoại Trò Chơi", "desc": "×1.5 delta coins, +3 lượt chơi trò chơi đoán vĩnh viễn", "unlock": "Thắng 1000 ván trò chơi tổng", "buffs": {"coins_mult_global": 0.5, "extra_plays_wordle": 3, "extra_plays_flag": 3}},
    "bach_khoa_toan_thu": {"name": "Bách Khoa Toàn Thư", "desc": "×3 delta coins, +8 lượt chơi trò chơi đoán vĩnh viễn", "unlock": "Thắng 5000 ván trò chơi đoán từ tổng", "buffs": {"coins_mult_global": 2.0, "extra_plays_wordle": 8, "extra_plays_flag": 8}},
    "co_thu_nhap": {"name": "Có Thu Nhập", "desc": "×1.2 delta coins", "unlock": "Kiếm tổng 5k delta coins", "buffs": {"coins_mult_global": 0.2}},
    "trieu_phu": {"name": "Triệu Phú", "desc": "×1.6 delta coins", "unlock": "Kiếm tổng 1M delta coins", "buffs": {"coins_mult_global": 0.6}},
    "ti_phu": {"name": "Tỉ Phú", "desc": "×2.1 delta coins", "unlock": "Kiếm tổng 1B delta coins", "buffs": {"coins_mult_global": 1.1}},
    "tong_tai_nghin_ti": {"name": "Tổng Tài Nghìn Tỉ", "desc": "×3 delta coins", "unlock": "Kiếm tổng 1T delta coins", "buffs": {"coins_mult_global": 2.0}},
    "cong_viec_dau_tien": {"name": "Công Việc Đầu Tiên", "desc": "×1.1 delta coins", "unlock": "Nhận lương /work 1 lần", "buffs": {"coins_mult_global": 0.1}},
    "cham_chi": {"name": "Chăm Chỉ", "desc": "×1.2 delta coins phần thưởng /work, -10% tỉ lệ sự kiện xui", "unlock": "Dùng /work 10 lần", "buffs": {"coins_mult_work": 0.2, "work_bad_event_reduction": 0.1}},
    "doanh_nhan": {"name": "Doanh Nhân", "desc": "×1.8 delta coins phần thưởng /work, -20% tỉ lệ sự kiện xui, +10% tỉ lệ thăng chức", "unlock": "Dùng /work 100 lần", "buffs": {"coins_mult_work": 0.8, "work_bad_event_reduction": 0.2}},
    "ong_trum_doanh_nghiep": {"name": "Ông Trùm Doanh Nghiệp", "desc": "×2.5 delta coins phần thưởng /work, +20% tỉ lệ thăng chức, +2 lượt /work vĩnh viễn", "unlock": "Dùng /work 1000 lần", "buffs": {"coins_mult_work": 1.5, "extra_plays_work": 2}},
    "kien_tri": {"name": "Kiên Trì", "desc": "+1 lượt /work vĩnh viễn", "unlock": "Điểm danh /work 7 ngày liên tiếp", "buffs": {"extra_plays_work": 1}},
    "diem_danh_chuyen_can": {"name": "Điểm Danh Chuyên Cần", "desc": "×1.3 delta coins, -20% tỉ lệ sự kiện xui, -15% thời gian work", "unlock": "Điểm danh /work 30 ngày", "buffs": {"coins_mult_work": 0.3, "work_bad_event_reduction": 0.2}},
    "tong_tai": {"name": "Tổng Tài", "desc": "×1.5 delta coins phần thưởng /work, +1 lượt /work vĩnh viễn", "unlock": "Thăng chức 'chủ tịch' tại công ty bất kỳ", "buffs": {"coins_mult_work": 0.5, "extra_plays_work": 1}},
    "xui_xeo": {"name": "Xui Xẻo", "desc": "Không có buff", "unlock": "Gặp sự kiện xui trong /work 1 lần", "buffs": {}},
    "may_man": {"name": "May Mắn", "desc": "+15% tỉ lệ sự kiện tốt trong /work", "unlock": "Gặp tổng 100 sự kiện trong /work", "buffs": {"work_bad_event_reduction": 0.15}},
    "khach_hang": {"name": "Khách Hàng", "desc": "×1.1 delta coins", "unlock": "Mua vật phẩm đầu tiên", "buffs": {"coins_mult_global": 0.1}},
    "tieu_tien": {"name": "Tiêu Tiền", "desc": "-10% giá mua ở shop (trừ vật phẩm sự kiện/giới hạn/gói đặc biệt)", "unlock": "Tiêu 1k delta coins", "buffs": {"shop_discount": 0.1}},
    "khach_vip": {"name": "Khách VIP", "desc": "-15% giá mua ở shop", "unlock": "Tiêu 100k delta coins", "buffs": {"shop_discount": 0.15}},
    "dai_gia_mua_sam": {"name": "Đại Gia Mua Sắm", "desc": "-20% giá mua ở shop", "unlock": "Tiêu 5M delta coins", "buffs": {"shop_discount": 0.2}},
    "ong_trum_mua_sam": {"name": "Ông Trùm Mua Sắm", "desc": "×1.5 delta coins, -25% giá mua ở shop", "unlock": "Tiêu 1B delta coins", "buffs": {"coins_mult_global": 0.5, "shop_discount": 0.25}},
    "khach_hang_dac_biet": {"name": "Khách Hàng Đặc Biệt", "desc": "Không có buff", "unlock": "Mua vật phẩm sự kiện đầu tiên", "buffs": {}},
    "phien_ban_gioi_han": {"name": "Phiên Bản Giới Hạn", "desc": "×1.2 delta coins", "unlock": "Mua vật phẩm giới hạn đầu tiên", "buffs": {"coins_mult_global": 0.2}},
    "xin_chao": {"name": "Xin Chào!", "desc": "+20 delta coins", "unlock": "Dùng 1 lệnh bất kỳ", "buffs": {}},
    "lam_mom": {"name": "Lắm Mồm", "desc": "×1.1 delta coins", "unlock": "Gửi 100 tin nhắn", "buffs": {"coins_mult_global": 0.1}},
    "cay_tam": {"name": "Cây Tám", "desc": "×1.15 delta coins", "unlock": "Gửi 1k tin nhắn", "buffs": {"coins_mult_global": 0.15}},
    "huyen_thoai_tro_chuyen": {"name": "Huyền Thoại Trò Chuyện", "desc": "×1.25 delta coins", "unlock": "Gửi 10k tin nhắn", "buffs": {"coins_mult_global": 0.25}},
    "nguoi_moi": {"name": "Người Mới", "desc": "+10 delta coins", "unlock": "Tham gia server 1 ngày", "buffs": {}},
    "cu_dan_delta": {"name": "Cư Dân Delta", "desc": "+200 delta coins", "unlock": "Tham gia server 7 ngày", "buffs": {}},
    "thanh_vien_ky_cuu": {"name": "Thành Viên Kỳ Cựu", "desc": "×1.1 delta coins", "unlock": "Tham gia server 30 ngày", "buffs": {"coins_mult_global": 0.1}},
    "huyen_thoai_delta": {"name": "Huyền Thoại Delta", "desc": "×1.3 delta coins", "unlock": "Tham gia server 365 ngày", "buffs": {"coins_mult_global": 0.3}},
    "huyen_thoai_moi_noi": {"name": "Huyền Thoại Mới Nổi", "desc": "×1.1 delta coins", "unlock": "Lọt top 500 delta coins", "buffs": {"coins_mult_global": 0.1}},
    "ngoi_sao_delta": {"name": "Ngôi Sao Delta", "desc": "×1.3 delta coins", "unlock": "Lọt top 100 delta coins", "buffs": {"coins_mult_global": 0.3}},
    "lot_vao_top_10": {"name": "Lọt Vào Top 10", "desc": "×1.8 delta coins", "unlock": "Lọt top 10 delta coins", "buffs": {"coins_mult_global": 0.8}},
    "vi_than_delta": {"name": "Vị Thần Delta", "desc": "×2.5 delta coins", "unlock": "Top 1 delta coins", "buffs": {"coins_mult_global": 1.5}},
    "dau_si": {"name": "Đấu Sĩ", "desc": "×1.1 ELO", "unlock": "Lọt top 500 ELO", "buffs": {}},
    "cao_thu_elo": {"name": "Cao Thủ", "desc": "×1.2 ELO", "unlock": "Lọt top 100 ELO", "buffs": {}},
    "dai_cao_thu": {"name": "Đại Cao Thủ", "desc": "×1.5 ELO", "unlock": "Lọt top 10 ELO", "buffs": {}},
    "vua_dau_truong": {"name": "Vua Đấu Trường", "desc": "×2 ELO", "unlock": "Top 1 ELO", "buffs": {}},
    "than_thoai": {"name": "Thần Thoại", "desc": "×1.5 ELO, +1 lượt tất cả minigame vĩnh viễn", "unlock": "Top 1 delta coins và top 1 ELO", "buffs": {"extra_plays_wordle": 1, "extra_plays_flag": 1}},
    "huyen_thoai_bat_bai": {"name": "Huyền Thoại Bất Bại", "desc": "×3 delta coins, ×2.5 ELO, +3 lượt tất cả minigame vĩnh viễn", "unlock": "Giữ Top 1 delta coins và Top 1 ELO liên tục 30 ngày", "buffs": {"coins_mult_global": 2.0, "extra_plays_wordle": 3, "extra_plays_flag": 3}},
    "huyen_thoai_loi_thoi": {"name": "Huyền Thoại Lỗi Thời", "desc": "Không có buff", "unlock": "Từng đạt Top 1 delta coins/ELO nhưng hiện không còn giữ", "buffs": {}},
    "tan_binh": {"name": "Tân Binh", "desc": "×1.05 delta coins", "unlock": "Đạt level 5", "buffs": {"coins_mult_global": 0.05}},
    "lao_lang": {"name": "Lão Làng", "desc": "×1.15 delta coins", "unlock": "Đạt level 20", "buffs": {"coins_mult_global": 0.15}},
    "ky_cuu": {"name": "Kỳ Cựu", "desc": "×1.3 delta coins", "unlock": "Đạt level 50", "buffs": {"coins_mult_global": 0.3}},
    "bac_thay": {"name": "Bậc Thầy", "desc": "×1.4 delta coins", "unlock": "Đạt level 100", "buffs": {"coins_mult_global": 0.4}},
    "huyen_thoai": {"name": "Huyền Thoại", "desc": "×1.5 delta coins", "unlock": "Đạt level 200", "buffs": {"coins_mult_global": 0.5}},
}
TITLE_MAX_EQUIPPED = 3