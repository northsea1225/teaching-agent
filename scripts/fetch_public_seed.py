from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
import ssl
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import zipfile
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTERNAL_ROOT = Path(r"E:\teaching-agent_resources\public_seed")
TARGET_ROOT = DEFAULT_EXTERNAL_ROOT if DEFAULT_EXTERNAL_ROOT.parent.exists() else PROJECT_ROOT / "data" / "public_seed"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class DirectDownloadSource:
    category: str
    name: str
    url: str
    extract_zip: bool = False


@dataclass(frozen=True)
class AttachmentPageSource:
    category: str
    name: str
    page_url: str
    suffixes: tuple[str, ...]


@dataclass(frozen=True)
class TextPageSource:
    category: str
    name: str
    url: str


DIRECT_DOWNLOADS: tuple[DirectDownloadSource, ...] = (
    DirectDownloadSource(
        category="high_school",
        name="普通高中课程方案和课程标准_2017版2020修订",
        url="http://www.moe.gov.cn/srcsite/A26/s8001/202006/W020200603315372317586.zip",
        extract_zip=True,
    ),
)


ATTACHMENT_PAGES: tuple[AttachmentPageSource, ...] = (
    AttachmentPageSource(
        category="compulsory_education",
        name="义务教育课程方案和课程标准_2022版",
        page_url="https://www.ahjx.gov.cn/OpennessContent/show/2383663.html",
        suffixes=(".pdf",),
    ),
    AttachmentPageSource(
        category="higher_education",
        name="普通高等学校本科专业类教学质量国家标准",
        page_url="https://jwc.llu.edu.cn/info/1954/8545.htm",
        suffixes=(".pdf",),
    ),
    AttachmentPageSource(
        category="higher_education",
        name="普通高等学校本科专业类教学质量国家标准_华侨大学镜像",
        page_url="https://jwc.hqu.edu.cn/info/1063/8565.htm",
        suffixes=(".pdf",),
    ),
)


