# task26100366
招聘内容敏感词扫描库（纯内存流式扫描，词库存本地 JSON）。

## 用法

```python
from sensitive_scan import Scanner

scanner = Scanner.from_json("lexicon.json")  # {"规则ID": ["词形", ...], ...}
for chunk in upstream_chunks:                # 任意字节边界分块
    for hit in scanner.feed(chunk):          # 逐条消费命中
        print(hit.rule_id, hit.start, hit.end)  # 原文 UTF-8 字节区间 [start, end)
scanner.finish()                             # 结束输入；末尾字符不完整会抛错
```

## 语义

- 词形与正文逐码点做 NFKD + casefold，再删除类别 M*/P*/Cf 及 White_Space 字符后匹配。
- 允许词内、重叠、前后缀同时命中；命中区间覆盖首个到末个参与匹配的原始码点的完整字节。
- 同一规则ID + 同一字节区间只交付一次；不同规则ID 各自交付。

## 测试

```bash
python3 -m pytest tests/ -q
```
