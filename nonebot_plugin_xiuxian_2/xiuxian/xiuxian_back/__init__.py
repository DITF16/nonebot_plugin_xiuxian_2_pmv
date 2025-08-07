import asyncio
import random
import re
import os
import json
from pathlib import Path
from datetime import datetime
from nonebot import on_command, require, on_fullmatch
from nonebot.adapters.onebot.v11 import (
    Bot,
    GROUP,
    Message,
    GroupMessageEvent,
    PrivateMessageEvent,
    MessageSegment,
    GROUP_ADMIN,
    GROUP_OWNER,
    ActionFailed
)
from ..xiuxian_utils.lay_out import assign_bot, assign_bot_group, Cooldown, CooldownIsolateLevel
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from .back_util import (
    get_user_main_back_msg, get_user_yaocai_back_msg, get_user_danyao_back_msg, check_equipment_can_use,
    get_use_equipment_sql, get_shop_data, save_shop,
    get_item_msg, get_item_msg_rank, check_use_elixir,
    get_use_jlq_msg, get_no_use_equipment_sql
)
from .backconfig import get_auction_config, savef_auction, remove_auction_item
from ..xiuxian_utils.item_json import Items
from ..xiuxian_utils.utils import (
    check_user, get_msg_pic, 
    send_msg_handler, CommandObjectID,
    Txt2Img, number_to, handle_send, handle_pagination
)
from ..xiuxian_utils.xiuxian2_handle import (
    XiuxianDateManage, get_weapon_info_msg, get_armor_info_msg,
    get_sec_msg, get_main_info_msg, get_sub_info_msg, UserBuffDate
)
from ..xiuxian_config import XiuConfig, convert_rank

items = Items()
config = get_auction_config()
groups = config['open']  # list，群交流会使用
auction = {}
AUCTIONSLEEPTIME = 120  # 拍卖初始等待时间（秒）
cache_help = {}
auction_offer_flag = False  # 拍卖标志
AUCTIONOFFERSLEEPTIME = 30  # 每次拍卖增加拍卖剩余的时间（秒）
auction_offer_time_count = 0  # 计算剩余时间
auction_offer_all_count = 0  # 控制线程等待时间
auction_time_config = config['拍卖会定时参数'] # 定时配置
sql_message = XiuxianDateManage()  # sql类
# 定时任务
set_auction_by_scheduler = require("nonebot_plugin_apscheduler").scheduler
reset_day_num_scheduler = require("nonebot_plugin_apscheduler").scheduler

# 仙肆相关命令
xiuxian_shop_view = on_command("仙肆查看", priority=5, block=True)
xian_shop_added_by_admin = on_command("系统仙肆上架", priority=5, permission=SUPERUSER, block=True)
xian_shop_add = on_command("仙肆上架", priority=5, block=True)
xian_shop_remove = on_command("仙肆下架", priority=5, block=True)
xian_buy = on_command("仙肆购买", priority=5, block=True)
my_xian_shop = on_command("我的仙肆", priority=5, block=True)
xian_shop_remove_by_admin = on_command("系统仙肆下架", priority=5, permission=SUPERUSER, block=True)

# 坊市相关命令
shop_view = on_command("坊市查看", priority=5, permission=GROUP, block=True)
shop_added = on_command("坊市上架", priority=5, permission=GROUP, block=True)
shop_added_by_admin = on_command("系统坊市上架", priority=5, permission=SUPERUSER, block=True)
shop_remove = on_command("坊市下架", priority=5, permission=GROUP, block=True)
shop_remove_by_admin = on_command("系统坊市下架", priority=5, permission=SUPERUSER, block=True)
buy = on_command("坊市购买", priority=5, permission=GROUP, block=True)
my_shop = on_command("我的坊市", priority=5, permission=GROUP, block=True)
shop_off_all = on_fullmatch("清空坊市", priority=3, permission=SUPERUSER, block=True)

# 其他原有命令保持不变
check_item_effect = on_command("查看效果", aliases={"查看物品"}, priority=5, block=True)
goods_re_root = on_command("炼金", priority=6, block=True)
auction_view = on_command("拍卖品查看", aliases={"查看拍卖品"}, priority=8, permission=GROUP, block=True)
main_back = on_command('我的背包', aliases={'我的物品'}, priority=10, block=True)
yaocai_back = on_command('药材背包', priority=10, block=True)
danyao_back = on_command('丹药背包', priority=10, block=True)
use = on_command("使用", priority=15, block=True)
no_use_zb = on_command("换装", priority=5, block=True)
auction_added = on_command("提交拍卖品", aliases={"拍卖品提交"}, priority=10, permission=GROUP, block=True)
auction_withdraw = on_command("撤回拍卖品", aliases={"拍卖品撤回"}, priority=10, permission=GROUP, block=True)
set_auction = on_command("拍卖会", priority=4, permission=GROUP and (SUPERUSER | GROUP_ADMIN | GROUP_OWNER), block=True)
creat_auction = on_fullmatch("举行拍卖会", priority=5, permission=GROUP and SUPERUSER, block=True)
offer_auction = on_command("拍卖", priority=5, permission=GROUP, block=True)
back_help = on_command("背包帮助", aliases={"坊市帮助"}, priority=8, block=True)
xiuxian_sone = on_fullmatch("灵石", priority=4, block=True)
chakan_wupin = on_command("查看修仙界物品", priority=25, block=True)

__back_help__ = f"""
修仙交易系统帮助

【背包管理】
🔹 我的背包 [页码] - 查看背包物品
🔹 药材背包 [页码] - 查看药材类物品
🔹 丹药背包 [页码] - 查看丹药类物品
🔹 使用+物品名 [数量] - 使用物品
🔹 换装+装备名 - 卸下装备
🔹 炼金+物品名 [数量] - 将物品转化为灵石

【坊市交易】（群内）
🔸 坊市查看 [类型] [页码] - 查看群坊市
  ▶ 支持类型：技能|装备|丹药|药材
🔸 坊市上架 物品 金额 [数量] - 上架物品
  ▶ 最低金额50万灵石，手续费10-30%
🔸 坊市购买 编号 [数量] - 购买物品
🔸 坊市下架 编号 - 下架自己的物品

【仙肆交易】（全服）
🔸 仙肆查看 [类型] [页码] - 查看全服仙肆
🔸 仙肆上架 物品 金额 [数量] - 上架物品
🔸 仙肆购买 编号 [数量] - 购买物品
🔸 仙肆下架 编号 - 下架自己的物品

【拍卖会】
🎫 查看拍卖品 - 查看待拍卖物品
🎫 提交拍卖品 物品 底价 [数量] - 提交拍卖
🎫 拍卖+金额 - 参与竞拍
🎫 撤回拍卖品 编号 - 撤回自己的拍卖品

【其他功能】
🔍 查看效果+物品名 - 查看物品详情
📜 查看修仙界物品+类型 [页码] 
  ▶ 支持类型：功法|神通|丹药|法器|防具等
💎 灵石 - 查看当前灵石数量

【系统规则】
⏰ 每日{auction_time_config['hours']}点自动举行拍卖会
💰 手续费规则：
  - 500万以下：10%
  - 500-1000万：15% 
  - 1000-2000万：20%
  - 2000万以上：30%

输入具体指令查看详细用法，祝道友交易愉快！
""".strip()


# 重置丹药每日使用次数
@reset_day_num_scheduler.scheduled_job("cron", hour=0, minute=0, )
async def reset_day_num_scheduler_():
    sql_message.day_num_reset()
    logger.opt(colors=True).info(f"<green>每日丹药使用次数重置成功！</green>")


# 定时任务生成拍卖会
@set_auction_by_scheduler.scheduled_job("cron", hour=auction_time_config['hours'], minute=auction_time_config['minutes'])
async def set_auction_by_scheduler_():
    global auction, auction_offer_flag, auction_offer_all_count, auction_offer_time_count
    if groups:
        if auction:
            logger.opt(colors=True).info(f"<green>已存在一场拍卖会，已清除！</green>")
            auction = {}

    auction_items = []
    try:
        # 用户拍卖品
        user_auction_id_list = get_user_auction_id_list()
        for auction_id in user_auction_id_list:
            user_auction_info = get_user_auction_price_by_id(auction_id)
            auction_items.append((auction_id, user_auction_info['quantity'], user_auction_info['start_price'], True))

        # 系统拍卖品
        auction_id_list = get_auction_id_list()
        auction_count = random.randint(3, 8)  # 随机挑选系统拍卖品数量
        auction_ids = random.sample(auction_id_list, auction_count)
        for auction_id in auction_ids:
            item_info = items.get_data_by_item_id(auction_id)
            item_quantity = 1
            if item_info['type'] in ['神物', '丹药']:
                item_quantity = random.randint(1, 3) # 丹药的话随机挑1-3个
            auction_items.append((auction_id, item_quantity, get_auction_price_by_id(auction_id)['start_price'], False))
    except LookupError:
        logger.opt(colors=True).info("<red>获取不到拍卖物品的信息，请检查配置文件！</red>")
        return
    
    # 打乱拍卖品顺序
    random.shuffle(auction_items)
    
    logger.opt(colors=True).info("<red>野生的大世界定时拍卖会出现了！！！，请管理员在这个时候不要重启机器人</red>")
    msg = f"大世界定时拍卖会出现了！！！\n"
    msg = f"请各位道友稍作准备，拍卖即将开始...\n"
    msg += f"本场拍卖会共有{len(auction_items)}件物品，将依次拍卖，分别是：\n"
    for idx, (auction_id, item_quantity, start_price, is_user_auction) in enumerate(auction_items):
        item_name = items.get_data_by_item_id(auction_id)['name']
        if is_user_auction:
            owner_info = sql_message.get_user_info_with_id(get_user_auction_price_by_id(auction_id)['user_id'])
            owner_name = owner_info['user_name']
            msg += f"{idx + 1}号：{item_name}x{item_quantity}（由{owner_name}道友提供）\n"
        else:
            msg += f"{idx + 1}号：{item_name}x{item_quantity}（由拍卖场提供）\n"

    for gid in groups:
        bot = await assign_bot_group(group_id=gid)
        try:
            await handle_send(bot, event, msg)
        except ActionFailed:
            continue
    
    auction_results = []  # 拍卖结果
    for i, (auction_id, item_quantity, start_price, is_user_auction) in enumerate(auction_items):
        auction_info = items.get_data_by_item_id(auction_id)

        auction = {
            'id': auction_id,
            'user_id': 0,
            'now_price': start_price,
            'name': auction_info['name'],
            'type': auction_info['type'],
            'quantity': item_quantity,
            'start_time': datetime.now(),
            'group_id': 0
        }

        
        if i + 1 == len(auction_items):
            msg = f"最后一件拍卖品为：\n{get_auction_msg(auction_id)}\n"
        else:
            msg = f"第{i + 1}件拍卖品为：\n{get_auction_msg(auction_id)}\n"
        msg += f"\n底价为{start_price}，加价不少于{int(start_price * 0.05)}"
        msg += f"\n竞拍时间为:{AUCTIONSLEEPTIME}秒，请诸位道友发送 拍卖+金额 来进行拍卖吧！"

        if auction['quantity'] > 1:
            msg += f"\n注意：拍卖品共{auction['quantity']}件，最终价为{auction['quantity']}x成交价。\n"

        if i + 1 < len(auction_items):
            next_item_name = items.get_data_by_item_id(auction_items[i + 1][0])['name']
            msg += f"\n下一件拍卖品为：{next_item_name}，请心仪的道友提前开始准备吧！"

        for gid in groups:
            bot = await assign_bot_group(group_id=gid)
            try:
                await handle_send(bot, event, msg)
            except ActionFailed:
                continue

     
        remaining_time = AUCTIONSLEEPTIME # 第一轮定时
        while remaining_time > 0:
            await asyncio.sleep(10)
            remaining_time -= 10


        while auction_offer_flag:  # 有人拍卖
            if auction_offer_all_count == 0:
                auction_offer_flag = False
                break

            logger.opt(colors=True).info(f"<green>有人拍卖，本次等待时间：{auction_offer_all_count * AUCTIONOFFERSLEEPTIME}秒</green>")
            first_time = auction_offer_all_count * AUCTIONOFFERSLEEPTIME
            auction_offer_all_count = 0
            auction_offer_flag = False
            await asyncio.sleep(first_time)
            logger.opt(colors=True).info(f"<green>总计等待时间{auction_offer_time_count * AUCTIONOFFERSLEEPTIME}秒，当前拍卖标志：{auction_offer_flag}，本轮等待时间：{first_time}</green>")

        logger.opt(colors=True).info(f"<green>等待时间结束，总计等待时间{auction_offer_time_count * AUCTIONOFFERSLEEPTIME}秒</green>")
        if auction['user_id'] == 0:
            msg = f"很可惜，{auction['name']}流拍了\n"
            if i + 1 == len(auction_items):
                msg += f"本场拍卖会到此结束，开始整理拍卖会结果，感谢各位道友参与！"
                
            for gid in groups:
                bot = await assign_bot_group(group_id=gid)
                try:
                    await handle_send(bot, event, msg)
                except ActionFailed:  # 发送群消息失败
                    continue
            auction_results.append((auction_id, None, auction['group_id'], auction_info['type'], auction['now_price'], auction['quantity']))
            auction = {}
            continue
        
        user_info = sql_message.get_user_info_with_id(auction['user_id'])
        msg = f"(拍卖锤落下)！！！\n"
        msg += f"恭喜来自群{auction['group_id']}的{user_info['user_name']}道友成功拍下：{auction['type']}-{auction['name']}x{auction['quantity']}，将在拍卖会结算后送到您手中。\n"
        if i + 1 == len(auction_items):
            msg += f"本场拍卖会到此结束，开始整理拍卖会结果，感谢各位道友参与！"

        auction_results.append((auction_id, user_info['user_id'], auction['group_id'], 
                                auction_info['type'], auction['now_price'], auction['quantity']))
        auction = {}
        auction_offer_time_count = 0
        for gid in groups:

            bot = await assign_bot_group(group_id=gid)
            try:
                await handle_send(bot, event, msg)
            except ActionFailed:
                continue

        await asyncio.sleep(random.randint(5, 30))

    # 拍卖会结算
    logger.opt(colors=True).info(f"<green>野生的大世界定时拍卖会结束了！！！</green>")
    end_msg = f"本场拍卖会结束！感谢各位道友的参与。\n拍卖结果整理如下：\n"
    for idx, (auction_id, user_id, group_id, item_type, final_price, quantity) in enumerate(auction_results):
        item_name = items.get_data_by_item_id(auction_id)['name']
        final_user_info = sql_message.get_user_info_with_id(user_id)
        if user_id:
            if final_user_info['stone'] < (int(final_price) * quantity):
                end_msg += f"{idx + 1}号拍卖品：{item_name}x{quantity} - 道友{final_user_info['user_name']}的灵石不足，流拍了\n"
            else:
                sql_message.update_ls(user_id, int(final_price) * quantity, 2)
                sql_message.send_back(user_id, auction_id, item_name, item_type, quantity)
                end_msg += f"{idx + 1}号拍卖品：{item_name}x{quantity}由群{group_id}的{final_user_info['user_name']}道友成功拍下\n"

            user_auction_info = get_user_auction_price_by_id(auction_id)
            if user_auction_info:
                seller_id = user_auction_info['user_id']
                auction_earnings = int(final_price) * quantity * 0.7 # 收个手续费
                sql_message.update_ls(seller_id, auction_earnings, 1)

            remove_auction_item(auction_id)

            auction = {}
            auction_offer_time_count = 0
        else:
            end_msg += f"{idx + 1}号拍卖品：{item_name}x{quantity} - 流拍了\n"

    for gid in groups:
        bot = await assign_bot_group(group_id=gid)
        try:
            await handle_send(bot, event, end_msg)
        except ActionFailed:  # 发送群消息失败
            continue

    return


