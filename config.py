# Meme Achievement
MEME_CONFIG = {
    "channel_id": 1528562696398831616,  # Kênh meme
    "role_id": 1529765560433381427,  # Role thưởng
    "required_count": 20,  # Số meme cần đạt
    "cooldown_minutes": 2,  # Thời gian giữa các lần kiểm tra (phút)
}

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
        "chance": 0.03,
    },
    {
        "key": "boss_bankrupt",
        "text": "📉 Sếp vỡ nợ và bỏ trốn — công ty tạm ngừng hoạt động, bạn cần tìm việc khác.",
        "penalty_hours": 48,
        "chance": 0.05,
    },
    {
        "key": "company_layoff",
        "text": "✂️ Công ty cắt giảm nhân sự lớn — bạn bị tạm cho nghỉ để tái cơ cấu.",
        "penalty_hours": 36,
        "chance": 0.08,
    },
    {
        "key": "server_crash",
        "text": "🖥️ Hệ thống công ty bị sập nghiêm trọng — toàn bộ công việc bị đình trệ.",
        "penalty_hours": 24,
        "chance": 0.10,
    },
    {
        "key": "legal_problem",
        "text": "⚖️ Công ty gặp vấn đề pháp lý — hoạt động bị điều tra và tạm dừng.",
        "penalty_hours": 60,
        "chance": 0.04,
    },
    {
        "key": "strike",
        "text": "📢 Nhân viên đình công — công ty đóng cửa tạm thời để giải quyết tranh chấp.",
        "penalty_hours": 30,
        "chance": 0.07,
    },
    {
        "key": "market_crash",
        "text": "📉 Thị trường lao dốc — công ty giảm tốc độ hoạt động và đóng băng dự án.",
        "penalty_hours": 40,
        "chance": 0.06,
    },
    {
        "key": "data_breach",
        "text": "🔓 Công ty bị rò rỉ dữ liệu — mọi hoạt động bị kiểm tra bảo mật.",
        "penalty_hours": 18,
        "chance": 0.12,
    },
    {
        "key": "equipment_failure",
        "text": "🔧 Thiết bị quan trọng bị hỏng — bạn không thể tiếp tục công việc bình thường.",
        "penalty_hours": 12,
        "chance": 0.15,
    },
    {
        "key": "bad_manager",
        "text": "😡 Quản lý mới quá khắt khe — hiệu suất làm việc giảm mạnh.",
        "penalty_hours": 20,
        "chance": 0.10,
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