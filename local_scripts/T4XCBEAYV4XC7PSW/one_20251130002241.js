'autojs'
// 由 panel_autojs 可视化工具生成
// 项目: one

let __lastFoundElement = null;

console.log("脚本开始执行: one");


// 节点: 启动应用 (n_1764274028572_0)
let v_n_1764274028572_0 = null;
launch("com.tencent.qqmusic");

// 节点: 控制台显示/隐藏 (n_1764373619491_3)
let v_n_1764373619491_3 = null;
console.show();

// 节点: 查找控件 (n_1764426406317_6)
let __lastFoundElement_1 = null;
__lastFoundElement_1 = text("首页").findOne(5000);
__lastFoundElement = __lastFoundElement_1;
if (!__lastFoundElement_1) { console.log("未找到控件: text=首页"); } else { console.log("找到控件: text=首页"); }

// 节点: 查找控件 (n_1764426634741_6)
let __lastFoundElement_2 = null;
__lastFoundElement_2 = text("我的L").findOne(5000);
__lastFoundElement = __lastFoundElement_2;
if (!__lastFoundElement_2) { console.log("未找到控件: text=我的L"); } else { console.log("找到控件: text=我的L"); }

// 节点: 逻辑与 (AND) (n_1764432935646_4)
let v_n_1764432935646_4 = null;
const A = __lastFoundElement_1;
const B = __lastFoundElement_2;
(function(){
  try {
    const __val = (A && B);
    v_n_1764432935646_4 = __val;
    console.log("逻辑与结果: " + String(__val));
    if (!__val) {
      console.log("逻辑与不满足");
    }
  } catch (e) {
    console.log("逻辑与表达式错误: " + String(e));
  }
})();

// 节点: 点击控件 (n_1764432950494_5)
let v_n_1764432950494_5 = null;
if (!v_n_1764432935646_4) {
  console.log("前置逻辑条件不满足，跳过点击");
} else {
  if (!__lastFoundElement_1) {
    console.log("目标变量 __lastFoundElement_1 为空，无法点击");
  } else {
    console.log("点击控件/坐标: " + __lastFoundElement_1);
    click(__lastFoundElement_1);
  }
}

// 节点: 控制台显示/隐藏 (n_1764432959846_6)
let v_n_1764432959846_6 = null;
if (!v_n_1764432935646_4) {
  console.log("前置逻辑条件不满足，跳过控制台操作");
} else {
  console.show();
}

console.log("脚本执行结束");
