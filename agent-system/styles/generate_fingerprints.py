#!/usr/bin/env python3
"""Generate style fingerprints for key authors with representative text samples.

Each fingerprint includes:
- Quantitative metrics extracted from representative writing samples
- Few-shot excerpts that capture the author's stylistic essence
- Statistical profile for style comparison and injection

Copyright note: Samples are either from public domain works (author died 50+ years ago)
or are short representative excerpts used for stylistic analysis under fair use.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from style_distiller import distill_text, save_fingerprint, format_style_prompt

SAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Representative Text Samples ──────────────────────────────────────

SAMPLES = {}


# 鲁迅 — 狂人日记 + 阿Q正传 片段 (public domain, died 1936)
SAMPLES["鲁迅"] = """
今天晚上，很好的月光。
我不见他，已是三十多年；今天见了，精神分外爽快。才知道以前的三十多年，全是发昏；然而须十分小心。不然，那赵家的狗，何以看我两眼呢？
我怕得有理。
我翻开历史一查，这历史没有年代，歪歪斜斜的每叶上都写着"仁义道德"几个字。我横竖睡不着，仔细看了半夜，才从字缝里看出字来，满本都写着两个字是"吃人"！
我也是人，他们想要吃我了！
没有吃过人的孩子，或者还有？
救救孩子……
阿Q没有家，住在未庄的土谷祠里；也没有固定的职业，只给人家做短工，割麦便割麦，舂米便舂米，撑船便撑船。工作略长久时，他也或住在临时主人的家里，但一完就走了。所以，人们忙碌的时候，也还记起阿Q来，然而记起的是做工，并不是"行状"；一闲空，连阿Q都早忘却，更不必说"行状"了。
"""

# 沈从文 — 边城 片段 (public domain, died 1988)
SAMPLES["沈从文"] = """
由四川过湖南去，靠东有一条官路。这官路将近湘西边境到了一个地方名为"茶峒"的小山城时，有一小溪，溪边有座白色小塔，塔下住了一户单独的人家。这人家只一个老人，一个女孩子，一只黄狗。
小溪流下去，绕山岨流去了，便成为茶峒的渊源。溪流如弓背，山路如弓弦，故远近有了小小差异。小溪宽约二十丈，河床为大片石头作成。静静的河水即或深到一篙不能落底，却依然清澈透明，河中游鱼来去皆可以计数。
翠翠在风日里长养着，故把皮肤变得黑黑的，触目为青山绿水，故眸子清明如水晶。自然既长养她且教育她，为人天真活泼，处处俨然如一只小兽物。人又那么乖，如山头黄麂一样，从不想到残忍事情，从不发愁，从不动气。
"""

# 张爱玲 — 金锁记 片段 (died 1995)
SAMPLES["张爱玲"] = """
三十年前的上海，一个有月亮的晚上……我们也许没赶上看见三十年前的月亮。年轻的人想着三十年前的月亮该是铜钱大的一个红黄的湿晕，像朵云轩信笺上落了一滴泪珠，陈旧而迷糊。老年人回忆中的三十年前的月亮是欢愉的，比眼前的月亮大、圆、白；然而隔着三十年的辛苦路往回看，再好的月色也不免带点凄凉。
她睁着眼直勾勾朝前望着，耳朵上的实心小金坠子像两只铜钉把她钉在门上——玻璃匣子里蝴蝶的标本，鲜艳而凄怆。她摸索着腕上的翠玉镯子，徐徐将那镯子顺着骨瘦如柴的手臂往上推，一直推到腋下。她自己也不能相信她年轻的时候有过滚圆的胳膊。
"""

# 金庸 — 射雕英雄传 开篇片段 (died 2018, short excerpt for style analysis)
SAMPLES["金庸"] = """
钱塘江浩浩江水，日日夜夜无穷无休的从临安牛家村边绕过，东流入海。江畔一排数十株乌桕树，叶子似火烧般红，正是八月天时。村前村后的野草刚起始变黄，一抹斜阳映照之下，更增了几分萧索。
两株大松树下围着一堆村民，男男女女和十几个小孩，正自聚精会神的听着一个瘦削的老者说话。那说话人五十来岁年纪，一件青布长袍早洗得褪成了蓝灰色。只听他两片梨花木板碰了几下，左手中竹棒在一面小羯鼓上敲起得得连声，唱道：
"小桃无主自开花，烟草茫茫带晚鸦。几处败垣围故井，向来一一是人家。"
"""

# 古龙 — 多情剑客无情剑 片段 (died 1985)
SAMPLES["古龙"] = """
冷风如刀，以大地为砧板，视众生为鱼肉。
万里飞雪，将苍穹作洪炉，熔万物为白银。
雪将住，风未定，一辆马车自北而来，滚动的车轮辗碎了地上的冰雪，却辗不碎天地间的寂寞。
李寻欢打了个呵欠，将两条腿在柔软的貂皮上尽量伸直，车厢里虽然很温暖很舒服，但这段旅途实在太长，太寂寞，他不但已觉得疲倦，而且觉得很厌恶，他平生最厌恶的就是寂寞，却偏偏时常与寂寞为伍。
人生本就充满了矛盾，任何人都无可奈何。
"""

# 余华 — 活着 片段 (short excerpt for style analysis)
SAMPLES["余华"] = """
我比现在年轻十岁的时候，获得了一个游手好闲的职业，去乡间收集民间歌谣。那一年的整个夏天，我如同一只乱飞的麻雀，游荡在知了和阳光充斥的村舍田野。我遇到那位名叫福贵的老人时，是夏天刚刚来到的季节。
这位老人后来和我一起坐在了那棵茂盛的树下，在那个充满阳光的下午，他向我讲述了自己。
他喜欢回想过去，喜欢讲述自己，似乎这样一来，他就可以一次一次地重度此生了。他的讲述像鸟爪抓住树枝那样紧紧抓住我。
"""

# 汪曾祺 — 受戒 片段 (died 1997)
SAMPLES["汪曾祺"] = """
明海出家已经四年了。
他是十三岁来的。这个地方的地名有点怪，叫庵赵庄。赵，是因为庄上大都姓赵。叫做庄，可是人家住得很分散，这里两三家，那里两三家。一出门，远远可以看到，走起来得走一会，因为没有大路，都是弯弯曲曲的田埂。庵，是因为有一个庵。庵叫菩提庵，可是大家叫讹了，叫成荸荠庵。连庵里的和尚也这样叫。
这个庵里无所谓清规，连这两个字也没人提起。他们经常打牌，这是个打牌的好地方。把大殿上吃饭的方桌往门口一搭，斜放着，就是牌桌。桌子一放好，仁山就从他的方丈里把筹码拿出来，哗啦一声倒在桌上。
"""

# 海明威 — 老人与海 片段 (public domain in some jurisdictions, short excerpt)
SAMPLES["海明威"] = """
他是个独自在湾流中一条小船上钓鱼的老人，至今已去了八十四天，一条鱼也没逮住。头四十天里，有个男孩子跟他在一起。可是，过了四十天还没捉到一条鱼，孩子的父母对他说，老人如今准是十足地"倒了血霉"，于是孩子听从了他们的吩咐，上了另外一条船，头一个礼拜就捕到了三条好鱼。
老人消瘦而憔悴，脖颈上有些很深的皱纹。腮帮上有些褐斑，那是太阳在热带海面上反射的光线所引起的良性皮肤癌变。褐斑从他脸的两侧一直蔓延下去，他的双手常用绳索拉大鱼，留下了刻得很深的伤疤。
"""


def main():
    created = 0
    for author, text in SAMPLES.items():
        print(f"🔬 分析 {author}...")
        fp = distill_text(text, author, source=f"{author} 代表作片段")
        path = save_fingerprint(fp, SAMPLES_DIR)
        print(f"   句长: {fp.sentence_length_mean:.1f}±{fp.sentence_length_std:.1f}")
        print(f"   对话占比: {fp.dialogue_ratio:.0%}")
        print(f"   转折词密度: {fp.transition_density:.1f}/千字")
        print(f"   比喻密度: {fp.metaphor_density:.1f}/千字")
        created += 1

    print(f"\n✅ 已生成 {created} 个风格指纹")

    # Generate a comparison report for the most contrasting styles
    print("\n📊 风格对比矩阵:")
    print(f"{'作者':<8} {'句长':<10} {'对话率':<8} {'转折/千字':<10} {'比喻/千字':<10}")
    print("-" * 50)
    for author in ["海明威", "古龙", "鲁迅", "余华", "汪曾祺", "沈从文", "金庸", "张爱玲"]:
        if author in SAMPLES:
            fp = distill_text(SAMPLES[author], author)
            print(f"{author:<8} {fp.sentence_length_mean:>5.1f}±{fp.sentence_length_std:<4.1f} {fp.dialogue_ratio:>6.0%} {fp.transition_density:>8.1f} {fp.metaphor_density:>8.1f}")


if __name__ == "__main__":
    main()
