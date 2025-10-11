try:
    import ujson as json
except ImportError:
    import json
import os
from pathlib import Path

configkey = ["Boss灵石", "Boss名字", "Boss倍率", "Boss生成时间参数", 'open', "世界积分商品"]
CONFIG = {
    "open": {
        "000000": {}
            },
    "Boss灵石": {
        '感气境': [10000000, 15000000, 20000000],
        '练气境': [10000000, 15000000, 20000000],
        '筑基境': [10000000, 15000000, 20000000],
        '结丹境': [10000000, 15000000, 20000000],
        '金丹境': [10000000, 15000000, 20000000],
        '元神境': [10000000, 15000000, 20000000],
        '化神境': [20000000, 25000000, 30000000],
        '炼神境': [20000000, 25000000, 30000000],
        '返虚境': [20000000, 25000000, 30000000],
        '大乘境': [20000000, 25000000, 30000000],
        '虚道境': [20000000, 25000000, 30000000],
        '斩我境': [20000000, 25000000, 30000000],
        '遁一境': [30000000, 35000000, 40000000],
        '至尊境': [30000000, 35000000, 40000000],
        '微光境': [40000000, 45000000, 50000000],
        '星芒境': [40000000, 45000000, 50000000],
        '月华境': [45000000, 50000000, 55000000],
        '耀日境': [45000000, 50000000, 55000000],
        '祭道境': [50000000, 55000000, 60000000],
        '自在境': [50000000, 55000000, 60000000],
        '破虚境': [60000000, 65000000, 70000000],
        '无界境': [60000000, 65000000, 70000000],
        '混元境': [60000000, 65000000, 70000000],
        '造化境': [60000000, 65000000, 70000000],
        '永恒境': [60000000, 65000000, 70000000]
    },
    "Boss名字": [
        "九寒",
        "精卫",
        "少姜",
        "陵光",
        "莫女",
        "术方",
        "卫起",
        "血枫",
        "以向",
        "砂鲛",
        "鲲鹏",
        "天龙",
        "莉莉丝",
        "霍德尔",
        "历飞雨",
        "神风王",
        "衣以候",
        "金凰儿",
        "元磁道人",
        "外道贩卖鬼",
        "散发着威压的尸体"
        ],  # 生成的Boss名字，自行修改
    "讨伐世界Boss体力消耗": 10,
    "Boss倍率": {
        # Boss属性：大境界平均修为是基础数值，气血：300倍，真元：10倍，攻击力：0.5倍
        # 作为参考：人物的属性，修为是基础数值，气血：0.5倍，真元：1倍，攻击力：0.1倍
        "气血": 300,
        "真元": 10,
        "攻击": 0.5
    },
    "Boss生成时间参数": {  # Boss生成的时间，2个不可全为0
        "hours": 0,
        "minutes": 45
    },
    "世界积分商品": {
        "1999": {
            "name": "渡厄丹",
            "cost": 1000,
            "weekly_limit": 10
        },
        "4003": {
            "name": "陨铁炉",
            "cost": 5000,
            "weekly_limit": 1
        },
        "4002": {
            "name": "雕花紫铜炉",
            "cost": 25000,
            "weekly_limit": 1
        },
        "4001": {
            "name": "寒铁铸心炉",
            "cost": 100000,
            "weekly_limit": 1
        },
        "2500": {
            "name": "一级聚灵旗",
            "cost": 5000,
            "weekly_limit": 1
        },
        "2501": {
            "name": "二级聚灵旗",
            "cost": 10000,
            "weekly_limit": 1
        },
        "2502": {
            "name": "三级聚灵旗",
            "cost": 20000,
            "weekly_limit": 1
        },
        "2503": {
            "name": "四级聚灵旗",
            "cost": 40000,
            "weekly_limit": 1
        },
        "2504": {
            "name": "仙级聚灵旗",
            "cost": 80000,
            "weekly_limit": 1
        },
        "2505": {
            "name": "无上聚灵旗",
            "cost": 160000,
            "weekly_limit": 1
        },
        "7085": {
            "name": "冲天槊槊",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "8931": {
            "name": "苍寰变",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "9937": {
            "name": "弑仙魔典",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "10402": {
            "name": "真神威录",
            "cost": 700000,
            "weekly_limit": 1
        },
        "10403": {
            "name": "太乙剑诀",
            "cost": 1000000,
            "weekly_limit": 1
        },
        "10411": {
            "name": "真龙九变",
            "cost": 1200000,
            "weekly_limit": 1
        },
        "20004": {
            "name": "蕴灵石",
            "cost": 10000,
            "weekly_limit": 10
        },
        "20003": {
            "name": "神圣石",
            "cost": 50000,
            "weekly_limit": 3
        },
        "20002": {
            "name": "化道石",
            "cost": 200000,
            "weekly_limit": 1
        },
        "20005": {
            "name": "祈愿石",
            "cost": 1000,
            "weekly_limit": 10
        },
        "15357": {
            "name": "八九玄功",
            "cost": 100000,
            "weekly_limit": 1
        },
        "9935": {
            "name": "暗渊灭世功",
            "cost": 100000,
            "weekly_limit": 1
        },
        "9940": {
            "name": "化功大法",
            "cost": 100000,
            "weekly_limit": 1
        },
        "10405": {
            "name": "醉仙",
            "cost": 50000,
            "weekly_limit": 1
        },
        "10410": {
            "name": "劫破",
            "cost": 1000000,
            "weekly_limit": 1
        },
        "10412": {
            "name": "无极·靖天",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "8933": {
            "name": "冥河鬼镰·千慄慄葬世",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "8934": {
            "name": "血影碎空·胧剑劫",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "8935": {
            "name": "剑御九天·万剑归墟",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "8936": {
            "name": "华光·万影噬空",
            "cost": 2000000,
            "weekly_limit": 1
        },
        "20011": {
            "name": "易名符",
            "cost": 10000,
            "weekly_limit": 1
        },
        "20006": {
            "name": "福缘石",
            "cost": 5000,
            "weekly_limit": 1
        }
    }
}


CONFIGJSONPATH = Path(__file__).parent
FILEPATH = CONFIGJSONPATH / 'config.json'

def get_boss_config():
    """加载配置，失败时返回默认配置但不覆盖文件"""
    if not os.path.exists(FILEPATH):
        # 如果文件不存在，保存默认配置
        savef_boss(CONFIG)
        return CONFIG
    config = readf()
    # 确保所有键存在
    for key in configkey:
        if key not in config:
            config[key] = CONFIG[key]
    return config

def readf():
    """读取配置文件"""
    try:
        with open(FILEPATH, "r", encoding="UTF-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"警告: 读取 {FILEPATH} 失败: {e}")
        return CONFIG

def savef_boss(data):
    """保存配置"""
    try:
        # 确保目录存在
        os.makedirs(CONFIGJSONPATH, exist_ok=True)
        with open(FILEPATH, "w", encoding="UTF-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=3)
        return True
    except Exception as e:
        print(f"错误: 保存 {FILEPATH} 失败: {e}")
        return False