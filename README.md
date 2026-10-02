# PixelForge 依赖求解库

多平台依赖求解库，仅使用 Python 标准库（兼容 Python 3.11+，本机以 3.13 验证）。

## 数据模型

- `Version`：SemVer 2.0.0 版本，支持预发布标识符，不含构建元数据；预发布按标准顺序参与比较，无额外过滤。
- `Constraint`：精确版本或左闭右开区间 `[lo, hi)` 的并集，端点可为 `None`（无界）。
- `Catalog`：发布目录快照，含若干 `Release`（组件名、版本、直接依赖 `Dependency` 列表、各平台测试状态）。目录在单次求解期间视为不变。
- `RootRequest`：根请求（组件名 + 约束），允许同一组件重复出现，以列表位置区分。
- `targets`：非空平台集合；发布在全部目标平台上的状态都必须为 `"passed"` 才可用（`"failed"`、`"untested"` 或缺失均不可用）。

## API

```python
from pixelforge import (Catalog, Constraint, Dependency, Release,
                        RootRequest, Version, resolve)

result = resolve(catalog, roots, targets)
```

- 有解时返回 `Solution`：`result.versions` 为 `{组件名: Version}` 的扁平集合，每个组件恰好一个版本，且仅含根及递归引入的依赖；依赖图保证无环（含自环）。
- 无解时返回 `Conflict`：`result.root_indices` 为根请求位置的不可约子集——该子集自身无解，去掉其中任一请求即有解。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

测试内容：

- `tests/test_version.py`、`tests/test_constraint.py`：SemVer 排序与区间代数单元测试。
- `tests/test_solver.py`：定向用例——高版本引入共享依赖冲突或环、降级后有解（验证回退不遗留已放弃发布的约束）、平台状态淘汰、不可约冲突子集。
- `tests/test_random.py`：400 个随机小规模目录（含预发布与平台淘汰、半数植入可解结构），与独立穷举枚举逐项对照，验证解的合法性及冲突子集的不可约性。

## 运行示例

```bash
PYTHONPATH=. python3 examples/demo.py
```

## 代码结构

- `pixelforge/version.py`：SemVer 版本解析与比较。
- `pixelforge/constraint.py`：区间与约束（并集、交集、包含判定）。
- `pixelforge/catalog.py`：发布、依赖、目录数据类型及平台可用性判定。
- `pixelforge/solver.py`：回溯求解器（不可变状态传递，回退天然撤销约束）与删除式不可约冲突提取。
