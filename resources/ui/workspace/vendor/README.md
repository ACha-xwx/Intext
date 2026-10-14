# Liquid Metal

本地打包 `@paper-design/shaders` 0.0.81 的 `ShaderMount` 和 `liquidMetalFragmentShader`，Apache-2.0；保留同目录 LICENSE 和 NOTICE。用户银边按钮参考的运行参数及构建入口位于 `scripts/startup-metal-entry.js`。应用运行时不需要Node/npm/CDN。

从项目根目录重新构建（开发工具，不是启动依赖）：

```powershell
npm pack @paper-design/shaders@0.0.81 --pack-destination local_artifacts/intext_hero_20261013 --silent
tar -xf local_artifacts/intext_hero_20261013/paper-design-shaders-0.0.81.tgz -C local_artifacts/intext_hero_20261013
npx --yes esbuild@0.25.11 scripts/startup-metal-entry.js --bundle --format=iife --minify --alias:@paper-design/shaders=./local_artifacts/intext_hero_20261013/package/dist/index.js --outfile=resources/ui/workspace/vendor/liquid-metal.js
```

第一次构建前创建命令中的local_artifacts目标目录。全部资源随workspace目录打包；只在未完成教程的Hero显示按钮时挂载shader，离开Hero即dispose，减少动画时speed=0；WebGL不可用时静态银边继续可点击。
