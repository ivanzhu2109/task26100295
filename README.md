# PixelForge 依赖求解库

纯 Python 标准库实现（兼容 Python 3.11+，无第三方依赖）的多平台依赖求解库。

## 功能

`resolve(catalog, roots, targets)` 在未撤回的目录快照上求解：

- 同名组件恰好选一个版本，解仅含 roots 及递归依赖引入的组件；
- 根约束与所有选中发布的依赖约束同时满足（约束为精确版本或左闭右开区间的并集，端点可无界）；
- 每个选中发布在 `targets` 全部平台上的测试状态均为 `passed`；
- 按实际选中发布构成的依赖图无环（含自环）；
- 有解返回任意一个 `Solution`；无解返回 `Conflict`，携带按请求位置区分的不可约根请求子集（自身无解，去掉任一请求即有解）。

版本遵循 SemVer 2.0.0（支持预发布，不含构建元数据），预发布按标准顺序参与区间比较，无额外过滤。

## 数据类型

```python
from pixelforge import (
    Catalog, Release, Dependency, RootRequest,
    Version, VersionSet, Solution, Conflict, resolve,
)

catalog = Catalog()
catalog.add(Release(
    name="app",
    version=Version.parse("1.2.0"),
    dependencies=(Dependency("lib", VersionSet.range(
        Version.parse("1.0.0"), Version.parse("2.0.0"))),),
    passed_platforms=frozenset({"linux", "win"}),  # 未列出的平台视为不可用
))

result = resolve(
    catalog,
    roots=[RootRequest("app", VersionSet.exact(Version.parse("1.2.0")))],
    targets={"linux", "win"},
)

if isinstance(result, Solution):
    print(dict(result.selections))   # {'app': 1.2.0, 'lib': ...}
else:
    print(result.root_indices)       # 不可约冲突子集的根请求下标
```

- `VersionSet.exact(v)`：精确版本；`VersionSet.range(low, high)`：左闭右开区间，
  端点传 `None` 表示无界；`union` / `intersect` 组合区间并集。
- `roots` 允许同一组件出现多次，约束取交集；冲突子集以列表位置区分重复项。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

测试包括：

- `tests/test_version_constraints.py`：SemVer 解析/排序与区间集合运算；
- `tests/test_solver.py`：场景测试，含高版本引入共享依赖冲突或环、降级后有解的
  回溯案例，验证撤销先前选择后不留已放弃发布的依赖；
- `tests/test_exhaustive.py`：400 个随机小目录（覆盖预发布与平台淘汰）与独立
  穷举枚举对照，逐项校验返回解的合法性及冲突子集的不可约性。

## 代码结构

- `pixelforge/version.py`：SemVer 2.0.0 版本解析与比较；
- `pixelforge/constraints.py`：左闭右开区间并集（`VersionSet`）；
- `pixelforge/model.py`：目录、发布、根请求、解与冲突的数据类型；
- `pixelforge/solver.py`：带回溯、前向检查与环检测的求解器，以及基于删除法的
  不可约冲突子集提取。