TEXT_PAGES: tuple[TextPageSource, ...] = (
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程方案和课程标准_2022版_教育部发布",
        url="https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/202204/t20220421_620068.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程方案和课程标准_2022版_政府网解读",
        url="https://www.gov.cn/xinwen/2022-04/22/content_5686606.htm",
    ),
    TextPageSource(
        category="preschool",
        name="3-6岁儿童学习与发展指南_解读",
        url="https://www.moe.gov.cn/jyb_xwfb/s5148/201210/t20121017_143353.html",
    ),
    TextPageSource(
        category="high_school",
        name="普通高中课程方案和课程标准_教育部解读",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/jyzt_2020n/2020_zt03/zydt/zydt_dfdt/202006/t20200604_462559.html",
    ),
    TextPageSource(
        category="vocational",
        name="职业教育专业目录_2021",
        url="https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/202103/t20210322_521664.html",
    ),
    TextPageSource(
        category="vocational",
        name="新版职业教育专业教学标准_答记者问",
        url="https://www.moe.gov.cn/jyb_xwfb/s271/202502/t20250211_1178747.html",
    ),
    TextPageSource(
        category="vocational",
        name="新版职业教育专业目录_答记者问",
        url="https://www.moe.gov.cn/jyb_xwfb/s271/202103/t20210322_521662.html",
    ),
    TextPageSource(
        category="vocational",
        name="新版职业教育专业简介公告",
        url="https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/A07/202209/t20220907_659058.html",
    ),
    TextPageSource(
        category="vocational",
        name="新版职业教育专业简介发布",
        url="https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/202209/t20220907_659056.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家高等教育智慧教育平台_帮助",
        url="https://higher.smartedu.cn/help",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育公共服务平台_用户总量突破1_78亿",
        url="https://www.moe.gov.cn/fbh/live/2025/77791/mtbd/202512/t20251231_1425330.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台_AI学习专栏",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2024/2024_zt05/mtbd/202404/t20240401_1123367.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="国家中小学智慧教育平台_浏览量超400亿次",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202405/t20240521_1131711.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="国家中小学智慧教育平台_在线教研栏目上线",
        url="https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/202403/t20240328_1122884.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程方案落实_王海霞解读",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/zjwz/202204/t20220421_620112.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程标准发布_人民网",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220421_620301.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程标准发布_中国青年报",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220422_620465.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程标准发布_北京青年报_标准",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220422_620519.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程标准发布_北京青年报_方案",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220422_620518.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程标准发布_齐鲁网",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220422_620531.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程标准发布_教育部普法网",
        url="https://qspfw.moe.gov.cn/html/hotnews/20220421/19446.html",
    ),
    TextPageSource(
        category="higher_education",
        name="国家高等教育智慧教育平台_创课平台上线",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202304/t20230412_1055330.html",
    ),
    TextPageSource(
        category="higher_education",
        name="我国慕课上线超7_68万门",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202404/t20240403_1123746.html",
    ),
    TextPageSource(
        category="higher_education",
        name="我国慕课数量和学习人数均居世界第一",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202412/t20241217_1167307.html",
    ),
    TextPageSource(
        category="higher_education",
        name="普通高等学校本科专业类教学质量国家标准_说明",
        url="https://meo.dufe.edu.cn/content_88808.html",
    ),
    TextPageSource(
        category="platforms",
        name="教育数字化战略行动实施三年成效综述",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202504/t20250417_1187747.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台累计注册用户突破1亿",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2024/2024_zt02/mtbd/202401/t20240126_1112602.html",
    ),
    TextPageSource(
        category="preschool",
        name="学前有法善育有规",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt09/jztth/202507/t20250711_1197296.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程标准修订完成_主要有哪些变化",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220421_620258.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课程方案和课程标准审议审核情况",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/sfcl/202204/t20220421_620071.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="义务教育课标及课程方案作出修订_中国网",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220422_620468.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="新版义务教育课程方案和课程标准发布_艺术课程调整",
        url="https://www.moe.gov.cn/fbh/live/2022/54382/mtbd/202204/t20220421_620254.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="推进提升国家中小学智慧教育平台建设应用",
        url="https://www.moe.gov.cn/fbh/live/2024/55785/mtbd/202401/t20240129_1113180.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="国家中小学智慧教育平台注册用户达1亿人",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2024/2024_zt02/mtbd/202401/t20240126_1112610.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="国家中小学智慧教育平台覆盖教材版本增至565册",
        url="https://www.moe.gov.cn/fbh/live/2024/55785/mtbd/202401/t20240126_1112623.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="推进教育数字化战略行动实现中小学平台提升",
        url="https://www.moe.gov.cn/fbh/live/2024/55785/mtbd/202401/t20240126_1112590.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="全国中小学互联网接入率达到100_澎湃",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230209_1043202.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="全国中小学互联网接入率达到100_人民网",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230209_1043212.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="中小学全部接入互联网智慧高教平台覆盖166个国家",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230209_1043184.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="基础教育优质均衡扩优提质新闻发布会",
        url="https://www.moe.gov.cn/fbh/live/2023/55484/mtbd/202308/t20230831_1077262.html",
    ),
    TextPageSource(
        category="compulsory_education",
        name="建议降低英语教学比重_教育部答复",
        url="https://dxs.moe.gov.cn/zx/a/kskt_yy/220929/1816063.shtml",
    ),
    TextPageSource(
        category="preschool",
        name="保障幼有所育学前教育有法可依",
        url="https://www.moe.gov.cn/fbh/live/2024/56271/mtbd/202411/t20241112_1162432.html",
    ),
    TextPageSource(
        category="preschool",
        name="加强幼儿园办学资质审核",
        url="https://www.moe.gov.cn/fbh/live/2024/56271/mtbd/202411/t20241111_1162278.html",
    ),
    TextPageSource(
        category="preschool",
        name="学前儿童入园不得组织考试或测试",
        url="https://www.moe.gov.cn/fbh/live/2024/56271/mtbd/202411/t20241111_1162276.html",
    ),
    TextPageSource(
        category="preschool",
        name="坚决防止和纠正学前教育小学化倾向",
        url="https://www.moe.gov.cn/fbh/live/2024/56271/mtbd/202411/t20241112_1162507.html",
    ),
    TextPageSource(
        category="preschool",
        name="幼儿园应以游戏为基本活动",
        url="https://www.moe.gov.cn/fbh/live/2024/56271/mtbd/202411/t20241111_1162279.html",
    ),
    TextPageSource(
        category="preschool",
        name="学前三年毛入园率达到91_1",
        url="https://www.moe.gov.cn/fbh/live/2024/56271/mtbd/202411/t20241111_1162331.html",
    ),
    TextPageSource(
        category="preschool",
        name="学前教育法推动教育法治建设突破",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt01/sdxw/shidaxinwen/202501/t20250111_1175252.html",
    ),
    TextPageSource(
        category="preschool",
        name="幼儿园工作人员应进行背景查询和健康检查",
        url="https://www.moe.gov.cn/fbh/live/2024/56271/mtbd/202411/t20241112_1162443.html",
    ),
    TextPageSource(
        category="preschool",
        name="学前教育步入有专门法可依新阶段",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202411/t20241112_1162400.html",
    ),
    TextPageSource(
        category="preschool",
        name="尊重教育科学_对学前教育法的感悟与实践",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt09/jztth/202507/t20250711_1197283.html",
    ),
    TextPageSource(
        category="preschool",
        name="贯彻学前教育法把好学前教育时代路向",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt09/jztls/202506/t20250626_1195590.html",
    ),
    TextPageSource(
        category="preschool",
        name="海南构建学前教育优质发展新图景",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt09/tzhxf/202505/t20250520_1191268.html",
    ),
    TextPageSource(
        category="high_school",
        name="普通高中课程方案公布_劳动为必修课",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/jyzt_2020n/2020_zt03/zydt/zydt_dfdt/202006/t20200604_462559.html",
    ),
    TextPageSource(
        category="high_school",
        name="普通高中英语日语俄语教学大纲通知",
        url="https://www.moe.gov.cn/jyb_xxgk/gk_gbgg/moe_0/moe_7/moe_445/tnull_6324.html",
    ),
    TextPageSource(
        category="high_school",
        name="普通高中语文等七科教学大纲通知",
        url="https://www.moe.gov.cn/jyb_xxgk/gk_gbgg/moe_0/moe_8/moe_25/tnull_237.html",
    ),
    TextPageSource(
        category="high_school",
        name="依托特等奖教材上好每节英语课",
        url="https://www.moe.gov.cn/jyb_xwfb/moe_2082/2024/2024_zl04/202404/t20240409_1124630.html",
    ),
    TextPageSource(
        category="vocational",
        name="教育部发布758项新版职业教育专业教学标准_新华网",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt08/mtbd/202505/t20250509_1189846.html",
    ),
    TextPageSource(
        category="vocational",
        name="覆盖1349个专业_新版职业教育专业简介",
        url="https://fx.xwapp.moe.gov.cn/article/202209/6317e830b2476a6364d5daf1.html",
    ),
    TextPageSource(
        category="higher_education",
        name="国家高等教育智慧教育平台用户覆盖166个国家_人民网",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230209_1043214.html",
    ),
    TextPageSource(
        category="higher_education",
        name="国家高等教育智慧教育平台用户覆盖166个国家_北京时间",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230210_1043424.html",
    ),
    TextPageSource(
        category="higher_education",
        name="高等教育数字化工作进展情况",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/cailiao/202302/t20230209_1043112.html",
    ),
    TextPageSource(
        category="higher_education",
        name="慕课学习人次达9_79亿",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202301/t20230103_1037816.html",
    ),
    TextPageSource(
        category="higher_education",
        name="十四五教育强国推进工程中西部投入情况",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202407/t20240708_1140031.html",
    ),
    TextPageSource(
        category="higher_education",
        name="吴岩出席2025世界数字教育大会平行会议",
        url="https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/moe_1485/202505/t20250515_1190753.html",
    ),
    TextPageSource(
        category="higher_education",
        name="九部门加快建设新形态国家数字大学",
        url="https://www.moe.gov.cn/fbh/live/2025/56808/mtbd/202504/t20250416_1187640.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台国际版覆盖全球120个国家和地区",
        url="https://www.moe.gov.cn/fbh/live/2025/56916/mtbd/202505/t20250512_1190190.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台成为世界第一大数字化中心和平台",
        url="https://www.moe.gov.cn/fbh/live/2025/56916/mtbd/202505/t20250512_1190193.html",
    ),
    TextPageSource(
        category="platforms",
        name="2025世界数字教育大会多项成果将发布",
        url="https://www.moe.gov.cn/fbh/live/2025/56916/mtbd/202505/t20250512_1190218.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台累计注册用户突破1亿_新华网客户端",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2024/2024_zt02/yw/202401/t20240129_1113233.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台国际版将在2024世界数字教育大会发布",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2024/2024_zt02/mtbd/202401/t20240126_1112608.html",
    ),
    TextPageSource(
        category="platforms",
        name="以创新应用引领数字教育变革",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2024/2024_zt05/mtbd/202404/t20240402_1123567.html",
    ),
    TextPageSource(
        category="platforms",
        name="我国基本建成世界第一大教育教学资源库_中青报",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230210_1043392.html",
    ),
    TextPageSource(
        category="platforms",
        name="我国基本建成世界第一大教育教学资源库_中青报客户端",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230209_1043216.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台已有4万余条中小学资源和2_7万门慕课",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2606/2023/cfh_0209/baodao/202302/t20230210_1043422.html",
    ),
    TextPageSource(
        category="platforms",
        name="为世界数字教育贡献中国智慧",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202309/t20230914_1080237.html",
    ),
    TextPageSource(
        category="platforms",
        name="智慧教育国家队赋能数字化变革",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202303/t20230328_1053044.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家教育数字化战略行动2025年部署会召开",
        url="https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/moe_1485/202503/t20250328_1185222.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育平台已覆盖全球学习者并上线国际版专区",
        url="https://www.moe.gov.cn/fbh/live/2025/56916/mtbd/202505/t20250512_1190190.html",
    ),
    TextPageSource(
        category="platforms",
        name="国家智慧教育公共服务平台访客量超过19_2亿人次",
        url="https://www.moe.gov.cn/jyb_xwfb/s5147/202306/t20230625_1065586.html",
    ),
    TextPageSource(
        category="preschool",
        name="甘肃推动学前教育法护航美好童年",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt09/tzhxf/202505/t20250520_1191247.html",
    ),
    TextPageSource(
        category="preschool",
        name="湖南推动构建安全优质学前教育公共服务体系",
        url="https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/2025/2025_zt09/tzhxf/202505/t20250520_1191284.html",
    ),
    TextPageSource(
        category="vocational",
        name="新版职业教育专业目录新在何处",
        url="https://dxs.moe.gov.cn/zx/a/jj/221010/1817626.shtml",
    ),
)