@check_item_effect.handle(parameterless=[Cooldown(at_sender=False)])
async def check_item_effect_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """查看物品效果，支持物品名或ID"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)

    # 检查用户是否已注册修仙
    is_user, user_info, msg = check_user(event)
    if not is_user:
        await handle_send(bot, event, msg)
        await check_item_effect.finish()

    # 获取用户输入的物品名或ID
    input_str = args.extract_plain_text().strip()
    if not input_str:
        msg = "请输入物品名称或ID！\n例如：查看效果 渡厄丹 或 查看效果 1999"
        await handle_send(bot, event, msg)
        await check_item_effect.finish()

    # 判断输入是ID还是名称
    goods_id = None
    if input_str.isdigit():  # 如果是纯数字，视为ID
        goods_id = int(input_str)
        item_info = items.get_data_by_item_id(goods_id)
        if not item_info:
            msg = f"ID {goods_id} 对应的物品不存在，请检查输入！"
            await handle_send(bot, event, msg)
            await check_item_effect.finish()
    else:  # 视为物品名称
        for k, v in items.items.items():
            if input_str == v['name']:
                goods_id = k
                break
        if goods_id is None:
            msg = f"物品 {input_str} 不存在，请检查名称是否正确！"
            await handle_send(bot, event, msg)
            await check_item_effect.finish()
    item_msg = get_item_msg(goods_id)
    if goods_id == 15053 or input_str == "补偿":
        await check_item_effect.finish()
    # 构造返回消息
    msg = f"\nID：{goods_id}\n{item_msg}"
    await handle_send(bot, event, msg)
    await check_item_effect.finish()
    
@back_help.handle(parameterless=[Cooldown(at_sender=False)])
async def back_help_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, session_id: int = CommandObjectID()):
    """背包帮助"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)

    # 检查用户是否已注册修仙
    is_user, user_info, msg = check_user(event)
    if not is_user:
        await handle_send(bot, event, msg)
        await back_help.finish()
    else:
        msg = __back_help__
        await handle_send(bot, event, msg)
        await back_help.finish()


@xiuxian_sone.handle(parameterless=[Cooldown(at_sender=False)])
async def xiuxian_sone_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    """我的灵石信息"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await xiuxian_sone.finish()
    msg = f"当前灵石：{user_info['stone']}({number_to(user_info['stone'])})"
    await handle_send(bot, event, msg)
    await xiuxian_sone.finish()

# 仙肆数据结构
XIANSHI_DATA = {
    "system_items": {},  # 系统物品 {id: {item_info}}
    "user_items": {},    # 用户物品 {id: {item_info}}
    "next_system_id": 1, # 系统物品ID计数器
}

# 仙肆最低价格限制
MIN_PRICE = 500000  # 50万灵石

TRADE_DATA_PATH = Path(__file__).parent / "trade_data"
XIANSHI_DATA_PATH = TRADE_DATA_PATH / "xianshi.json"

# 确保目录存在
TRADE_DATA_PATH.mkdir(parents=True, exist_ok=True)

def get_xianshi_data():
    """获取仙肆数据"""
    try:
        if XIANSHI_DATA_PATH.exists():
            with open(XIANSHI_DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"读取仙肆数据失败: {e}")
    return {"system_items": {}, "user_items": {}, "next_system_id": 1}

def save_xianshi_data(data):
    """保存仙肆数据"""
    try:
        with open(XIANSHI_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"保存仙肆数据失败: {e}")
        return False

def generate_xianshi_id():
    """生成6-10位不重复的仙肆ID"""
    data = get_xianshi_data()
    while True:
        xianshi_id = str(random.randint(100000, 9999999999))
        if xianshi_id not in data["system_items"] and xianshi_id not in data["user_items"]:
            return xianshi_id

FANGSHI_DATA_PATH = TRADE_DATA_PATH / "fangshi_data"

# 确保目录存在
FANGSHI_DATA_PATH.mkdir(parents=True, exist_ok=True)

def get_fangshi_data(group_id):
    """获取坊市数据"""
    filepath = FANGSHI_DATA_PATH / f"fangshi_{group_id}.json"
    try:
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"读取坊市数据失败: {e}")
    return {"system_items": {}, "user_items": {}, "next_system_id": 1}

def save_fangshi_data(group_id, data):
    """保存坊市数据"""
    filepath = FANGSHI_DATA_PATH / f"fangshi_{group_id}.json"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"保存坊市数据失败: {e}")
        return False

def get_xianshi_min_price(goods_name):
    """获取仙肆中该物品的最低价格"""
    data = get_xianshi_data()
    min_price = None
    
    # 检查系统物品
    for item in data["system_items"].values():
        if item["goods_name"] == goods_name:
            if min_price is None or item["price"] < min_price:
                min_price = item["price"]
    
    # 检查用户物品
    for item in data["user_items"].values():
        if item["goods_name"] == goods_name:
            if min_price is None or item["price"] < min_price:
                min_price = item["price"]
    
    return min_price
    
@xian_shop_add.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def xian_shop_add_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """仙肆上架"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
    
    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    
    if len(args) < 2:
        msg = "请输入正确指令！例如：仙肆上架 物品 价格 [数量]"
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
    
    goods_name = args[0]
    try:
        price = max(int(args[1]), MIN_PRICE)  # 确保不低于最低价格
        quantity = int(args[2]) if len(args) > 2 else 1
    except ValueError:
        msg = "请输入有效的价格和数量！"
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
    
    MAX_QUANTITY = 10  # 最大上架数量

    if quantity > MAX_QUANTITY:
        msg = f"单次上架数量不能超过{MAX_QUANTITY}个！"
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
        
    # 检查背包是否有足够物品
    back_msg = sql_message.get_back_msg(user_id)
    if not back_msg:
        msg = "道友的背包空空如也！"
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
    
    goods_info = None
    for item in back_msg:
        if item['goods_name'] == goods_name:
            goods_info = item
            break
    
    if not goods_info:
        msg = f"请检查该道具 {goods_name} 是否在背包内！"
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
    
    if quantity > goods_info['goods_num'] - goods_info['bind_num']:
        msg = f"道友的 {goods_name} 数量不足（需要 {quantity} 个，拥有 {goods_info['goods_num']} 个，其中 {goods_info['bind_num']} 个是绑定的）"
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
    
    # 计算手续费（按总价计算一次）
    total_price = price * quantity
    if total_price <= 5000000:
        fee_rate = 0.1
    elif total_price <= 10000000:
        fee_rate = 0.15
    elif total_price <= 20000000:
        fee_rate = 0.2
    else:
        fee_rate = 0.3
    
    fee = int(total_price * fee_rate)
    if user_info['stone'] < fee:
        msg = f"道友的灵石不足支付手续费（需要 {fee} 枚灵石）"
        await handle_send(bot, event, msg)
        await xian_shop_add.finish()
    
    # 扣除手续费和物品
    sql_message.update_ls(user_id, fee, 2)
    sql_message.update_back_j(user_id, goods_info['goods_id'], num=quantity)
    
    # 保存到仙肆数据（每个物品单独存储）
    data = get_xianshi_data()
    success_count = 0
    
    for _ in range(quantity):
        xianshi_id = generate_xianshi_id()
        data["user_items"][xianshi_id] = {
            "id": xianshi_id,
            "goods_id": goods_info['goods_id'],
            "goods_name": goods_name,
            "goods_type": goods_info['goods_type'],
            "price": price,
            "quantity": 1,
            "user_id": user_id,
            "user_name": user_info['user_name'],
            "desc": get_item_msg(goods_info['goods_id'])
        }
        success_count += 1
    
    save_xianshi_data(data)
    
    msg = f"成功上架 {goods_name} {success_count} 件到仙肆！\n单价: {price} 灵石\n总价: {total_price} 灵石\n手续费: {fee} 灵石"
    await handle_send(bot, event, msg)
    await xian_shop_add.finish()

