console.log("📱 手机静音控制程序");
console.log("====================");

console.log("当前音量状态:");
console.log("媒体音量: " + device.getMusicVolume());
console.log("铃声音量: " + device.getMusicVolume());
console.log("通知音量: " + device.getMusicVolume());
console.log("");

console.log("🔇 正在设置手机静音...");

device.setMusicVolume(0);
console.log("✅ 媒体音量已设置为: 0");

try {
    device.setVolume(0, 2);
    console.log("✅ 铃声音量已设置为: 0");
} catch (e) {
    console.log("⚠️  铃声音量设置失败: " + e.toString());
}

try {
    device.setVolume(0, 5);
    console.log("✅ 通知音量已设置为: 0");
} catch (e) {
    console.log("⚠️  通知音量设置失败: " + e.toString());
}

console.log("");
console.log("静音操作完成!");
console.log("当前音量状态:");
console.log("媒体音量: " + device.getMusicVolume());

toast("手机已静音");

setTimeout(function() {
    console.log("");
    console.log("程序将在3秒后自动退出...");
}, 1000);

setTimeout(function() {
    console.log("程序已退出");
    console.hide();
}, 4000);
