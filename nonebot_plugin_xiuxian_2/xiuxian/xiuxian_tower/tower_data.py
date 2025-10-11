import json
import os
from pathlib import Path
from datetime import datetime
from ..xiuxian_utils.xiuxian2_handle import XiuxianDateManage

PLAYERSDATA = Path() / "data" / "xiuxian" / "players"
TOWER_RANK_PATH = Path(__file__).parent / "tower_rank.json"
TOWER_CONFIG_PATH = Path(__file__).parent / "tower_config.json"
sql_message = XiuxianDateManage()

DEFAULT_CONFIG = {
    "体力消耗": {
        "单层爬塔": 5,
        "连续爬塔": 20
    },
    "积分奖励": {
        "每层基础": 100,
        "每10层额外": 500
    },
    "灵石奖励": {
        "每层基础": 1000000,
        "每10层额外": 5000000
    },
    "修为奖励": {
        "每10层": 0.001
    },
    "商店商品": {
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
    },
    "重置时间": {
        "day_of_week": "mon",  # 每周一
        "hour": 0,
        "minute": 0
    }
}

class TowerData:
    def __init__(self):
        self.config = self.get_tower_config()
    
    def get_tower_config(self):
        """加载通天塔配置"""
        try:
            if not TOWER_CONFIG_PATH.exists():
                with open(TOWER_CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
                return DEFAULT_CONFIG
            
            with open(TOWER_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # 确保所有配置项都存在
            for key in DEFAULT_CONFIG:
                if key not in config:
                    config[key] = DEFAULT_CONFIG[key]
            
            return config
        except Exception as e:
            print(f"加载通天塔配置失败: {e}")
            return DEFAULT_CONFIG
    
    def _check_reset(self, last_reset_str):
        """检查是否需要重置(每周一)"""
        if not last_reset_str:
            return True
            
        last_reset = datetime.strptime(last_reset_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        
        # 检查是否是新的周(周一0点后)
        return (now.isocalendar()[1] > last_reset.isocalendar()[1] or  # 周数不同
                now.year > last_reset.year)  # 或跨年

    def reset_all_floors(self):
        """重置所有用户的通天塔层数"""
        reset_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for user_file in PLAYERSDATA.glob("*/tower_info.json"):
            with open(user_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 保留历史最高层数，只重置当前层数
            data["current_floor"] = 0
            data["last_reset"] = reset_time  # 使用统一的重置时间
            
            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

    def get_user_tower_info(self, user_id):
        """获取用户通天塔信息"""
        user_id = str(user_id)
        file_path = PLAYERSDATA / user_id / "tower_info.json"
        
        default_data = {
            "current_floor": 0,  # 当前层数
            "max_floor": 0,      # 历史最高层数
            "score": 0,          # 总积分
            "last_reset": None   # 上次重置时间
        }
        
        if not file_path.exists():
            os.makedirs(file_path.parent, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_data, f, ensure_ascii=False, indent=4)
            return default_data
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 检查是否需要重置(每周一)
        if self._check_reset(data.get("last_reset")):
            data["current_floor"] = 0
            data["last_reset"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_user_tower_info(user_id, data)
        
        # 确保所有字段都存在
        for key in default_data:
            if key not in data:
                data[key] = default_data[key]
        
        return data
    
    def save_user_tower_info(self, user_id, data):
        """保存用户通天塔信息"""
        user_id = str(user_id)
        file_path = PLAYERSDATA / user_id / "tower_info.json"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def update_tower_rank(self, user_id, user_name, floor):
        """更新通天塔排行榜"""
        rank_data = self._load_rank_data()
        
        # 更新或添加用户记录
        rank_data[str(user_id)] = {
            "name": user_name,
            "floor": floor,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存排行榜
        with open(TOWER_RANK_PATH, "w", encoding="utf-8") as f:
            json.dump(rank_data, f, ensure_ascii=False, indent=4)
    
    def get_tower_rank(self, limit=50):
        """获取通天塔排行榜"""
        rank_data = self._load_rank_data()
        
        # 按层数降序排序
        sorted_rank = sorted(
            rank_data.items(),
            key=lambda x: x[1]["floor"],
            reverse=True
        )[:limit]
        
        return sorted_rank
    
    def _load_rank_data(self):
        """加载排行榜数据"""
        if not TOWER_RANK_PATH.exists():
            return {}
        
        with open(TOWER_RANK_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    
    def get_weekly_purchases(self, user_id, item_id):
        """获取用户本周已购买某商品的数量"""
        user_id = str(user_id)
        file_path = PLAYERSDATA / user_id / "tower_purchases.json"
        
        if not file_path.exists():
            # 初始化文件并设置重置日期
            self._init_purchase_file(user_id)
            return 0
        
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                # 检查是否需要重置
                if "_last_reset" in data:
                    last_reset = datetime.strptime(data["_last_reset"], "%Y-%m-%d")
                    current_week = datetime.now().isocalendar()[1]
                    last_week = last_reset.isocalendar()[1]
                    current_year = datetime.now().year
                    last_year = last_reset.year
                    
                    if current_week != last_week or current_year != last_year:
                        # 重置购买记录
                        self._init_purchase_file(user_id)
                        return 0
                else:
                    # 没有重置日期，初始化
                    self._init_purchase_file(user_id)
                    return 0
                    
                return data.get(str(item_id), 0)
            except:
                # 文件损坏，重新初始化
                self._init_purchase_file(user_id)
                return 0

    def _init_purchase_file(self, user_id):
        """初始化购买记录文件"""
        user_id = str(user_id)
        file_path = PLAYERSDATA / user_id / "tower_purchases.json"
        
        data = {
            "_last_reset": datetime.now().strftime("%Y-%m-%d")
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def update_weekly_purchase(self, user_id, item_id, quantity):
        """更新用户本周购买某商品的数量"""
        user_id = str(user_id)
        file_path = PLAYERSDATA / user_id / "tower_purchases.json"
        
        data = {}
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except:
                    pass
        
        # 确保有重置日期
        if "_last_reset" not in data:
            data["_last_reset"] = datetime.now().strftime("%Y-%m-%d")
        
        current = data.get(str(item_id), 0)
        data[str(item_id)] = current + quantity
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

tower_data = TowerData()