@xian_shop_remove.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def xian_shop_remove_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """仙肆下架
    用法: 
    1. 仙肆下架 物品名 - 下架该物品价格最低的一个
    2. 仙肆下架 物品名 数量 - 按价格从低到高下架指定数量(最多10个)
    """
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await xian_shop_remove.finish()
    
    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    
    if not args:
        msg = "请输入要下架的物品名称！\n例如：仙肆下架 生骨丹 或 仙肆下架 生骨丹 3"
        await handle_send(bot, event, msg)
        await xian_shop_remove.finish()
    
    goods_name = args[0]
    quantity = 1  # 默认下架1个
    
    # 解析数量参数
    if len(args) > 1:
        try:
            quantity = min(int(args[1]), 10)  # 限制最多下架10个
            if quantity <= 0:
                msg = "下架数量必须大于0！"
                await handle_send(bot, event, msg)
                await xian_shop_remove.finish()
        except ValueError:
            msg = "请输入有效的数量！"
            await handle_send(bot, event, msg)
            await xian_shop_remove.finish()
    
    data = get_xianshi_data()
    removed_items = []
    remaining_quantity = quantity
    
    # 获取用户所有该物品的上架记录，按价格排序
    user_items = [
        item for item in data["user_items"].values() 
        if str(item["user_id"]) == str(user_id) 
        and item["goods_name"] == goods_name
    ]
    user_items.sort(key=lambda x: x["price"])  # 按价格从低到高排序
    
    if not user_items:
        msg = f"未找到您上架的 {goods_name} 物品！"
        await handle_send(bot, event, msg)
        await xian_shop_remove.finish()
    
    # 计算总可用数量
    total_available = sum(item["quantity"] for item in user_items)
    if quantity > total_available:
        msg = f"您只有 {total_available} 个 {goods_name} 在仙肆中，无法下架 {quantity} 个！"
        await handle_send(bot, event, msg)
        await xian_shop_remove.finish()
    
    # 开始下架
    for item in user_items:
        if remaining_quantity <= 0:
            break
            
        item_id = item["id"]
        item_quantity = item["quantity"]
        
        # 计算本次能下架的数量
        remove_num = min(item_quantity, remaining_quantity)
        
        # 退回物品
        sql_message.send_back(
            user_id, 
            item["goods_id"], 
            item["goods_name"], 
            item["goods_type"], 
            remove_num
        )
        
        # 记录下架信息
        removed_items.append({
            "name": item["goods_name"],
            "price": item["price"],
            "quantity": remove_num
        })
        
        # 更新物品数量或删除物品
        if item_quantity == remove_num:
            del data["user_items"][item_id]
        else:
            data["user_items"][item_id]["quantity"] -= remove_num
        
        remaining_quantity -= remove_num
    
    # 保存数据
    save_xianshi_data(data)
    
    # 构造返回消息
    if removed_items:
        msg = "成功下架以下物品：\n"
        for item in removed_items:
            msg += f"{item['name']} {item['price']}灵石 x{item['quantity']}\n"
        
        if remaining_quantity > 0:
            msg += f"\n注意：实际下架了 {quantity - remaining_quantity} 个，未达到请求数量 {quantity} 个"
    else:
        msg = "没有物品被下架！"
    
    await handle_send(bot, event, msg)
    await xian_shop_remove.finish()

@xiuxian_shop_view.handle(parameterless=[Cooldown(at_sender=False)])
async def xiuxian_shop_view_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """仙肆查看"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await xiuxian_shop_view.finish()
    
    # 解析参数
    args_str = args.extract_plain_text().strip()
    parts = args_str.split()
    
    item_type = None
    current_page = 1
    
    if parts:
        # 尝试解析类型和页码
        for t in ["装备", "技能", "丹药", "药材"]:
            if parts[0].startswith(t):
                item_type = t
                if len(parts[0]) > len(t) and parts[0][len(t):].isdigit():
                    current_page = int(parts[0][len(t):])
                elif len(parts) > 1 and parts[1].isdigit():
                    current_page = int(parts[1])
                break
    
    data = get_xianshi_data()
    items_list = []
    for item in data["system_items"].values():
        if not item_type or item["goods_type"] == item_type:
            items_list.append({
                "id": item["id"],
                "name": item["goods_name"],
                "price": item["price"],
                "quantity": item.get("quantity", "无限"),
                "is_system": True
            })

    # 添加用户物品（去重，只保留最低价格）
    user_items_map = {}
    for item in data["user_items"].values():
        if not item_type or item["goods_type"] == item_type:
            key = item["goods_name"]
            if key not in user_items_map or item["price"] < user_items_map[key]["price"]:
                user_items_map[key] = {
                    "id": item["id"],
                    "name": item["goods_name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                    "is_system": False
                }

    # 合并系统物品和用户物品
    items_list.extend(user_items_map.values())

    # 检查分类下是否有物品
    if not items_list:
        if item_type:
            msg = f"仙肆中暂无{item_type}类物品！"
        else:
            msg = "仙肆目前空空如也！"
        await handle_send(bot, event, msg)
        await xiuxian_shop_view.finish()
    
    # 分页处理
    per_page = 10
    total_pages = (len(items_list) + per_page - 1) // per_page
    current_page = max(1, min(current_page, total_pages))
    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    paged_items = items_list[start_idx:end_idx]
    
    # 构建消息 - 修改显示格式
    msg_list = []
    if item_type:
        msg_list.append(f"☆------仙肆 {item_type} 物品------☆")
    else:
        msg_list.append("☆------仙肆所有物品------☆")
    
    for item in paged_items:
        if item["is_system"]:
            msg = f"{item['name']} {item['price']}灵石 ID:{item['id']}"
            if item["quantity"] != "无限":  # 系统物品显示数量或"无限"
                msg += f" 数量:{item['quantity']}"
            else:
                msg += " 数量:无限"
        else:
            msg = f"{item['name']} {item['price']}灵石 ID:{item['id']}"
            if item["quantity"] > 1:  # 用户物品数量大于1时显示
                msg += f" 数量:{item['quantity']}"
        msg_list.append(msg)
    
    msg_list.append(f"\n第 {current_page}/{total_pages} 页")
    if total_pages > 1:
        msg_list.append(f"输入 仙肆查看{item_type}{current_page + 1} 查看下一页")
    
    await send_msg_handler(bot, event, '仙肆查看', bot.self_id, msg_list)
    await xiuxian_shop_view.finish()

@my_xian_shop.handle(parameterless=[Cooldown(at_sender=False)])
async def my_xian_shop_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """我的仙肆"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await my_xian_shop.finish()
    
    # 获取页码
    try:
        current_page = int(args.extract_plain_text().strip())
    except:
        current_page = 1
    
    data = get_xianshi_data()
    user_items = []
    
    # 获取用户所有上架物品
    for item in data["user_items"].values():
        if str(item["user_id"]) == str(user_info["user_id"]):
            user_items.append(item)
    
    # 按物品名称和价格分组
    item_groups = {}
    for item in user_items:
        key = (item["goods_name"], item["price"])
        if key not in item_groups:
            item_groups[key] = 0
        item_groups[key] += item["quantity"]
        
    # 检查用户是否有上架物品
    if not user_items:
        msg = "您在仙肆中没有上架任何物品！"
        await handle_send(bot, event, msg)
        await my_xian_shop.finish()

    # 转换为消息列表
    msg_list = []
    for (name, price), quantity in item_groups.items():
        msg = f"{name} {price}灵石"
        if quantity > 1:
            msg += f" x{quantity}"
        msg_list.append(msg)
    
    # 分页处理
    per_page = 10
    total_pages = (len(msg_list) + per_page - 1) // per_page
    current_page = max(1, min(current_page, total_pages))
    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    paged_msgs = msg_list[start_idx:end_idx]
    
    # 构建最终消息
    final_msg = [f"☆------{user_info['user_name']}的仙肆物品------☆"]
    final_msg.extend(paged_msgs)
    final_msg.append(f"\n第 {current_page}/{total_pages} 页")
    
    await send_msg_handler(bot, event, '我的仙肆', bot.self_id, final_msg)
    await my_xian_shop.finish()

@xian_buy.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def xian_buy_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """仙肆购买"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await xian_buy.finish()
    
    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    
    if len(args) < 1:
        msg = "请输入要购买的仙肆ID！"
        await handle_send(bot, event, msg)
        await xian_buy.finish()
    
    xianshi_id = args[0]
    quantity = int(args[1]) if len(args) > 1 else 1
    
    # 获取仙肆数据
    data = get_xianshi_data()
    item = None
    
    # 查找物品
    if xianshi_id in data["system_items"]:
        item = data["system_items"][xianshi_id]
    elif xianshi_id in data["user_items"]:
        item = data["user_items"][xianshi_id]
    
    if not item:
        msg = f"未找到仙肆ID为 {xianshi_id} 的物品！"
        await handle_send(bot, event, msg)
        await xian_buy.finish()
    
    # 检查是否是自己的物品
    if "user_id" in item and str(item["user_id"]) == str(user_id):
        msg = "不能购买自己上架的物品！"
        await handle_send(bot, event, msg)
        await xian_buy.finish()
    
    # 检查库存
    if "quantity" in item:
        if isinstance(item["quantity"], str) and item["quantity"] == "无限":
            pass  # 无限数量无需检查
        elif item["quantity"] < quantity:
            msg = f"库存不足，只有 {item['quantity']} 个可用！"
            await handle_send(bot, event, msg)
            await xian_buy.finish()
    
    total_price = item["price"] * quantity
    
    # 检查灵石是否足够
    if user_info["stone"] < total_price:
        msg = f"灵石不足，需要 {total_price} 枚灵石！"
        await handle_send(bot, event, msg)
        await xian_buy.finish()
    
    try:
        # 扣除灵石
        sql_message.update_ls(user_id, total_price, 2)
        
        # 如果是用户物品，给卖家灵石
        if "user_id" in item:
            seller_id = item["user_id"]
            sql_message.update_ls(seller_id, total_price, 1)
        
        # 给买家物品
        sql_message.send_back(
            user_id,
            item["goods_id"],
            item["goods_name"],
            item["goods_type"],
            quantity
        )
        
        # 更新库存或删除物品
        if "quantity" in item:
            if isinstance(item["quantity"], str) and item["quantity"] == "无限":
                pass  # 无限数量无需处理
            else:
                item["quantity"] -= quantity
                if item["quantity"] <= 0:
                    if xianshi_id in data["system_items"]:
                        del data["system_items"][xianshi_id]
                    else:
                        del data["user_items"][xianshi_id]
        
        # 保存数据
        if not save_xianshi_data(data):
            raise Exception("保存仙肆数据失败")
        
        msg = f"成功购买 {item['goods_name']} x{quantity}！\n花费: {total_price} 灵石"
        await handle_send(bot, event, msg)
    except Exception as e:
        logger.error(f"仙肆购买出错: {e}")
        msg = "购买过程中出现错误，请稍后再试！"
        await handle_send(bot, event, msg)
    
    await xian_buy.finish()

@xian_shop_added_by_admin.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def xian_shop_added_by_admin_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """系统仙肆上架"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    args = args.extract_plain_text().split()
    
    if len(args) < 1:
        msg = "请输入正确指令！例如：系统仙肆上架 物品 [价格] [数量]"
        await handle_send(bot, event, msg)
        await xian_shop_added_by_admin.finish()
    
    goods_name = args[0]
    goods_id = None
    
    # 查找物品ID
    for k, v in items.items.items():
        if goods_name == v['name']:
            goods_id = k
            break
    
    if not goods_id:
        msg = f"未找到物品 {goods_name}！"
        await handle_send(bot, event, msg)
        await xian_shop_added_by_admin.finish()
    
    # 解析价格和数量
    try:
        price = int(args[1]) if len(args) > 1 else MIN_PRICE
        quantity = int(args[2]) if len(args) > 2 else 0  # 0表示无限
    except ValueError:
        msg = "请输入有效的价格和数量！"
        await handle_send(bot, event, msg)
        await xian_shop_added_by_admin.finish()
    
    price = max(price, MIN_PRICE)
    
    # 添加到系统仙肆
    data = get_xianshi_data()
    system_id = str(data["next_system_id"])
    data["next_system_id"] += 1
    
    data["system_items"][system_id] = {
        "id": system_id,
        "goods_id": goods_id,
        "goods_name": goods_name,
        "goods_type": items.get_data_by_item_id(goods_id)["type"],
        "price": price,
        "quantity": quantity if quantity > 0 else "无限",
        "desc": get_item_msg(goods_id)
    }
    
    save_xianshi_data(data)
    
    msg = f"系统成功上架 {goods_name} 到仙肆！\n价格: {price} 灵石\n"
    if quantity > 0:
        msg += f"数量: {quantity}"
    else:
        msg += "数量: 无限"
    msg += f"\n仙肆ID: {system_id}"
    
    await handle_send(bot, event, msg)
    await xian_shop_added_by_admin.finish()

