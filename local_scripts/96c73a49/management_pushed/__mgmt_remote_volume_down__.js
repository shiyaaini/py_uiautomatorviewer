var v = device.getMusicVolume();
var nv = v - 10;
if (nv < 0) nv = 0;
device.setMusicVolume(nv);
