# 项目规则

## 字数统计

统计纯汉字（中文字符）数量时，使用以下命令：

```bash
# 正确方式（Python）
python3 -c "
import re, sys
for f in sys.argv[1:]:
    with open(f) as fp:
        chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', fp.read()))
        print(f'{f}: {chars} 汉字')
" <文件1> <文件2> ...

# 批量统计示例
cd manuscript/vol-02 && python3 -c "
import re, os
files = [f for f in os.listdir('.') if f.endswith('.md')]
for f in sorted(files):
    chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', open(f).read()))
    print(f'{f}: {chars} 汉字')
"
```

**注意**：`tr -cd '一-龥'` 在某些 shell 环境中范围不准确，不要使用。

## 字数要求

- 每章纯汉字数不得少于 2,500 字。
- 统计时只统计中文字符（Unicode 范围：\u4e00-\u9fff, \u3400-\u4dbf），不包含标点、数字、英文、Markdown 格式字符。
