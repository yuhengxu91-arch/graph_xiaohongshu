"""
视频脚本生成服务
使用 DeepSeek LLM 生成 + Tavily 搜索增强
支持多种视频模板类型
"""
import json
import re
from typing import Optional

from app.services.llm_service import llm_service
from app.services.tavily_service import tavily_service


# ============== 干货技能卡 Prompt ==============
KNOWLEDGE_SCRIPT_PROMPT = """你是一位顶级短视频编剧，专精知识干货类短视频。你的脚本必须像「刷到就停不下来」的抖音爆款。

## 任务
根据主题，生成一个 60~90 秒的干货短视频脚本。

{search_context}

## 输出格式
严格输出 JSON，不要包含任何其他文字：

```json
{{
  "title": "视频标题（15字以内，数字+痛点+利益点，如'3个技巧省下10万广告费'）",
  "scenes": [
    {{
      "scene_index": 0,
      "type": "intro",
      "narration": "开场旁白（必须以反问、数字或反直觉的事实开头，制造'不看后悔'的感觉）",
      "scene_title": "开场大字（8字以内，直击痛点）",
      "key_points": [],
      "duration_hint": 5
    }},
    {{
      "scene_index": 1,
      "type": "content",
      "narration": "第一个知识点的口播（口语化，像给好朋友安利，不要书面语）",
      "scene_title": "技巧一的标题（6字以内）",
      "key_points": [
        "第一条说明（8字以内，用动词开头）",
        "第二条说明",
        "第三条说明",
        "第四条说明"
      ],
      "code_example": "副描述（用具体数字，如'提升 300% 效率 · 一行代码搞定'）",
      "duration_hint": 15
    }},
    {{
      "scene_index": 2,
      "type": "content",
      "narration": "第二个知识点...",
      "scene_title": "技巧二标题",
      "key_points": ["...", "...", "...", "..."],
      "code_example": "副描述...",
      "duration_hint": 15
    }},
    {{
      "scene_index": 3,
      "type": "content",
      "narration": "第三个知识点...",
      "scene_title": "技巧三标题",
      "key_points": ["...", "...", "...", "..."],
      "code_example": "副描述...",
      "duration_hint": 15
    }},
    {{
      "scene_index": 4,
      "type": "outro",
      "narration": "结尾金句+引导关注（不超过2句，最后一句必须是行动号召）",
      "scene_title": "结尾标题",
      "key_points": [],
      "duration_hint": 5
    }}
  ],
  "total_duration_hint": 55
}}
```

## 爆款脚本法则
1. **开场3秒定生死**：用反直觉、数字冲击或痛点共鸣开头（如"90%的人不知道，Excel这个按钮能省2小时"）
2. **narration 是核心**：这是 TTS 会朗读出来的内容，必须口语化、有节奏、像朋友聊天
3. **key_points 精炼有力**：每条5-8字，用动词开头（如"消除重复代码"、"提升3倍查询速度"）
4. **scene_title 吸睛**：大字标题6字以内，技术类可用英文关键词
5. **节奏紧凑**：3个核心要点，总时长55~75秒，每段15秒左右
6. **用真实数据**：如果有搜索到的参考资料，务必引用具体数据让内容更有说服力"""


# ============== 数据可视化 Prompt ==============
DATA_VIZ_SCRIPT_PROMPT = """你是一位顶级数据可视化短视频编剧，擅长将数据变成吸引人的故事。

## 任务
根据主题，生成一个 60~90 秒的数据可视化短视频脚本。
脚本需要包含数字翻转、柱状图对比、数据卡片三种视觉效果。

{search_context}

## 输出格式
严格输出 JSON，不要包含任何其他文字：

```json
{{
  "title": "视频标题（15字以内，数字驱动，如'5组数据揭开行业真相'）",
  "scenes": [
    {{
      "scene_index": 0,
      "sceneType": "number_flip",
      "narration": "开场旁白（用震撼数据引入话题）",
      "sceneTitle": "核心数据指标",
      "audioDuration": 8,
      "metrics": [
        {{"label": "指标名称", "value": 1200, "suffix": "万", "color": "#818cf8"}},
        {{"label": "另一个指标", "value": 95, "suffix": "%", "color": "#34d399"}}
      ]
    }},
    {{
      "scene_index": 1,
      "sceneType": "bar_chart",
      "narration": "用对比数据讲故事（口语化，突出差异的震撼感）",
      "sceneTitle": "对比维度标题",
      "audioDuration": 10,
      "unit": "%",
      "bars": [
        {{"label": "A方案", "value": 85, "color": "#818cf8"}},
        {{"label": "B方案", "value": 42, "color": "#f97316"}},
        {{"label": "C方案", "value": 23, "color": "#ef4444"}}
      ]
    }},
    {{
      "scene_index": 2,
      "sceneType": "data_card",
      "narration": "总结关键发现和洞察",
      "sceneTitle": "关键洞察总结",
      "audioDuration": 10,
      "cards": [
        {{"icon": "📈", "title": "指标名", "value": "1,234万", "trend": "↑ 23%", "trendColor": "#34d399"}},
        {{"icon": "💰", "title": "指标名", "value": "¥8.5亿", "trend": "Top 1", "trendColor": "#818cf8"}},
        {{"icon": "🎯", "title": "指标名", "value": "96.7%", "trend": "新高", "trendColor": "#f59e0b"}}
      ]
    }},
    {{
      "scene_index": 3,
      "sceneType": "number_flip",
      "narration": "结尾总结（用数字收束，引导关注）",
      "sceneTitle": "总结数据",
      "audioDuration": 6,
      "metrics": [
        {{"label": "总结指标", "value": 100, "suffix": "%", "color": "#34d399"}}
      ]
    }}
  ],
  "total_duration_hint": 55
}}
```

## 数据可视化脚本法则
1. **数据要真实可信**：如果有搜索到的参考资料，务必使用真实数据
2. **每组数据讲一个故事**：对比要有冲击力（如"传统方法需要3天，新方法只要5分钟"）
3. **narration 是灵魂**：TTS 会朗读的内容，用对话式语气解读数据（"你能想象吗"、"换句话说"）
4. **颜色搭配**：推荐色值如 #818cf8(紫), #34d399(绿), #f97316(橙), #ef4444(红), #38bdf8(蓝), #f59e0b(黄)
5. **3~4个场景**，节奏紧凑，总时长 55~70 秒"""


