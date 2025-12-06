var v = device.getMusicVolume();
var max = device.getMusicMaxVolume();
var nv = v + 10;
if (nv > max) nv = max;
device.setMusicVolume(nv);
