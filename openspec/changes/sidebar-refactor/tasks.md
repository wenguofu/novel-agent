# Tasks: 侧边栏重构

- [ ] 1. 写测试: `tests/test_sidebar.py` 验证前端 novContext 逻辑
- [ ] 2. RED: 确认测试失败
- [ ] 3. 实现 `App.setNovelContext()` + `_getNovel()`
- [ ] 4. 实现 `init()` 中填充 novelCtxSelect
- [ ] 5. 实现 `navigate()` 中小说专属页面守卫
- [ ] 6. GREEN: 确认测试通过
- [ ] 7. 更新各 render 函数使用 `_getNovel()` 回退
- [ ] 8. 硬刷新验证全部页面
- [ ] 9. 提交 commit: `feat: sidebar novel context selector`