# 模板 → Prompt 映射
TEMPLATE_PROMPTS = {
    "KnowledgeVideo": KNOWLEDGE_SCRIPT_PROMPT,
    "DataVizVideo": DATA_VIZ_SCRIPT_PROMPT,
}


class VideoScriptService:
    """视频脚本生成服务（DeepSeek + Tavily 搜索增强）"""

    async def generate_script(
        self,
        topic: str,
        style: Optional[str] = None,
        template: str = "KnowledgeVideo",
    ) -> dict:
        """
        根据主题和模板类型生成结构化视频脚本

        流程:
        1. Tavily 搜索主题相关资料
        2. 将搜索结果注入 Prompt
        3. DeepSeek 生成高质量脚本
        """
        # ===== Step 1: Tavily 搜索增强 =====
        search_context = ""
        try:
            search_result = await tavily_service.search_topic(topic, max_results=5)
            if search_result.get("success") and search_result.get("summary"):
                search_context = f"""## 参考资料（联网搜索获取的真实数据，请在脚本中引用）
{search_result['summary']}"""
                print(f"[VideoScript] Tavily 搜索成功，获得上下文 {len(search_context)} 字")
        except Exception as e:
            print(f"[VideoScript] Tavily 搜索跳过: {e}")

        # ===== Step 2: 构建消息 =====
        system_prompt_template = TEMPLATE_PROMPTS.get(template, KNOWLEDGE_SCRIPT_PROMPT)
        system_prompt = system_prompt_template.format(
            search_context=search_context if search_context else "（无额外参考资料）"
        )

        user_prompt = f"主题：{topic}"
        if style:
            user_prompt += f"\n风格：{style}"

        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # ===== Step 3: DeepSeek 生成脚本 =====
        try:
            response = await llm_service.llm_deepseek.ainvoke(messages)
            print(f"[VideoScript] 使用 DeepSeek 模型生成")
        except Exception as e:
            print(f"[VideoScript] DeepSeek 调用失败，回退到豆包标准: {e}")
            response = await llm_service.llm.ainvoke(messages)

        content = response.content.strip()

        # 解析 JSON
        script = self._parse_script_json(content)

        print(f"[VideoScript] 生成脚本: {script.get('title', '无标题')} "
              f"({len(script.get('scenes', []))} 个场景, 模板={template})")

        return script

    def _parse_script_json(self, content: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        # 尝试提取 code block 中的 JSON
        if "```" in content:
            content = re.sub(r'^.*?```(?:json)?\s*', '', content, flags=re.DOTALL)
            content = re.sub(r'\s*```.*$', '', content, flags=re.DOTALL)

        # 尝试找到 JSON 对象
        json_start = content.find('{')
        json_end = content.rfind('}')
        if json_start != -1 and json_end != -1:
            content = content[json_start:json_end + 1]

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[VideoScript] JSON 解析失败: {e}")
            return {
                "title": "脚本生成失败",
                "scenes": [
                    {
                        "scene_index": 0,
                        "type": "content",
                        "narration": content[:200] if content else "脚本内容解析失败",
                        "scene_title": "错误",
                        "key_points": ["脚本解析失败，请重试"],
                        "duration_hint": 5,
                    }
                ],
                "total_duration_hint": 5,
            }


# 单例
video_script_service = VideoScriptService()
