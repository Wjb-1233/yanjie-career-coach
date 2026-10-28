from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import Course, Scene, User
from app.features.scenes.taxonomy import LEGACY_CATEGORIES
from app.infrastructure.knowledge import KnowledgeDocument, knowledge_store


SCENES = [
    {
        "id": "scene-interview-01",
        "category": "交叉面 / 总监面",
        "title": "产品经理跨团队项目面试",
        "industry": "互联网与软件",
        "position": "产品经理",
        "role_name": "业务部门面试官",
        "difficulty": "进阶",
        "background": "一家成长型科技公司招聘产品经理，面试官关注结构化思考、跨团队协作与复盘能力。",
        "goal": "用 STAR 结构说明一次跨团队项目，并回应对结果不理想的追问。",
        "tags": ["STAR", "压力追问", "产品经理"],
        "opening_line": "先用两分钟介绍你最有挑战的一次跨团队协作。",
    },
    {
        "id": "scene-interview-02",
        "category": "技术一面",
        "title": "校园招聘项目经历面试",
        "industry": "互联网与软件",
        "position": "产品运营",
        "role_name": "业务面试官",
        "difficulty": "中级",
        "background": "应届生参加校园招聘，面试官希望了解其在校期间的项目贡献、协作方式和复盘能力。",
        "goal": "清楚说明项目背景、个人任务、关键行动和可验证结果，避免只讲团队成果。",
        "tags": ["校园招聘", "项目经历", "STAR"],
        "opening_line": "请选一个你最熟悉的项目，说明你具体负责了什么。",
    },
    {
        "id": "scene-interview-03",
        "category": "技术二面 / 复面",
        "title": "后端开发技术面试",
        "industry": "互联网与软件",
        "position": "Python 后端开发",
        "role_name": "技术面试官",
        "difficulty": "进阶",
        "background": "候选人应聘 Python 后端岗位，面试官关注技术取舍、故障定位和工程实践。",
        "goal": "按问题直接作答，再用真实项目经历说明方案、权衡依据与结果；不确定时清楚说明假设。",
        "tags": ["Python", "技术追问", "项目实践"],
        "opening_line": "请介绍一个你参与过的后端项目，以及其中最关键的一项技术决策。",
    },
    {
        "id": "scene-interview-04",
        "category": "HR 初面",
        "title": "HR 薪资与求职意向沟通",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "招聘 HR",
        "difficulty": "入门",
        "background": "候选人进入招聘沟通阶段，HR 需要确认求职动机、到岗时间和薪酬预期。",
        "goal": "表达真实意向与合理依据，礼貌确认薪酬结构和岗位发展信息。",
        "tags": ["HR 面", "薪资预期", "求职动机"],
        "opening_line": "你为什么选择这个岗位？对薪酬有什么预期？",
    },
    {
        "id": "scene-interview-05",
        "category": "交叉面 / 总监面",
        "title": "实习中的意见分歧",
        "industry": "互联网与软件",
        "position": "软件开发实习生",
        "role_name": "团队负责人",
        "difficulty": "中级",
        "background": "你在实习项目中与同事对实现方式有不同看法，面试官希望了解你如何沟通而不是简单争输赢。",
        "goal": "讲清分歧背景、你的判断依据、沟通过程和最终结果，突出个人行动。",
        "tags": ["团队协作", "冲突处理", "STAR"],
        "opening_line": "请讲一次你和团队成员意见不一致的经历，你当时具体怎么处理？",
    },
    {
        "id": "scene-interview-06",
        "category": "HR 初面",
        "title": "一次没有达到目标的项目复盘",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "校招面试官",
        "difficulty": "入门",
        "background": "面试官想了解候选人面对失败时是否能承担责任、识别原因并改进，而不是只归因于外部条件。",
        "goal": "用真实经历说明目标、偏差、自己的责任、采取的补救行动以及学到的经验。",
        "tags": ["失败复盘", "责任意识", "成长"],
        "opening_line": "请说一件你投入很多但结果未达到预期的事，你从中学到了什么？",
    },
    {
        "id": "scene-interview-07",
        "category": "技术二面 / 复面",
        "title": "面试官质疑你的项目贡献",
        "industry": "互联网与软件",
        "position": "Python 后端开发",
        "role_name": "技术主管",
        "difficulty": "进阶",
        "background": "候选人刚介绍完团队项目，面试官连续质疑所述成果是否主要由其他成员完成。",
        "goal": "在压力追问下保持冷静，区分团队成果与个人职责，并给出可核查的技术细节。",
        "tags": ["压力追问", "个人贡献", "技术证据"],
        "opening_line": "这些成果听起来都是团队完成的。你个人到底做了什么，能具体证明吗？",
    },
    {
        "id": "scene-interview-08",
        "category": "交叉面 / 总监面",
        "title": "经验不足时如何回应质疑",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "业务负责人",
        "difficulty": "中级",
        "background": "面试官指出候选人缺少正式工作经验，并担心入职后无法很快承担工作。",
        "goal": "承认客观差距，不编造经验，用已有实践、学习方式和可执行的上手计划回应顾虑。",
        "tags": ["经验不足", "压力应答", "学习能力"],
        "opening_line": "你没有做过我们这个岗位的正式工作，我为什么要冒险录用你？",
    },
    {
        "id": "scene-interview-09",
        "category": "交叉面 / 总监面",
        "title": "高压截止时间下的优先级判断",
        "industry": "互联网与软件",
        "position": "产品经理",
        "role_name": "部门总监",
        "difficulty": "进阶",
        "background": "项目临近上线，需求、质量和时间发生冲突，面试官要求候选人当场给出取舍方案并解释风险。",
        "goal": "在连续质疑中明确优先级、提出取舍依据、同步风险并给出备选方案。",
        "tags": ["时间压力", "优先级", "风险沟通"],
        "opening_line": "明天必须上线，但还有两个关键问题没解决。你现在决定先做什么？",
    },
    {
        "id": "scene-interview-10",
        "category": "技术一面",
        "title": "Python 接口超时故障排查",
        "industry": "互联网与软件",
        "position": "Python 后端开发",
        "role_name": "后端技术面试官",
        "difficulty": "中级",
        "background": "一个接口上线后响应时间明显变长，面试官希望听到有顺序的定位步骤和验证方法。",
        "goal": "先界定现象与影响，再说明指标、日志、数据库和依赖服务的排查顺序；明确无法确定时的假设。",
        "tags": ["Python", "故障排查", "性能"],
        "opening_line": "你的 Python 接口突然从 200 毫秒变成 3 秒，你会怎样排查？",
    },
    {
        "id": "scene-interview-11",
        "category": "技术一面",
        "title": "前端页面性能优化答辩",
        "industry": "互联网与软件",
        "position": "前端开发",
        "role_name": "前端技术面试官",
        "difficulty": "中级",
        "background": "面试官要求候选人解释一个页面加载缓慢的问题，并区分真实测量结果与推测。",
        "goal": "讲清性能指标、定位方法、优化动作与验证结果，避免泛泛罗列技术名词。",
        "tags": ["前端性能", "指标", "验证"],
        "opening_line": "如果一个页面首屏很慢，你会先看哪些数据，再决定怎么优化？",
    },
    {
        "id": "scene-interview-12",
        "category": "技术一面",
        "title": "数据分析项目方法追问",
        "industry": "数据服务",
        "position": "数据分析师",
        "role_name": "数据团队面试官",
        "difficulty": "入门",
        "background": "候选人介绍一份分析报告，面试官关注数据口径、异常值处理和结论是否得到证据支持。",
        "goal": "说明分析问题、数据来源、处理方法和结论边界；不把相关性说成因果性。",
        "tags": ["数据分析", "方法说明", "结论边界"],
        "opening_line": "请介绍一次你做过的数据分析，先说明问题和你采用的数据口径。",
    },
    {
        "id": "scene-interview-13",
        "category": "HRBP/HR 终面",
        "title": "提出有依据的期望薪资",
        "industry": "互联网与软件",
        "position": "软件开发工程师",
        "role_name": "招聘 HR",
        "difficulty": "中级",
        "background": "HR 询问候选人的期望薪资，并希望了解其考虑依据和可接受范围。",
        "goal": "基于岗位职责、个人能力和已知信息表达预期，同时保留讨论空间；不编造市场数据。",
        "tags": ["薪资预期", "依据表达", "谈判"],
        "opening_line": "你的期望薪资是多少？为什么认为这个数字合适？",
    },
    {
        "id": "scene-interview-14",
        "category": "HRBP/HR 终面",
        "title": "确认薪酬结构与试用期条件",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "招聘 HR",
        "difficulty": "入门",
        "background": "候选人收到口头薪酬说明，但固定工资、绩效、试用期和福利的计算方式还不清楚。",
        "goal": "礼貌地逐项确认薪酬构成和适用条件，复述双方已确认的信息。",
        "tags": ["薪酬结构", "试用期", "信息确认"],
        "opening_line": "我们的薪酬包含基本工资和绩效，你还有什么想确认的吗？",
    },
    {
        "id": "scene-interview-15",
        "category": "HRBP/HR 终面",
        "title": "多份录用机会中的薪资协商",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "招聘经理",
        "difficulty": "进阶",
        "background": "候选人同时在考虑两份录用机会，希望和更心仪的企业讨论薪酬与成长条件。",
        "goal": "如实表达意向和关注点，提出具体问题或请求，不虚构其他 offer 施压。",
        "tags": ["录用选择", "条件协商", "诚信沟通"],
        "opening_line": "我们已经给出正式 offer，你还有哪些条件需要讨论？",
    },
    {
        "id": "scene-general-motivation",
        "category": "HR 初面",
        "title": "为什么选择我们公司",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "招聘 HR",
        "difficulty": "入门",
        "background": "招聘 HR 想了解候选人对公司与岗位的认识，以及个人选择是否经过认真考虑。",
        "goal": "把了解过的公司与岗位事实、个人兴趣和可贡献之处连起来，不说空泛套话或编造信息。",
        "tags": ["求职动机", "岗位匹配", "真实表达"],
        "opening_line": "你为什么选择我们公司，而不是其他类似的企业？",
    },
    {
        "id": "scene-general-overtime",
        "category": "HRBP/HR 终面",
        "title": "如何回应加班安排",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "招聘经理",
        "difficulty": "进阶",
        "background": "面试官表示岗位可能经常加班，并提出加班没有额外补贴，观察候选人如何确认条件与表达边界。",
        "goal": "保持礼貌，先确认工作时长、安排与补偿政策，再清楚表达自己的考虑和可接受范围；不仓促承诺。",
        "tags": ["工作安排", "边界表达", "条件确认"],
        "opening_line": "我们这个岗位经常需要加班，而且没有额外加班费，你能接受吗？",
    },
    {
        "id": "scene-general-start-date",
        "category": "HR 初面",
        "title": "最早到岗时间怎么谈",
        "industry": "综合行业",
        "position": "应届毕业生",
        "role_name": "招聘 HR",
        "difficulty": "中级",
        "background": "企业希望尽快确定入职日期，但候选人还要完成毕业手续、当前工作交接或其他已确定安排。",
        "goal": "给出真实可执行的最早到岗日期、需要完成的事项和可协调空间，不做无法兑现的承诺。",
        "tags": ["到岗时间", "入职安排", "预期管理"],
        "opening_line": "如果我们决定录用你，你最早什么时候可以到岗？能不能再提前一些？",
    },
    {
        "id": "scene-stage-backend-basics", "category": "技术一面", "title": "Python 后端基础与接口设计",
        "industry": "互联网与软件", "position": "Python 后端开发", "role_name": "一面技术面试官", "difficulty": "入门",
        "background": "一面重点核实 Python 基础、HTTP 接口、数据库使用和候选人做过的基础开发任务。",
        "goal": "准确解释基础概念，并用自己完成的接口说明实现步骤和验证方式。",
        "tags": ["Python 基础", "接口设计", "技术一面"],
        "opening_line": "请介绍一个你亲自完成的接口，它接收什么输入、怎样处理、如何验证结果？",
    },
    {
        "id": "scene-stage-data-deep", "category": "技术二面 / 复面", "title": "数据分析方案复面",
        "industry": "数据服务", "position": "数据分析师", "role_name": "数据分析负责人", "difficulty": "进阶",
        "background": "复面围绕真实分析项目深入考察数据质量、指标口径、方法取舍和结论的业务影响。",
        "goal": "给出方法选择的依据、偏差控制与验证方法，说明结论适用边界。",
        "tags": ["分析方法", "指标口径", "复面"],
        "opening_line": "你如何证明项目结论不是数据口径变化或样本偏差造成的？",
    },
    {
        "id": "scene-stage-executive-product", "category": "大老板 / 高管终面", "title": "产品经理高管终面",
        "industry": "互联网与软件", "position": "产品经理", "role_name": "业务高管", "difficulty": "进阶",
        "background": "高管在最终面试中关注候选人对业务目标的判断、跨部门影响力和长期成长潜力。",
        "goal": "从业务价值、资源约束和风险三方面说明取舍，区分个人贡献与团队成果。",
        "tags": ["高管终面", "业务判断", "综合把关"],
        "opening_line": "如果资源只能支持你提出的两个方向中的一个，你会选哪个？为什么？",
    },
    {
        "id": "scene-stage-executive-backend", "category": "大老板 / 高管终面", "title": "后端开发高管终面",
        "industry": "互联网与软件", "position": "Python 后端开发", "role_name": "技术高管", "difficulty": "进阶",
        "background": "技术高管进行最终把关，关注复杂问题的判断、可靠性交付、协作方式和发展潜力。",
        "goal": "用真实经历说明技术决策如何服务业务目标，以及在风险和资源约束下如何负责。",
        "tags": ["高管终面", "技术判断", "协作潜力"],
        "opening_line": "如果业务要求快速上线，但你判断方案有明显稳定性风险，你会如何推动决策？",
    },
    {
        "id": "scene-stage-system-design", "category": "技术二面 / 复面", "title": "高并发接口的系统设计复面",
        "industry": "互联网与软件", "position": "Python 后端开发", "role_name": "后端架构面试官", "difficulty": "进阶",
        "background": "复面给出流量快速增长的接口场景，要求候选人说明容量估算、关键瓶颈、数据一致性与降级策略。",
        "goal": "先澄清约束，再提出分层方案，说明关键取舍、失败边界和验证指标。",
        "tags": ["系统设计", "高并发", "架构取舍"],
        "opening_line": "一个核心查询接口的流量预计增长十倍，你会先确认哪些约束，再怎样设计扩容方案？",
    },
    {
        "id": "scene-stage-algorithm-basics", "category": "技术一面", "title": "算法基础与复杂度说明",
        "industry": "互联网与软件", "position": "Python 后端开发", "role_name": "一面技术面试官", "difficulty": "中级",
        "background": "技术一面要求候选人讲清常见数据结构、时间复杂度，以及在简单业务问题中的选择依据。",
        "goal": "先解释思路和复杂度，再用具体输入说明边界条件，不把背诵答案当作实践经验。",
        "tags": ["算法基础", "复杂度", "技术一面"],
        "opening_line": "如果需要从大量记录中快速判断某个 ID 是否出现过，你会选什么数据结构？为什么？",
    },
    {
        "id": "scene-stage-hr-values", "category": "HRBP/HR 终面", "title": "职业选择与稳定性终面",
        "industry": "综合行业", "position": "应届毕业生", "role_name": "HRBP", "difficulty": "中级",
        "background": "HRBP 希望了解候选人的职业选择依据、对团队文化的期待和面对岗位变化时的考虑。",
        "goal": "结合真实经历说明价值观与发展规划，诚实表达可能影响稳定性的条件。",
        "tags": ["价值观", "稳定性", "职业规划"],
        "opening_line": "你希望未来两年在这个岗位获得什么？什么情况会让你重新考虑这份工作？",
    },
    {
        "id": "scene-foundation-logic", "category": "基础能力提升", "title": "把复杂问题讲清楚",
        "industry": "通用职场", "position": "应届求职者", "role_name": "项目面试官", "difficulty": "入门",
        "background": "面试官听完项目介绍后，仍不清楚结论、原因与结果，继续追问判断过程。",
        "goal": "先说结论，再按原因、行动、结果回答追问；每一轮保持前后逻辑一致。",
        "tags": ["逻辑性", "结论先行", "结构化表达"],
        "opening_line": "请用一句话说清你在项目中解决的核心问题，再解释你为何选择这个方案。",
    },
    {
        "id": "scene-foundation-appropriateness", "category": "基础能力提升", "title": "有分寸地表达不同意见",
        "industry": "通用职场", "position": "应届求职者", "role_name": "直属主管", "difficulty": "入门",
        "background": "主管提出一项你认为时间安排不合理的任务，你需要尊重对方并明确表达事实和边界。",
        "goal": "用事实说明影响，提出可执行的调整建议，保持尊重与清晰。",
        "tags": ["得体性", "边界表达", "尊重"],
        "opening_line": "这项任务明天就要交，你认为时间不够。你会怎么和我沟通？",
    },
    {
        "id": "scene-foundation-impact", "category": "基础能力提升", "title": "让观点更有说服力",
        "industry": "通用职场", "position": "应届求职者", "role_name": "业务面试官", "difficulty": "入门",
        "background": "你推荐了一种项目方案，但面试官担心执行成本与结果不确定性。",
        "goal": "用真实例子和可核查的依据回应顾虑，说明对对方的价值。",
        "tags": ["感染力", "事实说服", "结果表达"],
        "opening_line": "你为什么认为这个方案值得采用？请给我一个具体而可信的理由。",
    },
    {
        "id": "scene-foundation-relevance", "category": "基础能力提升", "title": "先回答对方真正的问题",
        "industry": "通用职场", "position": "应届求职者", "role_name": "招聘面试官", "difficulty": "入门",
        "background": "面试官连续追问你在团队项目中的个人贡献，容易被冗长背景带偏。",
        "goal": "先直接回应当前问题，再补充必要背景和依据，不偏离对方关切。",
        "tags": ["针对性", "直接回应", "识别关切"],
        "opening_line": "这个项目中你个人具体负责哪一部分？请先直接回答。",
    },
    {
        "id": "scene-foundation-concision", "category": "基础能力提升", "title": "30 秒讲清关键结论",
        "industry": "通用职场", "position": "应届求职者", "role_name": "忙碌的面试官", "difficulty": "入门",
        "background": "面试时间有限，面试官希望你用很短的回答说明最重要的项目结果。",
        "goal": "删除重复铺垫，用结论、关键依据和下一步构成紧凑回答。",
        "tags": ["简洁度", "30 秒表达", "信息密度"],
        "opening_line": "请在 30 秒内说明这个项目最重要的结果，以及你做了什么。",
    },
]

