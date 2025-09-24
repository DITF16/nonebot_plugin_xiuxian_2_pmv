from ..xiuxian_utils.item_json import Items
from random import shuffle
from collections import Counter

mix_config = Items().get_data_by_item_type(['合成丹药'])
mix_configs = {}
for k, v in mix_config.items():
    mix_configs[k] = v['elixir_config']

yonhudenji = 0
Llandudno_info = {
    "max_num": 10,
    "rank": 20
}


async def check_mix(elixir_config):
    is_mix = False
    l_id = []
    # mix_configs = await get_mix_config()
    for k, v in mix_configs.items():  # 这里是丹药配方
        type_list = []
        for ek, ev in elixir_config.items():  # 这是传入的值判断
            # 传入的丹药config
            type_list.append(ek)
        formula_list = []
        for vk, vv in v.items():  # 这里是每个配方的值
            formula_list.append(vk)
        if sorted(type_list) == sorted(formula_list):  # key满足了
            flag = False
            for typek in type_list:
                if elixir_config[typek] >= v[typek]:
                    flag = True
                    continue
                else:
                    flag = False
                    break
            if flag:
                l_id.append(k)

            continue
        else:
            continue
    id = 0
    if l_id:
        is_mix = True
        id_config = {}
        for id in l_id:
            for k, v in mix_configs[id].items():
                id_config[id] = v
                break
        id = sorted(id_config.items(), key=lambda x: x[1], reverse=True)[0][0]  # 选出最优解

    return is_mix, id


async def get_mix_elixir_msg(yaocai):
    """只生成一个配方，找到第一个有效配方就返回"""
    for k, v in yaocai.items():  # 这里是用户所有的药材dict
        i = 1
        while i <= v['num'] and i <= 5:  # 尝试第一个药材为主药
            for kk, vv in yaocai.items():
                if kk == k:  # 相同的药材不能同时做药引
                    continue
                o = 1
                while o <= vv['num'] and o <= 5:
                    if await tiaohe(v, i, vv, o):  # 调和失败
                        o += 1
                        continue
                    else:
                        for kkk, vvv in yaocai.items():
                            p = 1
                            # 尝试加入辅药
                            while p <= vvv['num'] and p <= 5:
                                elixir_config = {}
                                zhuyao_type = str(v['主药']['type'])
                                zhuyao_power = v['主药']['power'] * i
                                elixir_config[zhuyao_type] = zhuyao_power
                                
                                fuyao_type = str(vvv['辅药']['type'])
                                fuyao_power = vvv['辅药']['power'] * p
                                elixir_config[fuyao_type] = fuyao_power
                                
                                is_mix, id_ = await check_mix(elixir_config)
                                if is_mix:  # 有可以合成的
                                    if i + o + p <= Llandudno_info["max_num"]:
                                        # 判断背包里药材是否足够(同个药材多种类型)
                                        if len({v["name"], vv["name"], vvv["name"]}) != 3:
                                            num_dict = Counter([*[v["name"]]*i, *[vv["name"]]*o, *[vvv["name"]]*p])
                                            if any(num_dict[yao["name"]] > yao["num"] for yao in [v, vv, vvv]):
                                                p += 1
                                                continue

                                        # 找到第一个有效配方，直接返回
                                        mix_elixir_msg = {}
                                        mix_elixir_msg['id'] = id_
                                        mix_elixir_msg['配方'] = elixir_config
                                        mix_elixir_msg['配方简写'] = f"主药{v['name']}{i}药引{vv['name']}{o}辅药{vvv['name']}{p}"
                                        mix_elixir_msg['主药'] = v['name']
                                        mix_elixir_msg['主药_num'] = i
                                        mix_elixir_msg['主药_level'] = v['level']
                                        mix_elixir_msg['药引'] = vv['name']
                                        mix_elixir_msg['药引_num'] = o
                                        mix_elixir_msg['药引_level'] = vv['level']
                                        mix_elixir_msg['辅药'] = vvv['name']
                                        mix_elixir_msg['辅药_num'] = p
                                        mix_elixir_msg['辅药_level'] = vvv['level']
                                        return mix_elixir_msg
                                    else:
                                        p += 1
                                        continue
                                else:
                                    p += 1
                                    continue
                    o += 1
            i += 1
    return {}  # 没有找到任何配方

async def absolute(x):
    if x >= 0:
        return x
    else:
        return -x


async def tiaohe(zhuyao_info, zhuyao_num, yaoyin_info, yaoyin_num):
    _zhuyao = zhuyao_info['主药']['h_a_c']['type'] * zhuyao_info['主药']['h_a_c']['power'] * zhuyao_num
    _yaoyin = yaoyin_info['药引']['h_a_c']['type'] * yaoyin_info['药引']['h_a_c']['power'] * yaoyin_num

    return await absolute(_zhuyao + _yaoyin) > yonhudenji


async def make_dict(old_dict):
    old_dict_key = list(old_dict.keys())
    shuffle(old_dict_key)
    if len(old_dict_key) >= 25:
        old_dict_key = old_dict_key[:25]
    new_dic = {}
    for key in old_dict_key:
        new_dic[key] = old_dict.get(key)
    return new_dic
