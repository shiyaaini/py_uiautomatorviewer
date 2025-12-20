// get_ui_tree.js
auto.waitFor();
sleep(1000);

function nodeToJson(node, index) {
    if (!node) return null;
    var r = node.bounds();
    return {
        index: index || 0,
        text: node.text() || "",
        resource_id: node.id() || "",
        class_name: node.className() || "",
        package: node.packageName() || "",
        content_desc: node.desc() || "",
        checkable: String(node.checkable()),
        checked: String(node.checked()),
        clickable: String(node.clickable()),
        enabled: String(node.enabled()),
        focusable: String(node.focusable()),
        focused: String(node.focused()),
        scrollable: String(node.scrollable()),
        long_clickable: String(node.longClickable()),
        password: String(node.password()),
        selected: String(node.selected()),
        bounds: "[" + r.left + "," + r.top + "][" + r.right + "," + r.bottom + "]",
        children: node.children().map((child, i) => nodeToJson(child, i))
    };
}

var root = auto.rootInActiveWindow || auto.root;
var treeJson = nodeToJson(root, 0);
files.write("/sdcard/autojs_ui_tree.json", JSON.stringify(treeJson));