RETIRED_SCENE_IDS = ("scene-report-01", "scene-negotiation-01", "scene-meeting-01")

COURSES = [
    {
        "id": "course-logic-01",
        "title": "金字塔表达：先结论，再证据",
        "dimension": "逻辑性",
        "minutes": 18,
        "description": "把复杂信息压缩成听众能快速抓住的结构。",
        "content": "结论先行；同层互斥；证据支撑；用一句话复述结论。",
    },
    {
        "id": "course-tone-01",
        "title": "有分寸的坚定表达",
        "dimension": "得体性",
        "minutes": 15,
        "description": "在不同权力关系中保持尊重，同时清晰表达边界。",
        "content": "观察事实；说明影响；提出请求；确认共识。",
    },
    {
        "id": "course-impact-01",
        "title": "让观点更有说服力",
        "dimension": "感染力",
        "minutes": 20,
        "description": "用具体事实、对方收益和节奏设计增强说服力。",
        "content": "建立共同目标；用证据降低不确定性；用行动收尾。",
    },
    {
        "id": "course-relevance-01",
        "title": "先回应关切，再展开观点",
        "dimension": "针对性",
        "minutes": 16,
        "description": "识别对方真正的问题，让每句话都服务于当前沟通目标。",
        "content": "复述核心关切；先给直接答案；补充必要依据；确认是否解决问题。",
    },
    {
        "id": "course-concision-01",
        "title": "30 秒说清关键结论",
        "dimension": "简洁度",
        "minutes": 12,
        "description": "删除重复铺垫，用结论、依据和行动形成高密度表达。",
        "content": "一句话结论；两条关键依据；一个明确行动；删掉与决策无关的信息。",
    },
]


