// 定义APK文件的绝对路径（需替换为你实际的APK路径）
var apkPath = "/storage/emulated/0/Download/huluxia.apk"; 
var file = new java.io.File(apkPath);

// 第一步：检查文件是否存在
if (!file.exists()) {
    toast("错误：APK文件不存在，请检查路径！");
    log("文件路径：" + apkPath);
    exit();
}

// 第二步：获取文件的URI（解决Android 7.0+的文件权限问题）
var uri;
if (android.os.Build.VERSION.SDK_INT >= 24) {
    // Android 7.0+ 必须使用FileProvider获取URI
    uri = android.support.v4.content.FileProvider.getUriForFile(
        context, 
        context.getPackageName() + ".fileprovider", 
        file
    );
} else {
    // Android 7.0以下直接使用文件URI
    uri = android.net.Uri.fromFile(file);
}

// 第三步：创建安装Intent并启动系统安装器
var Intent = android.content.Intent;
var intent = new Intent(Intent.ACTION_VIEW);
// 设置文件类型为APK安装包
intent.setDataAndType(uri, "application/vnd.android.package-archive");
// 授予临时读取权限（关键：否则系统安装器无法读取APK文件）
intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
// 以新任务启动安装界面，避免上下文冲突
intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

// 启动安装界面
try {
    context.startActivity(intent);
    toast("已唤起系统安装器，请手动确认安装");
} catch (e) {
    toast("唤起安装器失败：" + e.message);
    log("错误详情：", e);
}