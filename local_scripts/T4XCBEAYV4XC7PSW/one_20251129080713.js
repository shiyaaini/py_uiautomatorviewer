'autojs'
// 由 panel_autojs 可视化工具生成
// 项目: one

let __lastFoundElement = null;

console.log("脚本开始执行: one");

launch("com.tencent.qqmusic");
console.show();
__lastFoundElement = text("首页").findOne(5000);
if (!__lastFoundElement) { console.log("未找到控件: text=首页"); } else { console.log("找到控件: text=首页"); }
console.log("逻辑与: " + "A && B");
if (!__lastFoundElement) {
  console.log("没有可点击的上一次查找结果");
} else {
  click(__lastFoundElement);
}
console.hide();
__lastFoundElement = text("").findOne(5000);
if (!__lastFoundElement) { console.log("未找到控件: text="); } else { console.log("找到控件: text="); }

console.log("脚本执行结束");
