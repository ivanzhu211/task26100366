# task26100366

招聘内容敏感词扫描库（纯 Python，无第三方依赖）。词库存本地 JSON，
正文与扫描状态仅驻留内存，供上层审核流程流式调用。

## 特性

- 归一化语义：逐码点 NFKD → casefold → 删除类别 M*/P*/Cf 及 White_Space 字符，
  可识别全角、大小写、标点、不可见字符掩饰的敏感表达。
- 流式匹配：基于 Aho-Corasick，正文可按任意字节边界分块喂入（允许截断多字节字符），
  每块返回当前可确定的全部命中，可逐条消费。
- 精确区间：命中携带原文 UTF-8 字节区间（起点包含、终点不包含），
  中间被忽略的字符计入区间，码点部分展开命中时覆盖完整码点字节。
- 去重语义：同一规则 ID + 同一字节区间只交付一次；不同规则各自交付。

## 用法

```python
from sensitive_scanner import Scanner

scanner = Scanner.from_json_file("lexicon.example.json")
# 或 Scanner({"规则ID": ["词形", ...]})

for chunk in upstream_chunks:          # bytes，任意分块
    for hit in scanner.feed(chunk):    # Hit(rule_id, start, end)
        audit(hit.rule_id, hit.start, hit.end)
for hit in scanner.finish():           # 冲刷尾部状态
    audit(hit.rule_id, hit.start, hit.end)
```

词库 JSON 格式：`{"规则ID": ["词形", ...], ...}`，见 `lexicon.example.json`。

## 测试

```sh
python3 -m unittest discover -s tests -v
```
