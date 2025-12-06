// 唤醒屏幕并执行任务的完整示例
function wakeScreenAndDoTask() {
    // 记录开始时间
    let startTime = new Date().getTime();
    
    // 尝试唤醒屏幕
    device.wakeUp();
    sleep(1500);
    
    // 如果唤醒失败，使用Power键
    if (!device.isScreenOn()) {
        keyCode(26);
        sleep(1500);
    }
    
    // 检查是否成功唤醒
    if (device.isScreenOn()) {
        toast("屏幕唤醒成功");
        
        // 在这里添加你要执行的任务
        // 例如：
        // launchApp("微信");
        // 或者执行其他自动化操作
        
    } else {
        toast("屏幕唤醒失败，请检查权限");
    }
    
    // 计算总耗时
    let endTime = new Date().getTime();
    console.log("总耗时：" + (endTime - startTime) + "ms");
}

// 执行函数
wakeScreenAndDoTask();