@xian_shop_remove_by_admin.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def xian_shop_remove_by_admin_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """系统仙肆下架"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    arg = args.extract_plain_text().strip()
    
    if not arg:
        msg = "请输入要下架的仙肆ID或物品名称！"
        await handle_send(bot, event, msg)
        await xian_shop_remove_by_admin.finish()
    
    data = get_xianshi_data()
    removed_items = []
    
    if arg.isdigit():  # 按ID下架
        xianshi_id = arg
        if xianshi_id in data["system_items"]:
            removed_items.append(data["system_items"][xianshi_id])
            del data["system_items"][xianshi_id]
        elif xianshi_id in data["user_items"]:
            item = data["user_items"][xianshi_id]
            # 退回给玩家
            sql_message.send_back(
                item["user_id"],
                item["goods_id"],
                item["goods_name"],
                item["goods_type"],
                item["quantity"]
            )
            removed_items.append(item)
            del data["user_items"][xianshi_id]
        else:
            msg = f"未找到仙肆ID为 {xianshi_id} 的物品！"
            await handle_send(bot, event, msg)
            await xian_shop_remove_by_admin.finish()
    else:  # 按名称下架
        goods_name = arg
        # 先找系统物品
        system_items = [item for item in data["system_items"].values() 
                       if item["goods_name"] == goods_name]
        
        if system_items:
            for item in system_items:
                removed_items.append(item)
                del data["system_items"][item["id"]]
        else:
            # 找用户物品（按价格排序）
            user_items = [item for item in data["user_items"].values() 
                         if item["goods_name"] == goods_name]
            user_items.sort(key=lambda x: x["price"])
            
            if user_items:
                item = user_items[0]
                # 退回给玩家
                sql_message.send_back(
                    item["user_id"],
                    item["goods_id"],
                    item["goods_name"],
                    item["goods_type"],
                    item["quantity"]
                )
                removed_items.append(item)
                del data["user_items"][item["id"]]
            else:
                msg = f"未找到名称为 {goods_name} 的物品！"
                await handle_send(bot, event, msg)
                await xian_shop_remove_by_admin.finish()
    
    save_xianshi_data(data)
    
    if removed_items:
        msg = "成功下架以下物品：\n"
        for item in removed_items:
            if "user_id" in item:
                msg += f"用户物品: {item['goods_name']} x{item['quantity']} (价格: {item['price']})\n"
            else:
                msg += f"系统物品: {item['goods_name']} x{item.get('quantity', '无限')}\n"
    else:
        msg = "没有物品被下架！"
    
    await handle_send(bot, event, msg)
    await xian_shop_remove_by_admin.finish()

@shop_added.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def shop_added_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """坊市上架"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await shop_added.finish()
    
    group_id = str(event.group_id)
    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    
    if len(args) < 2:
        msg = "请输入正确指令！例如：坊市上架 物品 价格 [数量]"
        await handle_send(bot, event, msg)
        await shop_added.finish()
    
    goods_name = args[0]
    try:
        price = int(args[1])
        quantity = int(args[2]) if len(args) > 2 else 1
    except ValueError:
        msg = "请输入有效的价格和数量！"
        await handle_send(bot, event, msg)
        await shop_added.finish()
    
    MAX_QUANTITY = 10  # 最大上架数量

    if quantity > MAX_QUANTITY:
        msg = f"单次上架数量不能超过{MAX_QUANTITY}个！"
        await handle_send(bot, event, msg)
        await shop_added.finish()
        
    # 检查背包是否有足够物品
    back_msg = sql_message.get_back_msg(user_id)
    if not back_msg:
        msg = "道友的背包空空如也！"
        await handle_send(bot, event, msg)
        await shop_added.finish()
    
    goods_info = None
    for item in back_msg:
        if item['goods_name'] == goods_name:
            goods_info = item
            break
    
    if not goods_info:
        msg = f"请检查该道具 {goods_name} 是否在背包内！"
        await handle_send(bot, event, msg)
        await shop_added.finish()
    
    if quantity > goods_info['goods_num'] - goods_info['bind_num']:
        msg = f"道友的 {goods_name} 数量不足（需要 {quantity} 个，拥有 {goods_info['goods_num']} 个，其中 {goods_info['bind_num']} 个是绑定的）"
        await handle_send(bot, event, msg)
        await shop_added.finish()
    
    # 获取仙肆最低价格并设置价格限制
    xianshi_min_price = get_xianshi_min_price(goods_name)
    if xianshi_min_price is not None:
        min_price = max(MIN_PRICE, xianshi_min_price // 2)
        max_price = xianshi_min_price * 2
        if price < min_price or price > max_price:
            msg = f"该物品在仙肆的最低价格为 {xianshi_min_price}，坊市价格限制为 {min_price}-{max_price} 灵石！"
            await handle_send(bot, event, msg)
            await shop_added.finish()
    else:
        min_price = MIN_PRICE
        if price < min_price:
            msg = f"坊市最低价格为 {min_price} 灵石！"
            await handle_send(bot, event, msg)
            await shop_added.finish()
    
    # 计算手续费（按总价计算一次）
    total_price = price * quantity
    if total_price <= 5000000:
        fee_rate = 0.1
    elif total_price <= 10000000:
        fee_rate = 0.15
    elif total_price <= 20000000:
        fee_rate = 0.2
    else:
        fee_rate = 0.3
    
    fee = int(total_price * fee_rate)
    if user_info['stone'] < fee:
        msg = f"道友的灵石不足支付手续费（需要 {fee} 枚灵石）"
        await handle_send(bot, event, msg)
        await shop_added.finish()
    
    # 扣除手续费和物品
    sql_message.update_ls(user_id, fee, 2)
    sql_message.update_back_j(user_id, goods_info['goods_id'], num=quantity)
    
    # 添加到坊市数据（每个物品单独存储）
    data = get_fangshi_data(group_id)
    success_count = 0
    
    for _ in range(quantity):
        fangshi_id = str(len(data["user_items"]) + 1)
        data["user_items"][fangshi_id] = {
            "id": fangshi_id,
            "goods_id": goods_info['goods_id'],
            "goods_name": goods_name,
            "goods_type": goods_info['goods_type'],
            "price": price,
            "quantity": 1,  # 每个物品单独存储，数量为1
            "user_id": user_id,
            "user_name": user_info['user_name'],
            "desc": get_item_msg(goods_info['goods_id'])
        }
        success_count += 1
    
    save_fangshi_data(group_id, data)
    
    msg = f"成功上架 {goods_name} {success_count} 件到坊市！\n单价: {price} 灵石\n总价: {total_price} 灵石\n手续费: {fee} 灵石"
    await handle_send(bot, event, msg)
    await shop_added.finish()

@shop_remove.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def shop_remove_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """坊市下架
    用法: 
    1. 坊市下架 物品名 - 下架该物品价格最低的一个
    2. 坊市下架 物品名 数量 - 按价格从低到高下架指定数量(最多10个)
    """
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await shop_remove.finish()
    
    group_id = str(event.group_id)
    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    
    if not args:
        msg = "请输入要下架的物品名称！\n例如：坊市下架 生骨丹 或 坊市下架 生骨丹 3"
        await handle_send(bot, event, msg)
        await shop_remove.finish()
    
    goods_name = args[0]
    quantity = 1  # 默认下架1个
    
    # 解析数量参数
    if len(args) > 1:
        try:
            quantity = min(int(args[1]), 10)  # 限制最多下架10个
            if quantity <= 0:
                msg = "下架数量必须大于0！"
                await handle_send(bot, event, msg)
                await shop_remove.finish()
        except ValueError:
            msg = "请输入有效的数量！"
            await handle_send(bot, event, msg)
            await shop_remove.finish()
    
    data = get_fangshi_data(group_id)
    removed_items = []
    remaining_quantity = quantity
    
    # 获取用户所有该物品的上架记录，按价格排序
    user_items = [
        item for item in data["user_items"].values() 
        if str(item["user_id"]) == str(user_id) 
        and item["goods_name"] == goods_name
    ]
    user_items.sort(key=lambda x: x["price"])  # 按价格从低到高排序
    
    if not user_items:
        msg = f"未找到您上架的 {goods_name} 物品！"
        await handle_send(bot, event, msg)
        await shop_remove.finish()
    
    # 计算总可用数量
    total_available = sum(item["quantity"] for item in user_items)
    if quantity > total_available:
        msg = f"您只有 {total_available} 个 {goods_name} 在坊市中，无法下架 {quantity} 个！"
        await handle_send(bot, event, msg)
        await shop_remove.finish()
    
    # 开始下架
    for item in user_items:
        if remaining_quantity <= 0:
            break
            
        item_id = item["id"]
        item_quantity = item["quantity"]
        
        # 计算本次能下架的数量
        remove_num = min(item_quantity, remaining_quantity)
        
        # 退回物品
        sql_message.send_back(
            user_id, 
            item["goods_id"], 
            item["goods_name"], 
            item["goods_type"], 
            remove_num
        )
        
        # 记录下架信息
        removed_items.append({
            "name": item["goods_name"],
            "price": item["price"],
            "quantity": remove_num
        })
        
        # 更新物品数量或删除物品
        if item_quantity == remove_num:
            del data["user_items"][item_id]
        else:
            data["user_items"][item_id]["quantity"] -= remove_num
        
        remaining_quantity -= remove_num
    
    # 重新编号
    data["user_items"] = reset_dict_num(data["user_items"])
    
    # 保存数据
    save_fangshi_data(group_id, data)
    
    # 构造返回消息
    if removed_items:
        msg = "成功下架以下物品：\n"
        for item in removed_items:
            msg += f"{item['name']} {item['price']}灵石 x{item['quantity']}\n"
        
        if remaining_quantity > 0:
            msg += f"\n注意：实际下架了 {quantity - remaining_quantity} 个，未达到请求数量 {quantity} 个"
    else:
        msg = "没有物品被下架！"
    
    await handle_send(bot, event, msg)
    await shop_remove.finish()

@buy.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def buy_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """坊市购买"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await buy.finish()
    
    group_id = str(event.group_id)
    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    
    if len(args) < 1:
        msg = "请输入要购买的坊市ID！"
        await handle_send(bot, event, msg)
        await buy.finish()
    
    fangshi_id = args[0]
    quantity = int(args[1]) if len(args) > 1 else 1
    
    # 获取坊市数据
    data = get_fangshi_data(group_id)
    item = None
    
    # 查找物品
    if fangshi_id in data["system_items"]:
        item = data["system_items"][fangshi_id]
    elif fangshi_id in data["user_items"]:
        item = data["user_items"][fangshi_id]
    
    if not item:
        msg = f"未找到坊市ID为 {fangshi_id} 的物品！"
        await handle_send(bot, event, msg)
        await buy.finish()
    
    # 检查是否是自己的物品
    if "user_id" in item and str(item["user_id"]) == str(user_id):
        msg = "不能购买自己上架的物品！"
        await handle_send(bot, event, msg)
        await buy.finish()
    
    # 检查库存
    if "quantity" in item:
        if isinstance(item["quantity"], str) and item["quantity"] == "无限":
            pass  # 无限数量无需检查
        elif item["quantity"] < quantity:
            msg = f"库存不足，只有 {item['quantity']} 个可用！"
            await handle_send(bot, event, msg)
            await buy.finish()
    
    total_price = item["price"] * quantity
    
    # 检查灵石是否足够
    if user_info["stone"] < total_price:
        msg = f"灵石不足，需要 {total_price} 枚灵石！"
        await handle_send(bot, event, msg)
        await buy.finish()
    
    try:
        # 扣除灵石
        sql_message.update_ls(user_id, total_price, 2)
        
        # 如果是用户物品，给卖家灵石
        if "user_id" in item:
            seller_id = item["user_id"]
            sql_message.update_ls(seller_id, total_price, 1)
        
        # 给买家物品
        sql_message.send_back(
            user_id,
            item["goods_id"],
            item["goods_name"],
            item["goods_type"],
            quantity
        )
        
        # 更新库存或删除物品
        if "quantity" in item:
            if isinstance(item["quantity"], str) and item["quantity"] == "无限":
                pass  # 无限数量无需处理
            else:
                item["quantity"] -= quantity
                if item["quantity"] <= 0:
                    if fangshi_id in data["system_items"]:
                        del data["system_items"][fangshi_id]
                    else:
                        del data["user_items"][fangshi_id]
        
        # 保存数据
        if not save_fangshi_data(group_id, data):
            raise Exception("保存坊市数据失败")
        
        msg = f"成功购买 {item['goods_name']} x{quantity}！\n花费: {total_price} 灵石"
        await handle_send(bot, event, msg)
    except Exception as e:
        logger.error(f"坊市购买出错: {e}")
        msg = "购买过程中出现错误，请稍后再试！"
        await handle_send(bot, event, msg)
    
    await buy.finish()

@shop_view.handle(parameterless=[Cooldown(at_sender=False)])
async def shop_view_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """坊市查看"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await shop_view.finish()
    
    group_id = str(event.group_id)
    
    # 解析参数
    args_str = args.extract_plain_text().strip()
    parts = args_str.split()
    
    item_type = None
    current_page = 1
    
    if parts:
        # 尝试解析类型和页码
        for t in ["装备", "技能", "丹药", "药材"]:
            if parts[0].startswith(t):
                item_type = t
                if len(parts[0]) > len(t) and parts[0][len(t):].isdigit():
                    current_page = int(parts[0][len(t):])
                elif len(parts) > 1 and parts[1].isdigit():
                    current_page = int(parts[1])
                break
    
    data = get_fangshi_data(group_id)
    items_list = []
    for item in data["system_items"].values():
        if not item_type or item["goods_type"] == item_type:
            items_list.append({
                "id": item["id"],
                "name": item["goods_name"],
                "price": item["price"],
                "quantity": item.get("quantity", "无限"),
                "is_system": True
            })

    # 添加用户物品（去重，只保留最低价格）
    user_items_map = {}
    for item in data["user_items"].values():
        if not item_type or item["goods_type"] == item_type:
            key = item["goods_name"]
            if key not in user_items_map or item["price"] < user_items_map[key]["price"]:
                user_items_map[key] = {
                    "id": item["id"],
                    "name": item["goods_name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                    "is_system": False
                }

    # 合并系统物品和用户物品
    items_list.extend(user_items_map.values())

    # 检查分类下是否有物品
    if not items_list:
        if item_type:
            msg = f"坊市中暂无{item_type}类物品！"
        else:
            msg = "坊市目前空空如也！"
        await handle_send(bot, event, msg)
        await shop_view.finish()
    
    # 分页处理
    per_page = 10
    total_pages = (len(items_list) + per_page - 1) // per_page
    current_page = max(1, min(current_page, total_pages))
    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    paged_items = items_list[start_idx:end_idx]
    
    # 构建消息
    msg_list = []
    if item_type:
        msg_list.append(f"☆------坊市 {item_type} 物品------☆")
    else:
        msg_list.append("☆------坊市所有物品------☆")
    
    for item in paged_items:
        if item["is_system"]:
            msg = f"{item['name']} {item['price']}灵石 ID:{item['id']}"
            if item["quantity"] != "无限":  # 系统物品显示数量或"无限"
                msg += f" 数量:{item['quantity']}"
            else:
                msg += " 数量:无限"
        else:
            msg = f"{item['name']} {item['price']}灵石 ID:{item['id']}"
            if item["quantity"] > 1:  # 用户物品数量大于1时显示
                msg += f" 数量:{item['quantity']}"
        msg_list.append(msg)
    
    msg_list.append(f"\n第 {current_page}/{total_pages} 页")
    if total_pages > 1:
        msg_list.append(f"输入 坊市查看{item_type}{current_page + 1} 查看下一页")
    
    await send_msg_handler(bot, event, '坊市查看', bot.self_id, msg_list)
    await shop_view.finish()

@my_shop.handle(parameterless=[Cooldown(at_sender=False)])
async def my_shop_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """我的坊市"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await my_shop.finish()
    
    group_id = str(event.group_id)
    
    # 获取页码
    try:
        current_page = int(args.extract_plain_text().strip())
    except:
        current_page = 1
    
    data = get_fangshi_data(group_id)
    user_items = []
    
    # 获取用户所有上架物品
    for item in data["user_items"].values():
        if str(item["user_id"]) == str(user_info["user_id"]):
            user_items.append(item)
    
    # 按物品名称和价格分组
    item_groups = {}
    for item in user_items:
        key = (item["goods_name"], item["price"])
        if key not in item_groups:
            item_groups[key] = 0
        item_groups[key] += item["quantity"]

    # 检查用户是否有上架物品
    if not user_items:
        msg = "您在坊市中没有上架任何物品！"
        await handle_send(bot, event, msg)
        await my_shop.finish()

    # 转换为消息列表
    msg_list = []
    for (name, price), quantity in item_groups.items():
        msg = f"{name} {price}灵石"
        if quantity > 1:
            msg += f" x{quantity}"
        msg_list.append(msg)
    
    # 分页处理
    per_page = 10
    total_pages = (len(msg_list) + per_page - 1) // per_page
    current_page = max(1, min(current_page, total_pages))
    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    paged_msgs = msg_list[start_idx:end_idx]
    
    # 构建最终消息
    final_msg = [f"☆------{user_info['user_name']}的坊市物品------☆"]
    final_msg.extend(paged_msgs)
    final_msg.append(f"\n第 {current_page}/{total_pages} 页")
    
    await send_msg_handler(bot, event, '我的坊市', bot.self_id, final_msg)
    await my_shop.finish()

@shop_added_by_admin.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def shop_added_by_admin_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """系统坊市上架"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    group_id = str(event.group_id)
    args = args.extract_plain_text().split()
    
    if len(args) < 1:
        msg = "请输入正确指令！例如：系统坊市上架 物品 [价格] [数量]"
        await handle_send(bot, event, msg)
        await shop_added_by_admin.finish()
    
    goods_name = args[0]
    goods_id = None
    
    # 查找物品ID
    for k, v in items.items.items():
        if goods_name == v['name']:
            goods_id = k
            break
    
    if not goods_id:
        msg = f"未找到物品 {goods_name}！"
        await handle_send(bot, event, msg)
        await shop_added_by_admin.finish()
    
    # 解析价格和数量
    try:
        price = int(args[1]) if len(args) > 1 else MIN_PRICE
        quantity = int(args[2]) if len(args) > 2 else 0  # 0表示无限
    except ValueError:
        msg = "请输入有效的价格和数量！"
        await handle_send(bot, event, msg)
        await shop_added_by_admin.finish()
    
    price = max(price, MIN_PRICE)
    
    # 添加到系统坊市
    data = get_fangshi_data(group_id)
    system_id = str(data["next_system_id"])
    data["next_system_id"] += 1
    
    data["system_items"][system_id] = {
        "id": system_id,
        "goods_id": goods_id,
        "goods_name": goods_name,
        "goods_type": items.get_data_by_item_id(goods_id)["type"],
        "price": price,
        "quantity": quantity if quantity > 0 else "无限",
        "desc": get_item_msg(goods_id)
    }
    
    save_fangshi_data(group_id, data)
    
    msg = f"系统成功上架 {goods_name} 到坊市！\n价格: {price} 灵石\n"
    if quantity > 0:
        msg += f"数量: {quantity}"
    else:
        msg += "数量: 无限"
    msg += f"\n坊市ID: {system_id}"
    
    await handle_send(bot, event, msg)
    await shop_added_by_admin.finish()

@shop_remove_by_admin.handle(parameterless=[Cooldown(1.4, at_sender=False)])
async def shop_remove_by_admin_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """系统坊市下架"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    group_id = str(event.group_id)
    arg = args.extract_plain_text().strip()
    
    if not arg:
        msg = "请输入要下架的坊市ID或物品名称！"
        await handle_send(bot, event, msg)
        await shop_remove_by_admin.finish()
    
    data = get_fangshi_data(group_id)
    removed_items = []
    
    if arg.isdigit():  # 按ID下架
        fangshi_id = arg
        if fangshi_id in data["system_items"]:
            removed_items.append(data["system_items"][fangshi_id])
            del data["system_items"][fangshi_id]
        elif fangshi_id in data["user_items"]:
            item = data["user_items"][fangshi_id]
            # 退回给玩家
            sql_message.send_back(
                item["user_id"],
                item["goods_id"],
                item["goods_name"],
                item["goods_type"],
                item["quantity"]
            )
            removed_items.append(item)
            del data["user_items"][fangshi_id]
        else:
            msg = f"未找到坊市ID为 {fangshi_id} 的物品！"
            await handle_send(bot, event, msg)
            await shop_remove_by_admin.finish()
    else:  # 按名称下架
        goods_name = arg
        # 先找系统物品
        system_items = [item for item in data["system_items"].values() 
                       if item["goods_name"] == goods_name]
        
        if system_items:
            for item in system_items:
                removed_items.append(item)
                del data["system_items"][item["id"]]
        else:
            # 找用户物品（按价格排序）
            user_items = [item for item in data["user_items"].values() 
                         if item["goods_name"] == goods_name]
            user_items.sort(key=lambda x: x["price"])
            
            if user_items:
                item = user_items[0]
                # 退回给玩家
                sql_message.send_back(
                    item["user_id"],
                    item["goods_id"],
                    item["goods_name"],
                    item["goods_type"],
                    item["quantity"]
                )
                removed_items.append(item)
                del data["user_items"][item["id"]]
            else:
                msg = f"未找到名称为 {goods_name} 的物品！"
                await handle_send(bot, event, msg)
                await shop_remove_by_admin.finish()
    
    save_fangshi_data(group_id, data)
    
    if removed_items:
        msg = "成功下架以下物品：\n"
        for item in removed_items:
            if "user_id" in item:
                msg += f"用户物品: {item['goods_name']} x{item['quantity']} (价格: {item['price']})\n"
            else:
                msg += f"系统物品: {item['goods_name']} x{item.get('quantity', '无限')}\n"
    else:
        msg = "没有物品被下架！"
    
    await handle_send(bot, event, msg)
    await shop_remove_by_admin.finish()


@auction_withdraw.handle(parameterless=[Cooldown(1.4, at_sender=False, isolate_level=CooldownIsolateLevel.GROUP)])
async def auction_withdraw_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """用户撤回拍卖品"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    group_id = "000000"
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await auction_withdraw.finish()

    group_id = "000000"
    if group_id not in groups:
        msg = '尚未开启拍卖会功能，请联系管理员开启！'
        await handle_send(bot, event, msg)
        await auction_withdraw.finish()

    config = get_auction_config()
    user_auctions = config.get('user_auctions', [])

    if not user_auctions:
        msg = f"拍卖会目前没有道友提交的物品！"
        await handle_send(bot, event, msg)
        await auction_withdraw.finish()

    arg = args.extract_plain_text().strip()
    auction_index = int(arg) - 1
    if auction_index < 0 or auction_index >= len(user_auctions):
        msg = f"请输入正确的编号"
        await handle_send(bot, event, msg)
        await auction_withdraw.finish()

    auction = user_auctions[auction_index]
    goods_name, details = list(auction.items())[0]
    if details['user_id'] != user_info['user_id']:
        msg = f"这不是你的拍卖品！"
        await handle_send(bot, event, msg)
        await auction_withdraw.finish()

    sql_message.send_back(details['user_id'], details['id'], goods_name, details['goods_type'], details['quantity'])
    user_auctions.pop(auction_index)
    config['user_auctions'] = user_auctions
    savef_auction(config)

    msg = f"成功撤回拍卖品：{goods_name}x{details['quantity']}！"
    await handle_send(bot, event, msg)

    await auction_withdraw.finish()

        
@no_use_zb.handle(parameterless=[Cooldown(at_sender=False)])
async def no_use_zb_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """卸载物品（只支持装备）
    ["user_id", "goods_id", "goods_name", "goods_type", "goods_num", "create_time", "update_time",
    "remake", "day_num", "all_num", "action_time", "state"]
    """
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await no_use_zb.finish()
    user_id = user_info['user_id']
    arg = args.extract_plain_text().strip()

    back_msg = sql_message.get_back_msg(user_id)  # 背包sql信息,list(back)
    if back_msg is None:
        msg = "道友的背包空空如也！"
        await handle_send(bot, event, msg)
        await no_use_zb.finish()
    in_flag = False  # 判断指令是否正确，道具是否在背包内
    goods_id = None
    goods_type = None
    for back in back_msg:
        if arg == back['goods_name']:
            in_flag = True
            goods_id = back['goods_id']
            goods_type = back['goods_type']
            break
    if not in_flag:
        msg = f"请检查道具 {arg} 是否在背包内！"
        await handle_send(bot, event, msg)
        await no_use_zb.finish()

    if goods_type == "装备":
        if not check_equipment_can_use(user_id, goods_id):
            sql_str, item_type = get_no_use_equipment_sql(user_id, goods_id)
            for sql in sql_str:
                sql_message.update_back_equipment(sql)
            if item_type == "法器":
                sql_message.updata_user_faqi_buff(user_id, 0)
            if item_type == "防具":
                sql_message.updata_user_armor_buff(user_id, 0)
            msg = f"成功卸载装备{arg}！"
            await handle_send(bot, event, msg)
            await no_use_zb.finish()
        else:
            msg = "装备没有被使用，无法卸载！"
            await handle_send(bot, event, msg)
            await no_use_zb.finish()
    else:
        msg = "目前只支持卸载装备！"
        await handle_send(bot, event, msg)
        await no_use_zb.finish()


@use.handle(parameterless=[Cooldown(at_sender=False)])
async def use_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """使用物品"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await use.finish()
    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    if not args:
        msg = "请输入要使用的物品名称！"
        await handle_send(bot, event, msg)
        await use.finish()
    
    arg = args[0]  # 物品名称
    back_msg = sql_message.get_back_msg(user_id)  # 获取背包信息
    if back_msg is None:
        msg = "道友的背包空空如也！"
        await handle_send(bot, event, msg)
        await use.finish()
    
    # 检查物品是否在背包中
    in_flag = False
    goods_id = None
    goods_type = None
    goods_num = None
    for back in back_msg:
        if arg == back['goods_name']:
            in_flag = True
            goods_id = back['goods_id']
            goods_type = back['goods_type']
            goods_num = back['goods_num']
            break
    
    if not in_flag:
        msg = f"请检查该道具 {arg} 是否在背包内！"
        await handle_send(bot, event, msg)
        await use.finish()
    
    # 处理使用数量的通用逻辑
    num = 1
    try:
        if len(args) > 1 and 1 <= int(args[1]) <= int(goods_num):
            num = int(args[1])
        elif len(args) > 1 and int(args[1]) > int(goods_num):
            msg = f"道友背包中的{arg}数量不足，当前仅有{goods_num}个！"
            await handle_send(bot, event, msg)
            await use.finish()
    except ValueError:
        num = 1
    
    # 根据物品类型处理逻辑
    goods_info = items.get_data_by_item_id(goods_id)

    if goods_type == "礼包":
        package_name = goods_info['name']
        msg_parts = []
        i = 1
        while True:
            buff_key = f'buff_{i}'
            name_key = f'name_{i}'
            type_key = f'type_{i}'
            amount_key = f'amount_{i}'

            if name_key not in goods_info:
                break

            item_name = goods_info[name_key]
            item_amount = goods_info.get(amount_key, 1) * num
            item_type = goods_info.get(type_key)
            buff_id = goods_info.get(buff_key)

            if item_name == "灵石":
                key = 1 if item_amount > 0 else 2  # 正数增加，负数减少
                sql_message.update_ls(user_id, abs(item_amount), key)
                msg_parts.append(f"获得灵石 {item_amount} 枚\n")
            else:
                # 调整 goods_type
                if item_type in ["辅修功法", "神通", "功法", "身法", "瞳术"]:
                    goods_type_item = "技能"
                elif item_type in ["法器", "防具"]:
                    goods_type_item = "装备"
                else:
                    goods_type_item = item_type  # 包括 "礼包" 类型，直接放入背包

                if buff_id is not None:
                    sql_message.send_back(user_id, buff_id, item_name, goods_type_item, item_amount, 1)
                    msg_parts.append(f"获得 {item_name} x{item_amount}\n")
            
            i += 1
        sql_message.update_back_j(user_id, goods_id, num=num, use_key=1)
        msg = f"道友打开了 {num} 个 {package_name}:\n" + "".join(msg_parts)

    elif goods_type == "装备":
        if not check_equipment_can_use(user_id, goods_id):
            msg = "该装备已被装备，请勿重复装备！"
        else:
            sql_str, item_type = get_use_equipment_sql(user_id, goods_id)
            for sql in sql_str:
                sql_message.update_back_equipment(sql)
            if item_type == "法器":
                sql_message.updata_user_faqi_buff(user_id, goods_id)
            if item_type == "防具":
                sql_message.updata_user_armor_buff(user_id, goods_id)
            msg = f"成功装备 {arg}！"

    elif goods_type == "技能":
        user_buff_info = UserBuffDate(user_id).BuffInfo
        skill_info = goods_info
        skill_type = skill_info['item_type']
        if skill_type == "神通":
            if int(user_buff_info['sec_buff']) == int(goods_id):
                msg = f"道友已学会该神通：{skill_info['name']}，请勿重复学习！"
            else:
                sql_message.update_back_j(user_id, goods_id)
                sql_message.updata_user_sec_buff(user_id, goods_id)
                msg = f"恭喜道友学会神通：{skill_info['name']}！"
        elif skill_type == "身法":
            if int(user_buff_info['effect1_buff']) == int(goods_id):
                msg = f"道友已学会该身法：{skill_info['name']}，请勿重复学习！"
            else:
                sql_message.update_back_j(user_id, goods_id)
                sql_message.updata_user_effect1_buff(user_id, goods_id)
                msg = f"恭喜道友学会身法：{skill_info['name']}！"
        elif skill_type == "瞳术":
            if int(user_buff_info['effect2_buff']) == int(goods_id):
                msg = f"道友已学会该瞳术：{skill_info['name']}，请勿重复学习！"
            else:
                sql_message.update_back_j(user_id, goods_id)
                sql_message.updata_user_effect2_buff(user_id, goods_id)
                msg = f"恭喜道友学会瞳术：{skill_info['name']}！"
        elif skill_type == "功法":
            if int(user_buff_info['main_buff']) == int(goods_id):
                msg = f"道友已学会该功法：{skill_info['name']}，请勿重复学习！"
            else:
                sql_message.update_back_j(user_id, goods_id)
                sql_message.updata_user_main_buff(user_id, goods_id)
                msg = f"恭喜道友学会功法：{skill_info['name']}！"
        elif skill_type == "辅修功法":
            if int(user_buff_info['sub_buff']) == int(goods_id):
                msg = f"道友已学会该辅修功法：{skill_info['name']}，请勿重复学习！"
            else:
                sql_message.update_back_j(user_id, goods_id)
                sql_message.updata_user_sub_buff(user_id, goods_id)
                msg = f"恭喜道友学会辅修功法：{skill_info['name']}！"
        else:
            msg = f"发生未知错误！"

    elif goods_type == "丹药":
        msg = check_use_elixir(user_id, goods_id, num)

    elif goods_type == "神物":
        user_info = sql_message.get_user_info_with_id(user_id)
        user_rank = convert_rank(user_info['level'])[0]
        goods_rank = goods_info['rank']
        goods_name = goods_info['name']
        if goods_rank < user_rank:
            msg = f"神物：{goods_name}的使用境界为{goods_info['境界']}以上，道友不满足使用条件！"
        else:
            exp = goods_info['buff'] * num
            user_hp = int(user_info['hp'] + (exp / 2))
            user_mp = int(user_info['mp'] + exp)
            user_atk = int(user_info['atk'] + (exp / 10))
            sql_message.update_exp(user_id, exp)
            sql_message.update_power2(user_id)
            sql_message.update_user_attribute(user_id, user_hp, user_mp, user_atk)
            sql_message.update_back_j(user_id, goods_id, num=num, use_key=1)
            msg = f"道友成功使用神物：{goods_name} {num} 个，修为增加 {exp} 点！"

    elif goods_type == "聚灵旗":
        msg = get_use_jlq_msg(user_id, goods_id)

    else:
        msg = "该类型物品调试中，未开启！"

    # 发送结果消息
    await handle_send(bot, event, msg)
    await use.finish()

@auction_view.handle(parameterless=[Cooldown(at_sender=False, isolate_level=CooldownIsolateLevel.GROUP)])
async def auction_view_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """查看拍卖会物品"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    group_id = "000000"
    if not isUser:
        await handle_send(bot, event, msg)
        await auction_view.finish()
    
    if group_id not in groups:
        msg = '尚未开启拍卖会功能，请联系管理员开启！'
        await handle_send(bot, event, msg)
        await auction_view.finish()

    config = get_auction_config()
    user_auctions = config.get('user_auctions', [])
   

    if not user_auctions:
        msg = "拍卖会目前没有道友提交的物品！"
        await handle_send(bot, event, msg)
        await auction_view.finish()

    auction_list_msg = "拍卖会物品列表:\n"
    
    for idx, auction in enumerate(user_auctions):
        for goods_name, details in auction.items():
            user_info = sql_message.get_user_info_with_id(details['user_id'])
            auction_list_msg += f"编号: {idx + 1}\n物品名称: {goods_name}\n物品类型：{details['goods_type']}\n所有者：{user_info['user_name']}\n底价: {details['start_price']} 枚灵石\n数量: {details['quantity']}\n"
            auction_list_msg += "☆------------------------------☆\n"

    await handle_send(bot, event, auction_list_msg)

    await auction_view.finish()


@creat_auction.handle(parameterless=[Cooldown(at_sender=False)])
async def creat_auction_(bot: Bot, event: GroupMessageEvent):
    global auction, auction_offer_flag, auction_offer_all_count, auction_offer_time_count
    group_id = "000000"
    bot = await assign_bot_group(group_id=group_id)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await creat_auction.finish()
        
    if group_id not in groups:
        msg = '尚未开启拍卖会功能，请联系管理员开启！'
        await handle_send(bot, event, msg)
        await creat_auction.finish()

    if auction:
        msg = "已存在一场拍卖会，请等待拍卖会结束！"
        await handle_send(bot, event, msg)
        await creat_auction.finish()

    auction_items = []
    try:
        # 用户拍卖品
        user_auction_id_list = get_user_auction_id_list()
        for auction_id in user_auction_id_list:
            user_auction_info = get_user_auction_price_by_id(auction_id)
            auction_items.append((auction_id, user_auction_info['quantity'], user_auction_info['start_price'], True))

        # 系统拍卖品
        auction_id_list = get_auction_id_list()
        auction_count = random.randint(1, 2)  # 随机挑选系统拍卖品数量
        auction_ids = random.sample(auction_id_list, auction_count)
        for auction_id in auction_ids:
            item_info = items.get_data_by_item_id(auction_id)
            item_quantity = 1
            if item_info['type'] in ['神物', '丹药']:
                item_quantity = random.randint(1, 3) # 如果是丹药的话随机挑1-3个
            auction_items.append((auction_id, item_quantity, get_auction_price_by_id(auction_id)['start_price'], False))
    except LookupError:
        msg = f"获取不到拍卖物品的信息，请检查配置文件！"
        await handle_send(bot, event, msg)
        await creat_auction.finish()

    # 打乱拍卖品顺序
    random.shuffle(auction_items)

    msg = f"请各位道友稍作准备，拍卖即将开始...\n"
    msg += f"本场拍卖会共有{len(auction_items)}件物品，将依次拍卖，分别是：\n"
    for idx, (auction_id, item_quantity, start_price, is_user_auction) in enumerate(auction_items):
        item_name = items.get_data_by_item_id(auction_id)['name']
        if is_user_auction:
            owner_info = sql_message.get_user_info_with_id(get_user_auction_price_by_id(auction_id)['user_id'])
            owner_name = owner_info['user_name']
            msg += f"{idx + 1}号：{item_name}x{item_quantity}（由{owner_name}道友提供）\n"
        else:
            msg += f"{idx + 1}号：{item_name}x{item_quantity}（由拍卖场提供）\n"
    
    for gid in groups:
        bot = await assign_bot_group(group_id=gid)
        try:
            await handle_send(bot, event, msg)
        except ActionFailed:
            continue
    
    auction_results = []  # 拍卖结果
    for i, (auction_id, item_quantity, start_price, is_user_auction) in enumerate(auction_items):
        auction_info = items.get_data_by_item_id(auction_id)

        auction = {
            'id': auction_id,
            'user_id': 0,
            'now_price': start_price,
            'name': auction_info['name'],
            'type': auction_info['type'],
            'quantity': item_quantity,
            'start_time': datetime.now(),
            'group_id': group_id
        }
        
        if i + 1 == len(auction_items):
            msg = f"最后一件拍卖品为：\n{get_auction_msg(auction_id)}\n"
        else:
            msg = f"第{i + 1}件拍卖品为：\n{get_auction_msg(auction_id)}\n"
        msg += f"\n底价为{start_price}，加价不少于{int(start_price * 0.05)}"
        msg += f"\n竞拍时间为:{AUCTIONSLEEPTIME}秒，请诸位道友发送 拍卖+金额 来进行拍卖吧！"

        if auction['quantity'] > 1:
            msg += f"\n注意：拍卖品共{auction['quantity']}件，最终价为{auction['quantity']}x成交价。\n"

        if i + 1 < len(auction_items):
            next_item_name = items.get_data_by_item_id(auction_items[i + 1][0])['name']
            msg += f"\n下一件拍卖品为：{next_item_name}，请心仪的道友提前开始准备吧！"

        for gid in groups:
            bot = await assign_bot_group(group_id=gid)
            try:
                await handle_send(bot, event, msg)
            except ActionFailed:
                continue
        
        remaining_time = AUCTIONSLEEPTIME # 第一轮定时
        while remaining_time > 0:
            await asyncio.sleep(10)
            remaining_time -= 10

        while auction_offer_flag:  # 有人拍卖
            if auction_offer_all_count == 0:
                auction_offer_flag = False
                break

            logger.opt(colors=True).info(f"<green>有人拍卖，本次等待时间：{auction_offer_all_count * AUCTIONOFFERSLEEPTIME}秒</green>")
            first_time = auction_offer_all_count * AUCTIONOFFERSLEEPTIME
            auction_offer_all_count = 0
            auction_offer_flag = False
            await asyncio.sleep(first_time)
            logger.opt(colors=True).info(f"<green>总计等待时间{auction_offer_time_count * AUCTIONOFFERSLEEPTIME}秒，当前拍卖标志：{auction_offer_flag}，本轮等待时间：{first_time}</green>")

        logger.opt(colors=True).info(f"<green>等待时间结束，总计等待时间{auction_offer_time_count * AUCTIONOFFERSLEEPTIME}秒</green>")
        if auction['user_id'] == 0:
            msg = f"很可惜，{auction['name']}流拍了\n"
            if i + 1 == len(auction_items):
                msg += f"本场拍卖会到此结束，开始整理拍卖会结果，感谢各位道友参与！"

            for gid in groups:
                bot = await assign_bot_group(group_id=gid)
                try:
                    await handle_send(bot, event, msg)
                except ActionFailed:
                    continue
            auction_results.append((auction_id, None, auction['group_id'], auction_info['type'], auction['now_price'], auction['quantity']))
            auction = {}
            continue
        
        user_info = sql_message.get_user_info_with_id(auction['user_id'])
        msg = f"(拍卖锤落下)！！！\n"
        msg += f"恭喜来自群{auction['group_id']}的{user_info['user_name']}道友成功拍下：{auction['type']}-{auction['name']}x{auction['quantity']}，将在拍卖会结算后送到您手中。\n"
        if i + 1 == len(auction_items):
            msg += f"本场拍卖会到此结束，开始整理拍卖会结果，感谢各位道友参与！"

        auction_results.append((auction_id, user_info['user_id'], auction['group_id'], 
                                auction_info['type'], auction['now_price'], auction['quantity']))
        auction = {}
        auction_offer_time_count = 0
        for gid in groups:
            bot = await assign_bot_group(group_id=gid)
            try:
                await handle_send(bot, event, msg)
            except ActionFailed:
                continue
        
    # 拍卖会结算
    end_msg = f"本场拍卖会结束！感谢各位道友的参与。\n拍卖结果整理如下：\n"
    for idx, (auction_id, user_id, group_id, item_type, final_price, quantity) in enumerate(auction_results):
        item_name = items.get_data_by_item_id(auction_id)['name']
        final_user_info = sql_message.get_user_info_with_id(user_id)
        if user_id:
            if final_user_info['stone'] < (int(final_price) * quantity):
                end_msg += f"{idx + 1}号拍卖品：{item_name}x{quantity} - 道友{final_user_info['user_name']}的灵石不足，流拍了\n"
            else:
                sql_message.update_ls(user_id, int(final_price) * quantity, 2)
                sql_message.send_back(user_id, auction_id, item_name, item_type, quantity)
                end_msg += f"{idx + 1}号拍卖品：{item_name}x{quantity}由群{group_id}的{final_user_info['user_name']}道友成功拍下\n"

            user_auction_info = get_user_auction_price_by_id(auction_id)
            if user_auction_info:
                seller_id = user_auction_info['user_id']
                auction_earnings = int(final_price * quantity * 0.7) # 收个手续费
                sql_message.update_ls(seller_id, auction_earnings, 1)

            remove_auction_item(auction_id)

            auction = {}
            auction_offer_time_count = 0
        else:
            end_msg += f"{idx + 1}号拍卖品：{item_name}x{quantity} - 流拍了\n"

    for gid in groups:
        bot = await assign_bot_group(group_id=gid)
        try:
            await handle_send(bot, event, end_msg)
        except ActionFailed:  # 发送群消息失败
            continue

    await creat_auction.finish()


@offer_auction.handle(parameterless=[Cooldown(1.4, at_sender=False, isolate_level=CooldownIsolateLevel.GLOBAL)])
async def offer_auction_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """拍卖"""
    group_id = "000000"
    bot = await assign_bot_group(group_id=group_id)
    isUser, user_info, msg = check_user(event)
    global auction, auction_offer_flag, auction_offer_all_count, auction_offer_time_count
    if not isUser:
        await handle_send(bot, event, msg)
        await offer_auction.finish()

    if group_id not in groups:
        msg = f"尚未开启拍卖会功能，请联系管理员开启！"
        await handle_send(bot, event, msg)
        await offer_auction.finish()

    if not auction:
        msg = f"不存在拍卖会，请等待拍卖会开启！"
        await handle_send(bot, event, msg)
        await offer_auction.finish()

    price = args.extract_plain_text().strip()
    try:
        price = int(price)
    except ValueError:
        msg = f"请发送正确的灵石数量"
        await handle_send(bot, event, msg)
        await offer_auction.finish()

    now_price = auction['now_price']
    min_price = int(now_price * 0.05)  # 最低加价5%
    if price <= 0 or price <= auction['now_price'] or price > user_info['stone']:
        msg = f"走开走开，别捣乱！小心清空你灵石捏"
        await handle_send(bot, event, msg)
        await offer_auction.finish()
    if price - now_price < min_price:
        msg = f"拍卖不得少于当前竞拍价的5%，目前最少加价为：{min_price}灵石，目前竞拍价为：{now_price}!"
        await handle_send(bot, event, msg)
        await offer_auction.finish()

    auction_offer_flag = True  # 有人拍卖
    auction_offer_time_count += 1
    auction_offer_all_count += 1

    auction['user_id'] = user_info['user_id']
    auction['now_price'] = price
    auction['group_id'] = group_id

    logger.opt(colors=True).info(f"<green>{user_info['user_name']}({auction['user_id']})竞价了！！</green>")

    now_time = datetime.now()
    dif_time = (now_time - auction['start_time']).total_seconds()
    remaining_time = int(AUCTIONSLEEPTIME - dif_time + AUCTIONOFFERSLEEPTIME * auction_offer_time_count)
    msg = (
        f"来自群{group_id}的{user_info['user_name']}道友拍卖：{price}枚灵石！" +
        f"竞拍时间增加：{AUCTIONOFFERSLEEPTIME}秒，竞拍剩余时间：{remaining_time}秒"
    )
    error_msg = None
    for group_id in groups:
        bot = await assign_bot_group(group_id=group_id)
        try:
            await handle_send(bot, event, msg)
        except ActionFailed:
            continue
    logger.opt(colors=True).info(
        f"<green>有人拍卖，拍卖标志：{auction_offer_flag}，当前等待时间：{auction_offer_all_count * AUCTIONOFFERSLEEPTIME}，总计拍卖次数：{auction_offer_time_count}</green>")
    if error_msg is None:
        await offer_auction.finish()
    else:
        msg = error_msg
        await handle_send(bot, event, msg)
        await offer_auction.finish()


@auction_added.handle(parameterless=[Cooldown(1.4, isolate_level=CooldownIsolateLevel.GROUP)])
async def auction_added_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """用户提交拍卖品"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    group_id = "000000"
    if not isUser:
        await handle_send(bot, event, msg)
        await auction_added.finish()

    if group_id not in groups:
        msg = f"尚未开启拍卖会功能，请联系管理员开启！"
        await handle_send(bot, event, msg)
        await auction_added.finish()

    user_id = user_info['user_id']
    args = args.extract_plain_text().split()
    goods_name = args[0] if len(args) > 0 else None
    price_str = args[1] if len(args) > 1 else "1"
    quantity_str = args[2] if len(args) > 2 else "1"

    if not goods_name:
        msg = f"请输入正确指令！例如：提交拍卖品 物品 可选参数为(金额 数量)"
        await handle_send(bot, event, msg)
        await auction_added.finish()

    back_msg = sql_message.get_back_msg(user_id)  # 获取背包信息
    if back_msg is None:
        msg = f"道友的背包空空如也！"
        await handle_send(bot, event, msg)
        await auction_added.finish()

    # 物品是否存在于背包中
    in_flag = False
    goods_id = None
    goods_type = None
    goods_state = None
    goods_num = None
    goods_bind_num = None
    for back in back_msg:
        if goods_name == back['goods_name']:
            in_flag = True
            goods_id = back['goods_id']
            goods_type = back['goods_type']
            goods_state = back['state']
            goods_num = back['goods_num']
            goods_bind_num = back['bind_num']
            break

    if not in_flag:
        msg = f"请检查该道具 {goods_name} 是否在背包内！"
        await handle_send(bot, event, msg)
        await auction_added.finish()

    try:
        price = int(price_str)
        quantity = int(quantity_str)
        if price <= 0 or quantity <= 0 or quantity > goods_num:
            raise ValueError("价格和数量必须为正数，或者超过了你拥有的数量!")
    except ValueError as e:
        msg = f"请输入正确的金额和数量: {str(e)}"
        await handle_send(bot, event, msg)
        await auction_added.finish()

    if goods_type == "装备" and int(goods_state) == 1 and int(goods_num) == 1:
        msg = f"装备：{goods_name}已经被道友装备在身，无法提交！"
        await handle_send(bot, event, msg)
        await auction_added.finish()

    if int(goods_num) <= int(goods_bind_num):
        msg = f"该物品是绑定物品，无法提交！"
        await handle_send(bot, event, msg)
        await auction_added.finish()
    if goods_type == "聚灵旗" or goods_type == "炼丹炉":
        if user_info['root'] == "凡人":
            pass
        else:
            msg = f"道友职业无法上架！"
            await handle_send(bot, event, msg)
            await auction_added.finish()

    config = get_auction_config()

    user_auction = {
        goods_name: {
            'id': goods_id,
            'goods_type': goods_type,
            'user_id': user_id,
            'start_price': price,
            'quantity': quantity
        }
    }
    config['user_auctions'].append(user_auction)

    savef_auction(config)
    sql_message.update_back_j(user_id, goods_id, num=quantity)

    msg = f"道友的拍卖品：{goods_name}成功提交，底价：{price}枚灵石，数量：{quantity}"
    msg += f"\n下次拍卖将优先拍卖道友的拍卖品！！！"
    await handle_send(bot, event, msg)
    await auction_added.finish()


@set_auction.handle(parameterless=[Cooldown(at_sender=False)])
async def set_auction_(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """拍卖会开关"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    mode = args.extract_plain_text().strip()
    group_id = "000000"
    is_in_group = is_in_groups(event)  # True在，False不在

    if mode == '开启':
        if is_in_group:
            msg = "已开启拍卖会，请勿重复开启!"
            await handle_send(bot, event, msg)
            await set_auction.finish()
        else:
            config['open'].append(group_id)
            savef_auction(config)
            msg = "已开启拍卖会"
            await handle_send(bot, event, msg)
            await set_auction.finish()

    elif mode == '关闭':
        if is_in_group:
            config['open'].remove(group_id)
            savef_auction(config)
            msg = "已关闭拍卖会!"
            await handle_send(bot, event, msg)
            await set_auction.finish()
        else:
            msg = "未开启拍卖会!"
            await handle_send(bot, event, msg)
            await set_auction.finish()

    else:
        msg = __back_help__
        await handle_send(bot, event, msg)
        await set_auction.finish()


@chakan_wupin.handle(parameterless=[Cooldown(at_sender=False)])
async def chakan_wupin_(
    bot: Bot, 
    event: GroupMessageEvent | PrivateMessageEvent, 
    args: Message = CommandArg()
):
    """查看修仙界物品（支持 类型+页码 或 类型 + 空格 + 页码）"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    args_str = args.extract_plain_text().strip()
    
    # 支持的类型列表
    valid_types = ["功法", "辅修功法", "神通", "身法", "瞳术", "丹药", "合成丹药", "法器", "防具", "特殊物品"]
    
    # 解析类型和页码
    item_type = None
    current_page = 1  # 默认第一页
    
    # 情况1：用户输入类似 "神通2"（无空格）
    for t in valid_types:
        if args_str.startswith(t) and len(args_str) > len(t):
            remaining = args_str[len(t):].strip()
            if remaining.isdigit():  # 检查剩余部分是否是数字
                item_type = t
                current_page = int(remaining)
                break
    
    if item_type is None:
        parts = args_str.split(maxsplit=1)  # 只分割第一个空格
        if len(parts) == 2 and parts[0] in valid_types and parts[1].isdigit():
            item_type = parts[0]
            current_page = int(parts[1])
        elif args_str in valid_types:  # 仅类型，无页码
            item_type = args_str
        else:
            msg = "请输入正确类型【功法|辅修功法|神通|身法|瞳术|丹药|合成丹药|法器|防具|特殊物品】！！！"
            await handle_send(bot, event, msg)
            await chakan_wupin.finish()
    
    # 获取物品数据
    if item_type == "特殊物品":
        # 特殊物品包括聚灵旗和特殊道具
        jlq_data = items.get_data_by_item_type(["聚灵旗"])
        special_data = items.get_data_by_item_type(["特殊物品"])
        item_data = {**jlq_data, **special_data}
    else:
        item_data = items.get_data_by_item_type([item_type])
    
    msg_list = []
    
    for item_id, item_info in item_data.items():
        name = item_info['name']
        if item_type in ["功法", "辅修功法", "神通", "身法", "瞳术", "法器", "防具"]:
            desc = get_item_msg(item_id)
            msg = f"ID：{item_id}\n{desc}"
        elif item_type == "特殊物品":
            if item_info['type'] == "聚灵旗":
                msg = f"ID：{item_id}\n名字：{name}\n效果：{item_info['desc']}\n修炼速度：{item_info['修炼速度'] * 100}%\n药材速度：{item_info['药材速度'] * 100}%"
            else:  # 特殊道具
                msg = f"ID：{item_id}\n名字：{name}\n效果：{item_info.get('desc', '十分神秘的东西，谁也不知道它的作用')}"
        else:  # 丹药、合成丹药
            rank = item_info.get('境界', '')
            desc = item_info.get('desc', '')
            msg = f"※{rank}丹药:{name}，效果：{desc}\n"
        msg_list.append(msg)
    
    # 分页处理
    title = f"修仙界物品列表-{item_type}"
    msgs = await handle_pagination(
        msg_list, 
        current_page, 
        title=title, 
        empty_msg=f"修仙界暂无{item_type}类物品"
    )
    
    if isinstance(msgs, str):  # 空提示消息
        await handle_send(bot, event, msgs)
    else:  # 分页消息列表
        await send_msg_handler(bot, event, title, bot.self_id, msgs)
    
    await chakan_wupin.finish()

@main_back.handle(parameterless=[Cooldown(cd_time=10, at_sender=False)])
async def main_back_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """我的背包"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await main_back.finish()
    
    # 获取页码
    try:
        current_page = int(args.extract_plain_text().strip())
    except:
        current_page = 1
    
    user_id = user_info['user_id']
    msg_list = get_user_main_back_msg(user_id)
    title = f"{user_info['user_name']}的背包"
    msgs = await handle_pagination(
        msg_list, 
        current_page,
        title=title,
        empty_msg="道友的背包空空如也！"
    )
    
    if isinstance(msgs, str):
        await handle_send(bot, event, msgs)
    else:
        await send_msg_handler(bot, event, '背包', bot.self_id, msgs)
    
    await main_back.finish()

@yaocai_back.handle(parameterless=[Cooldown(cd_time=10, at_sender=False)])
async def yaocai_back_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """药材背包"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await yaocai_back.finish()
    
    # 获取页码
    try:
        current_page = int(args.extract_plain_text().strip())
    except:
        current_page = 1
    
    user_id = user_info['user_id']
    msg_list = get_user_yaocai_back_msg(user_id)
    title = f"{user_info['user_name']}的药材背包"
    msgs = await handle_pagination(
        msg_list, 
        current_page,
        title=title,
        empty_msg="道友的药材背包空空如也！"
    )
    
    if isinstance(msgs, str):
        await handle_send(bot, event, msgs)
    else:
        await send_msg_handler(bot, event, '药材背包', bot.self_id, msgs)
    
    await yaocai_back.finish()

@danyao_back.handle(parameterless=[Cooldown(cd_time=10, at_sender=False)])
async def danyao_back_(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """丹药背包"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await danyao_back.finish()
    
    # 获取页码
    try:
        current_page = int(args.extract_plain_text().strip())
    except:
        current_page = 1
    
    user_id = user_info['user_id']
    msg_list = get_user_danyao_back_msg(user_id)
    title = f"{user_info['user_name']}的丹药背包"
    msgs = await handle_pagination(
        msg_list, 
        current_page,
        title=title,
        empty_msg="道友的丹药背包空空如也！"
    )
    
    if isinstance(msgs, str):
        await handle_send(bot, event, msgs)
    else:
        await send_msg_handler(bot, event, '丹药背包', bot.self_id, msgs)
    
    await danyao_back.finish()


@shop_off_all.handle(parameterless=[Cooldown(60, isolate_level=CooldownIsolateLevel.GROUP, parallel=1)])
async def shop_off_all_(bot: Bot, event: GroupMessageEvent):
    """坊市清空"""
    bot, send_group_id = await assign_bot(bot=bot, event=event)
    isUser, user_info, msg = check_user(event)
    if not isUser:
        await handle_send(bot, event, msg)
        await shop_off_all.finish()
    group_id = str(event.group_id)
    shop_data = get_shop_data(group_id)
    if shop_data[group_id] == {}:
        msg = "坊市目前空空如也！"
        await handle_send(bot, event, msg)
        await shop_off_all.finish()

    msg = "正在清空,稍等！"
    await handle_send(bot, event, msg)

    list_msg = []
    msg = ""
    num = len(shop_data[group_id])
    for x in range(num):
        x = num - x
        if shop_data[group_id][str(x)]['user_id'] == 0:  # 这么写为了防止bot.send发送失败，不结算
            msg += f"成功下架系统物品：{shop_data[group_id][str(x)]['goods_name']}!\n"
            del shop_data[group_id][str(x)]
            save_shop(shop_data)
        else:
            sql_message.send_back(shop_data[group_id][str(x)]['user_id'], shop_data[group_id][str(x)]['goods_id'],
                                  shop_data[group_id][str(x)]['goods_name'],
                                  shop_data[group_id][str(x)]['goods_type'], shop_data[group_id][str(x)]['stock'])
            msg += f"成功下架{shop_data[group_id][str(x)]['user_name']}的{shop_data[group_id][str(x)]['stock']}个{shop_data[group_id][str(x)]['goods_name']}!\n"
            del shop_data[group_id][str(x)]
            save_shop(shop_data)
    shop_data[group_id] = reset_dict_num(shop_data[group_id])
    save_shop(shop_data)
    list_msg.append(
                    {"type": "node", "data": {"name": "执行清空坊市ing", "uin": bot.self_id,
                                              "content": msg}})
    try:
        await send_msg_handler(bot, event, list_msg)
    except ActionFailed:
        await handle_send(bot, event, msg)
    await shop_off_all.finish()


def reset_dict_num(dict_):
    i = 1
    temp_dict = {}
    for k, v in dict_.items():
        temp_dict[i] = v
        temp_dict[i]['编号'] = i
        i += 1
    return temp_dict


def get_user_auction_id_list():
    user_auctions = config['user_auctions']
    user_auction_id_list = []
    for auction in user_auctions:
        for k, v in auction.items():
            user_auction_id_list.append(v['id'])
    return user_auction_id_list

def get_auction_id_list():
    auctions = config['auctions']
    auction_id_list = []
    for k, v in auctions.items():
        auction_id_list.append(v['id'])
    return auction_id_list

def get_user_auction_price_by_id(id):
    user_auctions = config['user_auctions']
    user_auction_info = None
    for auction in user_auctions:
        for k, v in auction.items():
            if int(v['id']) == int(id):
                user_auction_info = v
                break
        if user_auction_info:
            break
    return user_auction_info

def get_auction_price_by_id(id):
    auctions = config['auctions']
    auction_info = None
    for k, v in auctions.items():
        if int(v['id']) == int(id):
            auction_info = v
            break
    return auction_info


def is_in_groups(event: GroupMessageEvent):
    return str(event.group_id) in groups


def get_auction_msg(auction_id):
    item_info = items.get_data_by_item_id(auction_id)
    _type = item_info['type']
    msg = None
    if _type == "装备":
        if item_info['item_type'] == "防具":
            msg = get_armor_info_msg(auction_id, item_info)
        if item_info['item_type'] == '法器':
            msg = get_weapon_info_msg(auction_id, item_info)

    if _type == "技能":
        if item_info['item_type'] == '神通':
            msg = f"{item_info['level']}-{item_info['name']}:\n"
            msg += f"效果：{get_sec_msg(item_info)}"
        if item_info['item_type'] == '功法':
            msg = f"{item_info['level']}-{item_info['name']}\n"
            msg += f"效果：{get_main_info_msg(auction_id)[1]}"
        if item_info['item_type'] == '辅修功法': #辅修功法10
            msg = f"{item_info['level']}-{item_info['name']}\n"
            msg += f"效果：{get_sub_info_msg(auction_id)[1]}"
            
    if _type == "神物":
        msg = f"{item_info['name']}\n"
        msg += f"效果：{item_info['desc']}"

    if _type == "丹药":
        msg = f"{item_info['name']}\n"
        msg += f"效果：{item_info['desc']}"

    return msg

async def check_trade_data_dir():
    """检查交易数据文件夹"""
    if not TRADE_DATA_PATH.exists():
        TRADE_DATA_PATH.mkdir(parents=True)
        logger.info(f"创建交易数据目录: {TRADE_DATA_PATH}")

# 在机器人启动时调用
check_trade_data_dir()