async def seed_database(session: AsyncSession, include_demo_users: bool = True) -> None:
    if include_demo_users and not await session.scalar(
        select(User.id).where(User.email == "student@example.com")
    ):
        session.add(
            User(
                id="demo-student",
                email="student@example.com",
                password_hash=hash_password("Student123!"),
                display_name="王同学",
                role="STUDENT",
            )
        )
    if include_demo_users and not await session.scalar(
        select(User.id).where(User.email == "admin@example.com")
    ):
        session.add(
            User(
                id="demo-admin",
                email="admin@example.com",
                password_hash=hash_password("Admin123!"),
                display_name="系统管理员",
                role="ADMIN",
            )
        )
    for legacy, category in LEGACY_CATEGORIES.items():
        await session.execute(
            update(Scene).where(Scene.category == legacy).values(category=category)
        )
    for item in SCENES:
        scene = await session.get(Scene, item["id"])
        if scene is None:
            session.add(Scene(**item))
        else:
            for field, value in item.items():
                setattr(scene, field, value)
            scene.active = True
    for scene_id in RETIRED_SCENE_IDS:
        old_scene = await session.get(Scene, scene_id)
        if old_scene is not None:
            old_scene.active = False
    for item in COURSES:
        if not await session.get(Course, item["id"]):
            session.add(Course(**item))
    await session.commit()
    await knowledge_store.upsert(
        [
            KnowledgeDocument("k-star", "STAR 回答法", "按情境、任务、行动、结果组织回答，行动与结果要具体可验证。", "面试"),
            KnowledgeDocument("k-pyramid", "面试表达结构", "面试回答先直接回应问题，再用具体经历说明依据，最后总结结果与岗位关联。", "面试"),
            KnowledgeDocument("k-followup", "面试经历追问", "按情境、任务、行动、结果组织面试回答，突出个人行动和可验证结果。", "面试"),
            KnowledgeDocument("k-interview-followup", "面试追问应对", "面对追问时先回应问题，再说明判断依据；不确定的事实应明确说明，不编造经历。", "面试"),
        ]
    )