def sanitize_name(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", name).strip() or "resource"


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except ssl.SSLCertVerificationError:
        insecure_context = ssl.create_default_context()
        insecure_context.check_hostname = False
        insecure_context.verify_mode = ssl.CERT_NONE
        with urlopen(request, timeout=60, context=insecure_context) as response:
            return response.read()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def infer_filename(url: str, fallback_stem: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if name:
        return sanitize_name(unescape(name))
    return f"{sanitize_name(fallback_stem)}.bin"


def looks_like_html(payload: bytes) -> bool:
    probe = payload[:512].decode("utf-8", errors="ignore").lower()
    return "<html" in probe or "<!doctype html" in probe or "<head" in probe


def strip_html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>|</div>|</li>|</tr>|</h[1-6]>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_zip_file(zip_path: Path, target_dir: Path) -> list[str]:
    extracted: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            raw_name = info.filename
            try:
                raw_name = raw_name.encode("cp437").decode("gbk")
            except Exception:
                pass
            filename = sanitize_name(Path(raw_name).name)
            if not filename:
                continue
            output_path = target_dir / filename
            with archive.open(info) as src, output_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(str(output_path))
    return extracted


def discover_attachment_urls(page_url: str, suffixes: tuple[str, ...]) -> list[str]:
    html = fetch_bytes(page_url).decode("utf-8", errors="ignore")
    urls: list[str] = []
    seen: set[str] = set()
    hrefs = re.findall(r"""(?i)(?:href|src)\s*=\s*["']([^"'#]+)["']""", html)
    plain_urls = re.findall(r"""https?://[^\s"'<>]+""", html)
    for candidate in [*hrefs, *plain_urls]:
        full_url = urljoin(page_url, unescape(candidate))
        lowered = full_url.lower()
        if not lowered.startswith(("http://", "https://")):
            continue
        if not lowered.endswith(suffixes):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        urls.append(full_url)
    return urls


def download_direct(source: DirectDownloadSource, summary: list[dict[str, object]]) -> None:
    category_dir = ensure_dir(TARGET_ROOT / source.category)
    payload = fetch_bytes(source.url)
    filename = infer_filename(source.url, source.name)
    output_path = category_dir / filename
    output_path.write_bytes(payload)
    extracted_files: list[str] = []
    if source.extract_zip and output_path.suffix.lower() == ".zip":
        extracted_dir = category_dir / f"{output_path.stem}_extracted"
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir, ignore_errors=True)
        ensure_dir(extracted_dir)
        extracted_files = extract_zip_file(output_path, extracted_dir)
    summary.append(
        {
            "type": "direct",
            "name": source.name,
            "url": source.url,
            "saved_to": str(output_path),
            "extracted_files": extracted_files,
        }
    )


def download_attachments(source: AttachmentPageSource, summary: list[dict[str, object]]) -> None:
    category_dir = ensure_dir(TARGET_ROOT / source.category)
    discovered = discover_attachment_urls(source.page_url, source.suffixes)
    if not discovered:
        raise RuntimeError("No attachment URLs discovered on page")
    saved: list[str] = []
    extracted_files: list[str] = []
    for url in discovered:
        payload = fetch_bytes(url)
        if looks_like_html(payload):
            continue
        filename = infer_filename(url, source.name)
        output_path = category_dir / filename
        if output_path.exists():
            stem = output_path.stem
            suffix = output_path.suffix
            output_path = category_dir / f"{stem}_{len(saved)+1}{suffix}"
        output_path.write_bytes(payload)
        saved.append(str(output_path))
        if output_path.suffix.lower() == ".zip":
            extracted_dir = category_dir / f"{output_path.stem}_extracted"
            if extracted_dir.exists():
                shutil.rmtree(extracted_dir, ignore_errors=True)
            ensure_dir(extracted_dir)
            extracted_files.extend(extract_zip_file(output_path, extracted_dir))
    summary.append(
        {
            "type": "attachment_page",
            "name": source.name,
            "page_url": source.page_url,
            "downloaded_files": saved,
            "extracted_files": extracted_files,
        }
    )


def download_text_page(source: TextPageSource, summary: list[dict[str, object]]) -> None:
    category_dir = ensure_dir(TARGET_ROOT / source.category)
    html = fetch_bytes(source.url).decode("utf-8", errors="ignore")
    text = strip_html_to_text(html)
    output_path = category_dir / f"{sanitize_name(source.name)}.txt"
    output_path.write_text(text, encoding="utf-8")
    summary.append(
        {
            "type": "text_page",
            "name": source.name,
            "url": source.url,
            "saved_to": str(output_path),
            "chars": len(text),
        }
    )


def main() -> None:
    ensure_dir(TARGET_ROOT)
    summary: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    for source in DIRECT_DOWNLOADS:
        try:
            download_direct(source, summary)
        except Exception as exc:
            errors.append({"name": source.name, "url": source.url, "error": str(exc)})

    for source in ATTACHMENT_PAGES:
        try:
            download_attachments(source, summary)
        except Exception as exc:
            errors.append({"name": source.name, "url": source.page_url, "error": str(exc)})

    for source in TEXT_PAGES:
        try:
            download_text_page(source, summary)
        except Exception as exc:
            errors.append({"name": source.name, "url": source.url, "error": str(exc)})

    manifest_path = TARGET_ROOT / "download_manifest.json"
    manifest_path.write_text(
        json.dumps({"items": summary, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"target_root": str(TARGET_ROOT), "items": len(summary), "errors": len(errors)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
