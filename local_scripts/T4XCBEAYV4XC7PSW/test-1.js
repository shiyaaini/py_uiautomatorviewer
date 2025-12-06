'autojs'
// 由 panel_autojs 可视化工具生成
// 项目: one
console.show()
console.log("脚本开始执行: one");

launch("com.example.tcllogin");
sleep(1000);
let w = selector().id("navigation_profile").desc("我的").className("android.widget.FrameLayout").findOne();
w.click();

console.log("脚本执行结束");
console.show();
